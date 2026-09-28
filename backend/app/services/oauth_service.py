"""
app/services/oauth_service.py
==============================
OAuth 2.0 Identity & Session Integration Service.

Responsibilities:
1. Short-lived OAuthState creation and transaction cookie hash validation.
2. Google OAuth 2.0 authorization code exchange and userinfo validation.
3. Authoritative (provider, provider_user_id) identity matching.
4. Safe account linking enforcing provider email verification.
5. Integration with standard AREA Account and UserSession creation.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import Account, OAuthAccount, OAuthState, UserSession
from app.services.auth import auth_service

logger = logging.getLogger(__name__)

OAUTH_STATE_COOKIE_NAME = "area_oauth_state"
OAUTH_STATE_LIFETIME_MINUTES = 10


class OAuthService:
    """
    Core security authority for OAuth 2.0 flows, CSRF protection, and account linking.
    """

    # ------------------------------------------------------------------ #
    # 1. State Management & Browser Transaction Binding
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_oauth_state(db: Session, provider: str) -> Tuple[str, str]:
        """
        Generates:
        - state_token: URL parameter sent to OAuth provider.
        - cookie_secret: Opaque secret string stored in HttpOnly area_oauth_state cookie.

        Persists OAuthState in DB with transaction_cookie_hash = SHA256(cookie_secret).
        """
        state_token = secrets.token_urlsafe(32)
        cookie_secret = secrets.token_urlsafe(32)
        cookie_hash = hashlib.sha256(cookie_secret.encode("utf-8")).hexdigest()

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=OAUTH_STATE_LIFETIME_MINUTES)

        state_record = OAuthState(
            state_token=state_token,
            provider=provider,
            transaction_cookie_hash=cookie_hash,
            is_used=False,
            expires_at=expires_at,
        )
        db.add(state_record)
        db.commit()
        db.refresh(state_record)
        return state_token, cookie_secret

    @staticmethod
    def validate_and_consume_state(
        db: Session, state_token: str, provider: str, raw_cookie_secret: Optional[str]
    ) -> bool:
        """
        Validates state token and browser transaction cookie secret.
        Must satisfy:
        1. Record exists and provider matches.
        2. is_used is False (prevents replay).
        3. expires_at > now() (prevents expired tokens).
        4. SHA256(raw_cookie_secret) == transaction_cookie_hash.

        Marks is_used = True and sets consumed_at timestamp upon success.
        """
        if not state_token or not raw_cookie_secret:
            logger.warning("OAuth callback missing state token or transaction cookie secret.")
            return False

        state_record = db.query(OAuthState).filter(OAuthState.state_token == state_token).first()
        if not state_record:
            logger.warning(f"OAuth state token '{state_token}' not found.")
            return False

        if state_record.provider != provider:
            logger.warning(f"OAuth state provider mismatch: expected {state_record.provider}, got {provider}.")
            return False

        if state_record.is_used:
            logger.warning(f"OAuth state token '{state_token}' already used (replay attempt).")
            return False

        now = datetime.now(timezone.utc)
        expires_at = state_record.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < now:
            logger.warning(f"OAuth state token '{state_token}' has expired.")
            return False

        computed_hash = hashlib.sha256(raw_cookie_secret.encode("utf-8")).hexdigest()
        if computed_hash != state_record.transaction_cookie_hash:
            logger.warning("OAuth transaction cookie hash mismatch (CSRF / browser mismatch).")
            return False

        # Consume token atomically
        state_record.is_used = True
        state_record.consumed_at = now
        db.commit()
        return True

    # ------------------------------------------------------------------ #
    # 2. Account Lookup & Safe Account-Linking Policy
    # ------------------------------------------------------------------ #

    def get_or_create_oauth_account(
        self,
        db: Session,
        provider: str,
        provider_user_id: str,
        email: Optional[str],
        email_verified: bool,
    ) -> Account:
        """
        Safe Account-Linking Workflow:
        1. Primary Match: Check for existing OAuthAccount record matching (provider, provider_user_id).
           - If found, return existing linked Account.
        2. Safe Email Linking:
           - If email is present AND email_verified is True:
             - Check if existing Account exists with matching email.
             - If existing Account found, link new OAuthAccount identity to existing Account.
             - If no existing Account found, create new Account (password_hash=None, assigned_role=None).
        3. Unverified Email / No Email:
           - If email is unverified (email_verified=False) AND no existing OAuthAccount found,
             raise HTTP 400 Bad Request to prevent account takeover.
        """
        provider_user_id_clean = str(provider_user_id).strip()
        email_clean = email.strip().lower() if email else None

        # 1. Authoritative Lookup by (provider, provider_user_id)
        existing_oauth = (
            db.query(OAuthAccount)
            .filter(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == provider_user_id_clean,
            )
            .first()
        )
        if existing_oauth:
            account = db.query(Account).filter(Account.id == existing_oauth.account_id).first()
            if account:
                if account.account_status != "ACTIVE":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Account is inactive. Please contact your system administrator.",
                    )
                account.last_login_at = datetime.now(timezone.utc)
                db.commit()
                return account

        # 2. Enforce Verified Email Policy for new links
        if not email_verified or not email_clean:
            logger.warning(
                f"OAuth login for provider '{provider}' ID '{provider_user_id_clean}' rejected: "
                f"email '{email_clean}' is unverified."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth account linking rejected: provider email is unverified.",
            )

        # 3. Check for existing AREA Account by verified email
        existing_account = db.query(Account).filter(Account.email == email_clean).first()

        if existing_account:
            if existing_account.account_status != "ACTIVE":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is inactive. Please contact your system administrator.",
                )
            account = existing_account
            logger.info(f"Linking new OAuth identity ({provider}:{provider_user_id_clean}) to existing account {account.email}")
        else:
            # Create new passwordless Account
            account = Account(
                email=email_clean,
                password_hash=None,  # Null for OAuth accounts
                account_status="ACTIVE",
                assigned_role=None,  # Triggers initial role selection flow
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            logger.info(f"Created new OAuth account for {email_clean} (ID: {account.id}) via {provider}")

        # 4. Record OAuthAccount link
        oauth_link = OAuthAccount(
            account_id=account.id,
            provider=provider,
            provider_user_id=provider_user_id_clean,
            provider_email=email_clean,
        )
        db.add(oauth_link)
        account.last_login_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(account)
        return account

    # ------------------------------------------------------------------ #
    # 3. Google OAuth 2.0 Protocol Flow
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_google_authorize_url(state: str) -> str:
        """Constructs Google OAuth 2.0 authorization URL."""
        if not settings.is_google_oauth_configured:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google OAuth is not configured on this server.",
            )

        base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
        query_string = "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items())
        return f"{base_url}?{query_string}"

    def process_google_callback(
        self, db: Session, code: str, state_token: str, raw_cookie_secret: Optional[str]
    ) -> Tuple[Account, UserSession]:
        """
        Executes Google authorization code exchange, verifies state, fetches userinfo,
        links/creates Account, and generates standard AREA UserSession.
        """
        # 1. Validate State & Browser Binding Cookie
        if not self.validate_and_consume_state(db, state_token, "google", raw_cookie_secret):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OAuth state parameter (CSRF check failed).",
            )

        if not settings.is_google_oauth_configured:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google OAuth is not configured on this server.",
            )

        # 2. Exchange authorization code for Google tokens
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                token_res = client.post(token_url, data=payload)
                if token_res.status_code != 200:
                    logger.error(f"Google token exchange failed (HTTP {token_res.status_code}): {token_res.text[:200]}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to exchange authorization code with Google.",
                    )
                tokens = token_res.json()
                access_token = tokens.get("access_token")

                # Fetch Userinfo profile
                userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
                headers = {"Authorization": f"Bearer {access_token}"}
                userinfo_res = client.get(userinfo_url, headers=headers)
                if userinfo_res.status_code != 200:
                    logger.error(f"Google userinfo fetch failed (HTTP {userinfo_res.status_code})")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to retrieve profile information from Google.",
                    )
                userinfo = userinfo_res.json()

        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Unexpected error during Google OAuth callback: {type(exc).__name__}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Google OAuth authentication service error.",
            )

        # 3. Extract Identity & Claims
        provider_user_id = userinfo.get("sub")
        email = userinfo.get("email")
        email_verified = bool(userinfo.get("email_verified", False))

        if not provider_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google userinfo response did not contain a subject identifier (sub).",
            )

        # 4. Safe Account Link/Creation
        account = self.get_or_create_oauth_account(
            db=db,
            provider="google",
            provider_user_id=provider_user_id,
            email=email,
            email_verified=email_verified,
        )

        # 5. Create Standard AREA Session
        user_session = auth_service.create_session(db, account.id)
        return account, user_session


oauth_service = OAuthService()
