"""
app/services/auth.py
====================
Authentication, Session, and Account Management Service.

Responsibilities:
1. Secure password hashing and verification using passlib (bcrypt).
2. Account registration and authentication.
3. Server-managed session creation and verification.
4. One-time, permanent role binding (BUSINESS_ANALYST, CLIENT, DEVELOPER, QA, PRODUCT_OWNER).
5. Role immutability enforcement (rejects subsequent role assignment attempts).
6. Account deactivation (sets status to INACTIVE, invalidates sessions, preserves history).
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.models import Account, UserSession
from app.schemas.schemas import SUPPORTED_ROLES

logger = logging.getLogger(__name__)

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_COOKIE_NAME = "area_session"
DEFAULT_SESSION_DURATION_HOURS = 24


class AuthService:
    """
    Core backend security authority for identity, session, and role binding.
    """

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a plaintext password securely using bcrypt."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plaintext password against a stored bcrypt hash."""
        return pwd_context.verify(plain_password, hashed_password)

    # ------------------------------------------------------------------ #
    # Account Operations
    # ------------------------------------------------------------------ #

    def register_account(self, db: Session, email: str, password: str) -> Account:
        """
        Create a new account with ACTIVE status and assigned_role = None.
        Used by legacy unit tests.
        """
        email_clean = email.strip().lower()
        existing = db.query(Account).filter(Account.email == email_clean).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email address already exists.",
            )

        account = Account(
            email=email_clean,
            password_hash=self.hash_password(password),
            account_status="ACTIVE",
            assigned_role=None,
            email_verified=True,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        logger.info(f"Registered new account: {account.email} (ID: {account.id})")
        return account

    def check_email(self, db: Session, email: str) -> tuple[bool, bool, str]:
        """
        Validates email address syntax and domain deliverability, and checks DB existence.
        Returns: (exists: bool, deliverable: bool, detail: str)
        """
        from app.utils.email_validator import validate_email_address

        valid, err_msg = validate_email_address(email)
        if not valid:
            return False, False, err_msg

        email_clean = email.strip().lower()
        existing = db.query(Account).filter(Account.email == email_clean).first()
        if existing:
            return True, True, "Account exists. Please enter your password."
        return False, True, "Email address is valid and available for registration."

    def onboard_account(self, db: Session, email: str, password: str) -> tuple[Account, str]:
        """
        Smart onboarding:
        1. Validates email deliverability & domain.
        2. Enforces password security policy.
        3. Generates 6-digit OTP code and creates account.
        Returns: (account: Account, otp_code: str)
        """
        from app.utils.email_validator import validate_email_address
        from app.utils.password_validator import validate_password_strength

        email_clean = email.strip().lower()

        # Validate Email
        valid_email, email_err = validate_email_address(email_clean)
        if not valid_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=email_err,
            )

        # Check existing account
        existing = db.query(Account).filter(Account.email == email_clean).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email address already exists. Please sign in.",
            )

        # Validate Password Strength
        valid_pwd, pwd_errs = validate_password_strength(password, email_clean)
        if not valid_pwd:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password policy failed: " + "; ".join(pwd_errs),
            )

        # Generate 6-digit OTP
        otp_code = f"{secrets.randbelow(900000) + 100000}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        account = Account(
            email=email_clean,
            password_hash=self.hash_password(password),
            account_status="ACTIVE",
            assigned_role=None,
            email_verified=False,
            verification_code=otp_code,
            verification_code_expires_at=expires_at,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        logger.info(f"Onboarded account (OTP generated): {account.email} (ID: {account.id})")
        return account, otp_code

    def verify_email_otp(self, db: Session, email: str, code: str) -> Account:
        """
        Verifies 6-digit OTP code and marks account as email_verified = True.
        """
        email_clean = email.strip().lower()
        account = db.query(Account).filter(Account.email == email_clean).first()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account found with this email address.",
            )

        if account.email_verified:
            return account

        if not account.verification_code or account.verification_code != code.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code. Please check your code and try again.",
            )

        if account.verification_code_expires_at:
            now = datetime.now(timezone.utc)
            exp = account.verification_code_expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if now > exp:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Verification code has expired. Please request a new verification code.",
                )

        account.email_verified = True
        account.verification_code = None
        account.verification_code_expires_at = None
        db.commit()
        db.refresh(account)
        logger.info(f"Email verified via OTP for account: {account.email}")
        return account

    def authenticate_account(self, db: Session, email: str, password: str) -> Account:
        """
        Authenticate email + password credentials.

        Checks:
        1. Account exists and password matches -> 401 Unauthorized if invalid.
        2. Account status is ACTIVE -> 403 Forbidden if INACTIVE.

        Updates last_login_at on success.
        """
        email_clean = email.strip().lower()
        account = db.query(Account).filter(Account.email == email_clean).first()

        if not account or not self.verify_password(password, account.password_hash):
            logger.warning(f"Failed authentication attempt for email: {email_clean}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email address or password.",
            )

        if account.account_status != "ACTIVE":
            logger.warning(f"Authentication attempt on INACTIVE account: {email_clean}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Please contact your system administrator.",
            )

        account.last_login_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(account)
        return account

    def get_account_by_id(self, db: Session, account_id: UUID) -> Optional[Account]:
        """Fetch account by primary key."""
        return db.query(Account).filter(Account.id == account_id).first()

    # ------------------------------------------------------------------ #
    # Session Management (Server-Managed Sessions with HttpOnly Cookies)
    # ------------------------------------------------------------------ #

    def create_session(
        self, db: Session, account_id: UUID, duration_hours: int = DEFAULT_SESSION_DURATION_HOURS
    ) -> UserSession:
        """
        Generate a secure 256-bit session token and store in PostgreSQL.
        """
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)

        session = UserSession(
            session_token=session_token,
            account_id=account_id,
            expires_at=expires_at,
            is_active=True,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        logger.debug(f"Created session {session.id} for account {account_id}")
        return session

    def get_session_and_account(
        self, db: Session, session_token: str
    ) -> Tuple[Optional[UserSession], Optional[Account]]:
        """
        Validate an incoming session token.

        Returns (session, account) if valid and active, or (None, None) if invalid/expired/inactive.
        """
        if not session_token:
            return None, None

        session = (
            db.query(UserSession)
            .filter(
                UserSession.session_token == session_token,
                UserSession.is_active == True,  # noqa: E712
            )
            .first()
        )

        if not session:
            return None, None

        # Check expiration
        now = datetime.now(timezone.utc)
        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < now:
            logger.info(f"Session {session.id} expired at {session.expires_at}")
            session.is_active = False
            db.commit()
            return None, None


        account = self.get_account_by_id(db, session.account_id)
        if not account or account.account_status != "ACTIVE":
            logger.warning(f"Session {session.id} belongs to missing or INACTIVE account.")
            return None, None

        return session, account

    def logout_session(self, db: Session, session_token: str) -> bool:
        """Invalidate a specific session on logout."""
        if not session_token:
            return False

        session = (
            db.query(UserSession)
            .filter(UserSession.session_token == session_token)
            .first()
        )
        if session:
            session.is_active = False
            db.commit()
            logger.info(f"Session {session.id} logged out.")
            return True
        return False

    # ------------------------------------------------------------------ #
    # Permanent Role Binding (Role Immutability)
    # ------------------------------------------------------------------ #

    def assign_role(self, db: Session, account: Account, role: str) -> Account:
        """
        One-time role assignment worker.

        Rules:
        1. Account must be ACTIVE.
        2. assigned_role MUST currently be None.
        3. If assigned_role is already set -> HTTP 400 Bad Request. Rejection enforced server-side.
        4. Role must be one of the 5 allowed roles.
        5. Atomic database-level row lock (with_for_update) prevents concurrent assignment races.
        """
        # Fetch with row lock to guarantee atomic execution under concurrency
        db_account = (
            db.query(Account)
            .filter(Account.id == account.id)
            .with_for_update(of=Account)
            .first()
        )
        if not db_account:
            db_account = account

        if db_account.account_status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot assign role to an inactive account.",
            )

        if db_account.assigned_role is not None:
            logger.warning(
                f"Attempted role reassignment on account {db_account.id} "
                f"(current role: '{db_account.assigned_role}', requested: '{role}'). Rejected."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Account already has assigned role '{db_account.assigned_role}'. "
                    "Role assignment is permanent and cannot be modified."
                ),
            )

        role_clean = role.strip().upper()
        if role_clean not in SUPPORTED_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role '{role}'. Supported roles: {sorted(SUPPORTED_ROLES)}",
            )

        db_account.assigned_role = role_clean
        db.commit()
        db.refresh(db_account)
        logger.info(f"Permanently bound role '{role_clean}' to account {db_account.id}")
        return db_account


    # ------------------------------------------------------------------ #
    # Account Deactivation
    # ------------------------------------------------------------------ #

    def deactivate_account(self, db: Session, account: Account) -> Account:
        """
        Deactivate an account.

        Behavior:
        - Marks status as 'INACTIVE'.
        - Invalidates all active user sessions for this account.
        - Preserves account row, history, comments, and audit logs.
        - Account can no longer authenticate or make API calls.
        """
        account.account_status = "INACTIVE"

        # Invalidate all open sessions
        db.query(UserSession).filter(
            UserSession.account_id == account.id,
            UserSession.is_active == True,  # noqa: E712
        ).update({"is_active": False})

        db.commit()
        db.refresh(account)
        logger.info(f"Account {account.id} ({account.email}) deactivated. Historical data preserved.")
        return account


# Singleton instance
auth_service = AuthService()
