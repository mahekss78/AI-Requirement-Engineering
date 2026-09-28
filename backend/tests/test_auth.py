"""
tests/test_auth.py
==================
Phase A unit and integration tests: Authentication, Session, and Role Immutability.

Tests:
1. Account registration and duplicate email rejection.
2. Login credential verification (valid/invalid password).
3. Session cookie / token retrieval and validation.
4. One-time role assignment (BUSINESS_ANALYST, CLIENT, DEVELOPER, QA, PRODUCT_OWNER).
5. Role immutability enforcement (server-side rejection of subsequent role change attempts).
6. Account deactivation (preserves historical record, revokes session, prevents login).
7. Inactive account access rejection.
8. Logout session invalidation.
9. Forgot password interface stub.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.models import Account, UserSession
from app.services.auth import SESSION_COOKIE_NAME, auth_service
from main import app

client = TestClient(app)


# ------------------------------------------------------------------ #
# 1. Registration Tests
# ------------------------------------------------------------------ #


def test_register_account_success(test_db: Session):
    response = client.post(
        "/api/auth/register",
        json={"email": "ba@xyz.com", "password": "securepassword123"},
    )
    assert response.status_code == 201
    data = response.json()

    assert data["authenticated"] is True
    assert data["user"]["email"] == "ba@xyz.com"
    assert data["account_status"] == "ACTIVE"
    assert data["assigned_role"] is None
    assert SESSION_COOKIE_NAME in response.cookies


def test_register_duplicate_email_fails(test_db: Session):
    # First registration
    client.post(
        "/api/auth/register",
        json={"email": "dup@xyz.com", "password": "password123"},
    )

    # Second registration with same email
    response = client.post(
        "/api/auth/register",
        json={"email": "dup@xyz.com", "password": "password456"},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


# ------------------------------------------------------------------ #
# 2. Login Tests
# ------------------------------------------------------------------ #


def test_login_success(test_db: Session):
    # Register
    client.post(
        "/api/auth/register",
        json={"email": "user@xyz.com", "password": "mypassword"},
    )

    # Login
    response = client.post(
        "/api/auth/login",
        json={"email": "user@xyz.com", "password": "mypassword"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["user"]["email"] == "user@xyz.com"
    assert SESSION_COOKIE_NAME in response.cookies


def test_login_invalid_password_fails(test_db: Session):
    client.post(
        "/api/auth/register",
        json={"email": "wrongpass@xyz.com", "password": "correct_password"},
    )

    response = client.post(
        "/api/auth/login",
        json={"email": "wrongpass@xyz.com", "password": "wrong_password"},
    )
    assert response.status_code == 401
    assert "Invalid email address or password" in response.json()["detail"]


# ------------------------------------------------------------------ #
# 3. Session Management Tests
# ------------------------------------------------------------------ #


def test_session_unauthenticated():
    # Fresh client without cookies
    fresh_client = TestClient(app)
    response = fresh_client.get("/api/auth/session")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is False
    assert data["user"] is None
    assert data["assigned_role"] is None


def test_session_authenticated(test_db: Session):
    # Register / login using client session
    c = TestClient(app)
    c.post(
        "/api/auth/register",
        json={"email": "sessionuser@xyz.com", "password": "password123"},
    )

    response = c.get("/api/auth/session")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["user"]["email"] == "sessionuser@xyz.com"
    assert data["account_status"] == "ACTIVE"


# ------------------------------------------------------------------ #
# 4. Role Assignment & Immutability Tests
# ------------------------------------------------------------------ #


def test_role_assignment_success(test_db: Session):
    c = TestClient(app)
    c.post(
        "/api/auth/register",
        json={"email": "ba_role@xyz.com", "password": "password123"},
    )

    # Assign role
    response = c.post("/api/auth/role", json={"role": "BUSINESS_ANALYST"})
    assert response.status_code == 200
    data = response.json()
    assert data["assigned_role"] == "BUSINESS_ANALYST"

    # Verify session now reflects assigned role
    sess_resp = c.get("/api/auth/session")
    assert sess_resp.json()["assigned_role"] == "BUSINESS_ANALYST"


def test_role_assignment_invalid_role_fails(test_db: Session):
    c = TestClient(app)
    c.post(
        "/api/auth/register",
        json={"email": "badrole@xyz.com", "password": "password123"},
    )

    # Try assigning non-supported role "STUDENT"
    response = c.post("/api/auth/role", json={"role": "STUDENT"})
    assert response.status_code == 422  # Pydantic validation error or 400


def test_role_immutability_server_side_rejection(test_db: Session):
    c = TestClient(app)
    c.post(
        "/api/auth/register",
        json={"email": "immutable@xyz.com", "password": "password123"},
    )

    # Initial assignment -> SUCCESS
    resp1 = c.post("/api/auth/role", json={"role": "BUSINESS_ANALYST"})
    assert resp1.status_code == 200
    assert resp1.json()["assigned_role"] == "BUSINESS_ANALYST"

    # Subsequent assignment attempt (trying to change to DEVELOPER) -> REJECTED
    resp2 = c.post("/api/auth/role", json={"role": "DEVELOPER"})
    assert resp2.status_code == 400
    assert "already has assigned role" in resp2.json()["detail"]

    # Verify role remains unchanged as BUSINESS_ANALYST
    sess = c.get("/api/auth/session")
    assert sess.json()["assigned_role"] == "BUSINESS_ANALYST"


# ------------------------------------------------------------------ #
# 5. Account Deactivation Tests
# ------------------------------------------------------------------ #


def test_deactivate_account_preserves_data(test_db: Session):
    c = TestClient(app)
    reg_resp = c.post(
        "/api/auth/register",
        json={"email": "deactivate@xyz.com", "password": "password123"},
    )
    user_id = reg_resp.json()["user"]["id"]

    # Deactivate account
    deact_resp = c.post("/api/auth/deactivate")
    assert deact_resp.status_code == 200
    assert "deactivated" in deact_resp.json()["message"].lower()

    # Session is now unauthenticated
    sess = c.get("/api/auth/session")
    assert sess.json()["authenticated"] is False

    # Attempting to login fails with 403 Forbidden
    login_resp = c.post(
        "/api/auth/login",
        json={"email": "deactivate@xyz.com", "password": "password123"},
    )
    assert login_resp.status_code == 403
    assert "inactive" in login_resp.json()["detail"].lower()

    # Account record MUST still exist in database with status INACTIVE (history preserved)
    account_in_db = test_db.query(Account).filter(Account.email == "deactivate@xyz.com").first()
    assert account_in_db is not None
    assert account_in_db.account_status == "INACTIVE"


# ------------------------------------------------------------------ #
# 6. Logout Tests
# ------------------------------------------------------------------ #


def test_logout(test_db: Session):
    c = TestClient(app)
    c.post(
        "/api/auth/register",
        json={"email": "logoutuser@xyz.com", "password": "password123"},
    )

    # Confirm authenticated
    assert c.get("/api/auth/session").json()["authenticated"] is True

    # Logout
    logout_resp = c.post("/api/auth/logout")
    assert logout_resp.status_code == 200

    # Confirm unauthenticated
    assert c.get("/api/auth/session").json()["authenticated"] is False


# ------------------------------------------------------------------ #
# 7. Forgot Password Stub Test
# ------------------------------------------------------------------ #


def test_forgot_password_stub():
    response = client.post("/api/auth/forgot-password", json={"email": "test@xyz.com"})
    assert response.status_code == 200
    assert "dispatched" in response.json()["message"]
