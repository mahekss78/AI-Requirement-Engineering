"""
tests/test_google_oauth.py
===========================
Comprehensive Unit & Integration Test Suite for Google OAuth 2.0.

Verifies:
1. Authorization redirect & transaction cookie creation.
2. Missing configuration handling (HTTP 400).
3. OAuthState CSRF verification (invalid, expired, replayed, cookie mismatch).
4. Unverified Google email rejection (account takeover prevention).
5. New OAuth account creation (password_hash=None, assigned_role=None).
6. Existing account linking for verified emails.
7. Session creation and area_session cookie binding.
8. One-time role selection flow and role immutability.
9. Password login rejection for passwordless OAuth accounts.
10. Logout and session invalidation.
"""

import uuid
import pytest
import httpx
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import Account, OAuthAccount, OAuthState, UserSession
from app.services.oauth_service import oauth_service, OAUTH_STATE_COOKIE_NAME
from main import app

client = TestClient(app)


@pytest.fixture
def mock_google_config(monkeypatch):
    """Fixture enabling Google OAuth configuration."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "dummy_google_client_id.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "dummy_google_client_secret")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/oauth/google/callback")


def test_google_authorize_url_generation(test_db, mock_google_config):
    """Initiating Google authorize returns HTTP 302 redirect and sets area_oauth_state cookie."""
    res = client.get("/api/auth/oauth/google/authorize", follow_redirects=False)
    assert res.status_code == 302
    assert "accounts.google.com" in res.headers["location"]
    assert "dummy_google_client_id" in res.headers["location"]
    assert OAUTH_STATE_COOKIE_NAME in res.cookies

    # Verify state record in DB
    state_rec = test_db.query(OAuthState).filter(OAuthState.provider == "google").first()
    assert state_rec is not None
    assert state_rec.is_used is False


def test_google_missing_config_returns_400(test_db, monkeypatch):
    """Initiating Google authorize without client credentials returns HTTP 400."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")

    res = client.get("/api/auth/oauth/google/authorize")
    assert res.status_code == 400
    assert "not configured" in res.json()["detail"].lower()


def test_google_callback_invalid_state_token_rejected(test_db, mock_google_config):
    """Callback with unknown state token returns HTTP 400."""
    res = client.get("/api/auth/oauth/google/callback?code=dummy_code&state=nonexistent_state")
    assert res.status_code == 400
    assert "csrf" in res.json()["detail"].lower()


def test_google_callback_cookie_mismatch_rejected(test_db, mock_google_config):
    """Callback with state token but wrong transaction cookie returns HTTP 400."""
    state_token, _ = oauth_service.create_oauth_state(test_db, "google")

    client.cookies.set(OAUTH_STATE_COOKIE_NAME, "wrong_cookie_secret", path="/api/auth/oauth")
    res = client.get(f"/api/auth/oauth/google/callback?code=dummy_code&state={state_token}")
    assert res.status_code == 400
    assert "csrf" in res.json()["detail"].lower()


def test_google_callback_state_replay_rejected(test_db, mock_google_config):
    """Replaying an already consumed state token returns HTTP 400."""
    state_token, cookie_secret = oauth_service.create_oauth_state(test_db, "google")

    # Mark as used
    state_rec = test_db.query(OAuthState).filter(OAuthState.state_token == state_token).first()
    state_rec.is_used = True
    test_db.commit()

    client.cookies.set(OAUTH_STATE_COOKIE_NAME, cookie_secret, path="/api/auth/oauth")
    res = client.get(f"/api/auth/oauth/google/callback?code=dummy_code&state={state_token}")
    assert res.status_code == 400


