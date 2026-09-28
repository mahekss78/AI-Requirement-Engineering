"""
app/api/dependencies.py
========================
FastAPI Dependency Injection providers for the AREA platform.

Responsibilities:
- Database session lifecycle management.
- Authentication dependency (`get_current_account` reading from HttpOnly cookie or Authorization header).
- Account status verification (`require_active_account`).
- Role-based access control enforcement (`require_role(...)`).
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.models import Account, UserSession
from app.services.auth import SESSION_COOKIE_NAME, auth_service


def get_session_token(request: Request) -> Optional[str]:
    """
    Extract session token from:
    1. HttpOnly cookie (`area_session`)
    2. Fallback: Authorization header `Bearer <token>`
    """
    # 1. Check Cookie
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        return token

    # 2. Check Authorization Header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()

    return None


def get_current_session_and_account(
    request: Request,
    db: Session = Depends(get_db),
) -> Tuple[Optional[UserSession], Optional[Account]]:
    """
    Optional authentication inspector.
    Returns (session, account) if authenticated and active, or (None, None) if not.
    Does not raise exceptions on missing tokens.
    """
    token = get_session_token(request)
    if not token:
        return None, None
    return auth_service.get_session_and_account(db, token)


def get_current_account(
    request: Request,
    db: Session = Depends(get_db),
) -> Account:
    """
    Required authentication dependency.
    Raises HTTP 401 if missing/invalid session token.
    Raises HTTP 403 if account is INACTIVE.
    """
    token = get_session_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
        )

    session, account = auth_service.get_session_and_account(db, token)
    if not session or not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please sign in again.",
        )

    if account.account_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Access denied.",
        )

    return account


def require_role(*allowed_roles: str) -> Callable:
    """
    Role-based authorization dependency factory.

    Usage:
        @router.post("/requirements", dependencies=[Depends(require_role("BUSINESS_ANALYST"))])
        def create_requirement(...):

    Enforces server-side role validation.
    """

    def role_checker(account: Account = Depends(get_current_account)) -> Account:
        if account.assigned_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role has not been assigned to this account yet. Please complete role selection first.",
            )

        if account.assigned_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{account.assigned_role}' is not authorized to perform this operation. "
                    f"Required role(s): {list(allowed_roles)}"
                ),
            )

        return account

    return role_checker