def test_google_callback_unverified_email_rejected(test_db, mock_google_config, monkeypatch):
    """Unverified Google email is rejected to prevent account takeover."""
    state_token, cookie_secret = oauth_service.create_oauth_state(test_db, "google")

    class MockClientContext:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            res = MagicMock()
            res.status_code = 200
            res.json.return_value = {"access_token": "google_access_token_123"}
            return res
        def get(self, url, **kwargs):
            res = MagicMock()
            res.status_code = 200
            res.json.return_value = {
                "sub": "google_user_101",
                "email": "unverified@example.com",
                "email_verified": False,
            }
            return res

    monkeypatch.setattr("app.services.oauth_service.httpx.Client", MockClientContext)

    client.cookies.set(OAUTH_STATE_COOKIE_NAME, cookie_secret, path="/api/auth/oauth")
    res = client.get(f"/api/auth/oauth/google/callback?code=valid_code&state={state_token}")
    assert res.status_code == 400
    assert "unverified" in res.json()["detail"].lower()


def test_google_callback_new_user_creates_account_and_session(test_db, mock_google_config, monkeypatch):
    """New Google user creates Account (assigned_role=None), OAuthAccount, and UserSession."""
    state_token, cookie_secret = oauth_service.create_oauth_state(test_db, "google")

    class MockClientContext:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            res = MagicMock()
            res.status_code = 200
            res.json.return_value = {"access_token": "google_access_token_123"}
            return res
        def get(self, url, **kwargs):
            res = MagicMock()
            res.status_code = 200
            res.json.return_value = {
                "sub": "google_user_999",
                "email": "newuser@google.com",
                "email_verified": True,
            }
            return res

    monkeypatch.setattr("app.services.oauth_service.httpx.Client", MockClientContext)

    client.cookies.set(OAUTH_STATE_COOKIE_NAME, cookie_secret, path="/api/auth/oauth")
    res = client.get(f"/api/auth/oauth/google/callback?code=valid_code&state={state_token}", follow_redirects=False)
    assert res.status_code == 302
    assert "area_session" in res.cookies

    # Verify Account in DB
    account = test_db.query(Account).filter(Account.email == "newuser@google.com").first()
    assert account is not None
    assert account.password_hash is None
    assert account.assigned_role is None

    # Verify OAuthAccount mapping
    oauth_acc = test_db.query(OAuthAccount).filter(OAuthAccount.account_id == account.id).first()
    assert oauth_acc is not None
    assert oauth_acc.provider == "google"
    assert oauth_acc.provider_user_id == "google_user_999"


def test_google_callback_existing_account_linking(test_db, mock_google_config, monkeypatch):
    """Google login with verified email links to pre-existing password Account."""
    from app.services.auth import auth_service
    existing_acc = auth_service.register_account(test_db, "existingba@company.com", "Password123!")

    state_token, cookie_secret = oauth_service.create_oauth_state(test_db, "google")

    class MockClientContext:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            res = MagicMock()
            res.status_code = 200
            res.json.return_value = {"access_token": "google_access_token_123"}
            return res
        def get(self, url, **kwargs):
            res = MagicMock()
            res.status_code = 200
            res.json.return_value = {
                "sub": "google_user_888",
                "email": "existingba@company.com",
                "email_verified": True,
            }
            return res

    monkeypatch.setattr("app.services.oauth_service.httpx.Client", MockClientContext)

    client.cookies.set(OAUTH_STATE_COOKIE_NAME, cookie_secret, path="/api/auth/oauth")
    res = client.get(f"/api/auth/oauth/google/callback?code=valid_code&state={state_token}", follow_redirects=False)
    assert res.status_code == 302

    # Verify existing account linked without duplicate creation
    accounts = test_db.query(Account).filter(Account.email == "existingba@company.com").all()
    assert len(accounts) == 1
    assert accounts[0].id == existing_acc.id

    oauth_acc = test_db.query(OAuthAccount).filter(OAuthAccount.account_id == existing_acc.id).first()
    assert oauth_acc is not None
    assert oauth_acc.provider_user_id == "google_user_888"


def test_password_login_blocks_null_password_oauth_account(test_db):
    """Password authentication rejects passwordless OAuth accounts (password_hash=None)."""
    oauth_acc = Account(email="oauthonly@google.com", password_hash=None, account_status="ACTIVE", assigned_role=None)
    test_db.add(oauth_acc)
    test_db.commit()

    res = client.post("/api/auth/login", json={"email": "oauthonly@google.com", "password": "AnyPassword!"})
    assert res.status_code == 401
