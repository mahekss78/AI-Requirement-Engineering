"""
app/api/auth_router.py
======================
FastAPI authentication and session management router.

Endpoints:
- POST /api/auth/register        — Register a new user account
- POST /api/auth/login           — Authenticate user, establish session, set HttpOnly cookie
- POST /api/auth/logout          — Revoke session, clear HttpOnly cookie
- GET  /api/auth/session         — Query current session status, account status, and assigned role
- POST /api/auth/role            — One-time permanent role assignment (immutable once set)
- POST /api/auth/deactivate      — Freeze account (sets status to INACTIVE, invalidates sessions)
- POST /api/auth/forgot-password — Password reset request stub
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_account,
    get_current_session_and_account,
    get_db,
    get_session_token,
)
from app.models.models import Account
from app.schemas.schemas import (
    EmailCheckRequest,
    EmailCheckResponse,
    ForgotPasswordRequest,
    OKResponse,
    OnboardRequest,
    OnboardResponse,
    RoleAssignmentRequest,
    SessionResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.auth import SESSION_COOKIE_NAME, auth_service

router = APIRouter(prefix="/auth", tags=["Authentication & Session"])


@router.post(
    "/check-email",
    response_model=EmailCheckResponse,
    summary="Validate email address syntax, deliverability, and account existence",
)
def check_email_endpoint(
    payload: EmailCheckRequest,
    db: Session = Depends(get_db),
) -> EmailCheckResponse:
    """
    Checks email deliverability, disposable domain blocklist, and whether an account already exists.
    """
    exists, deliverable, detail = auth_service.check_email(db, payload.email)
    return EmailCheckResponse(exists=exists, deliverable=deliverable, detail=detail)


@router.post(
    "/onboard",
    response_model=OnboardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard a new user with strong password and OTP verification code",
)
def onboard_endpoint(
    payload: OnboardRequest,
    db: Session = Depends(get_db),
) -> OnboardResponse:
    """
    Onboards a new user:
    1. Validates email deliverability.
    2. Enforces password security policy.
    3. Generates 6-digit OTP code and stores unverified account.
    """
    account, otp_code = auth_service.onboard_account(db, payload.email, payload.password)
    return OnboardResponse(
        status="verification_required",
        message="A 6-digit verification code has been generated. Please enter the code to verify your email.",
        email=account.email,
        dev_otp=otp_code,
    )


@router.post(
    "/verify-email",
    response_model=SessionResponse,
    summary="Verify email ownership via 6-digit OTP code",
)
def verify_email_endpoint(
    payload: VerifyEmailRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    """
    Verifies 6-digit OTP code, marks email_verified = True, establishes session, and sets HttpOnly cookie.
    """
    account = auth_service.verify_email_otp(db, payload.email, payload.code)
    user_session = auth_service.create_session(db, account.id)

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=user_session.session_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=86400,
    )

    return SessionResponse(
        authenticated=True,
        user=UserResponse.model_validate(account),
        account_status=account.account_status,
        assigned_role=account.assigned_role,
    )


@router.post(
    "/register",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(
    payload: UserRegister,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    """
    Registers a new user account with ACTIVE status and assigned_role = None.
    Creates a new session and sets the HttpOnly session cookie.
    """
    account = auth_service.register_account(db, payload.email, payload.password)
    user_session = auth_service.create_session(db, account.id)

    # Set HttpOnly Cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=user_session.session_token,
        httponly=True,
        samesite="lax",
        secure=False,  # In production, set to True for HTTPS
        max_age=86400,
    )

    return SessionResponse(
        authenticated=True,
        user=UserResponse.model_validate(account),
        account_status=account.account_status,
        assigned_role=account.assigned_role,
    )


@router.post(
    "/login",
    response_model=SessionResponse,
    summary="Sign in to user account",
)
def login(
    payload: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    """
    Verifies user credentials, checks account status (ACTIVE required),
    establishes a server-managed session, and sets an HttpOnly cookie.

    Flow:
    - If account INACTIVE -> 403 Forbidden ("Account is inactive")
    - If credentials invalid -> 401 Unauthorized
    - If valid & assigned_role is set -> Returns role
    - If valid & assigned_role is null -> Returns assigned_role: null (Frontend shows role selector)
    """
    account = auth_service.authenticate_account(db, payload.email, payload.password)
    user_session = auth_service.create_session(db, account.id)

    # Set HttpOnly Cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=user_session.session_token,
        httponly=True,
        samesite="lax",
        secure=False,  # In production, set to True for HTTPS
        max_age=86400,
    )

    return SessionResponse(
        authenticated=True,
        user=UserResponse.model_validate(account),
        account_status=account.account_status,
        assigned_role=account.assigned_role,
    )


@router.get(
    "/session",
    response_model=SessionResponse,
    summary="Get current session and role state",
)
def get_session(
    request: Request,
    db: Session = Depends(get_db),
) -> SessionResponse:
    """
    Used by the frontend on application boot or page refresh to inspect auth state.

    Returns:
    - authenticated: True/False
    - user: { id, email }
    - account_status: ACTIVE / INACTIVE
    - assigned_role: string or null
    """
    _, account = get_current_session_and_account(request, db)

    if not account or account.account_status != "ACTIVE":
        return SessionResponse(
            authenticated=False,
            user=None,
            account_status=account.account_status if account else None,
            assigned_role=None,
        )

    return SessionResponse(
        authenticated=True,
        user=UserResponse.model_validate(account),
        account_status=account.account_status,
        assigned_role=account.assigned_role,
    )


@router.post(
    "/role",
    response_model=SessionResponse,
    summary="One-time permanent role binding",
)
def assign_role(
    payload: RoleAssignmentRequest,
    current_account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
) -> SessionResponse:
    """
    One-time role assignment endpoint.

    Rules:
    - Must be authenticated with an ACTIVE account.
    - If assigned_role is currently NULL -> Binds the role permanently.
    - If assigned_role is ALREADY SET -> Rejects with 400 Bad Request.
    - Role switching is strictly prohibited server-side.
    """
    updated_account = auth_service.assign_role(db, current_account, payload.role)

    return SessionResponse(
        authenticated=True,
        user=UserResponse.model_validate(updated_account),
        account_status=updated_account.account_status,
        assigned_role=updated_account.assigned_role,
    )


@router.post(
    "/logout",
    response_model=OKResponse,
    summary="Sign out and revoke session",
)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> OKResponse:
    """
    Revokes the current session token in PostgreSQL and clears the HttpOnly cookie.
    """
    token = get_session_token(request)
    if token:
        auth_service.logout_session(db, token)

    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return OKResponse(status="ok", message="Signed out successfully.")


@router.post(
    "/deactivate",
    response_model=OKResponse,
    summary="Deactivate user account (preserves historical data)",
)
def deactivate_account(
    response: Response,
    current_account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
) -> OKResponse:
    """
    Deactivates the current user's account.

    Behavior:
    - Sets account_status = 'INACTIVE'.
    - Invalidates all active user sessions for this account.
    - Clears session cookie.
    - Account data, audit logs, comments, and requirements history remain intact.
    - Account cannot authenticate or execute API actions going forward.
    """
    auth_service.deactivate_account(db, current_account)
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return OKResponse(
        status="ok",
        message="Account deactivated successfully. Historical audit records preserved.",
    )


@router.post(
    "/forgot-password",
    response_model=OKResponse,
    summary="Password reset request interface stub",
)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> OKResponse:
    """
    Interface stub for forgot-password workflow.
    Validates payload format and returns acknowledgement without raising errors.
    """
    return OKResponse(
        status="ok",
        message=f"If an active account exists for '{payload.email}', password reset instructions have been dispatched.",
    )


# ================================================================== #
# OAuth 2.0 Provider Endpoints (Google)
# ================================================================== #

from fastapi.responses import RedirectResponse
from app.services.oauth_service import OAUTH_STATE_COOKIE_NAME, oauth_service


@router.get(
    "/oauth/google/authorize",
    summary="Initiate Google OAuth 2.0 authorization",
)
def google_authorize(
    db: Session = Depends(get_db),
):
    """
    Generates OAuthState, sets area_oauth_state transaction cookie,
    and redirects user to Google's OAuth consent screen.
    """
    state_token, cookie_secret = oauth_service.create_oauth_state(db, "google")
    authorize_url = oauth_service.get_google_authorize_url(state_token)

    res = RedirectResponse(url=authorize_url, status_code=status.HTTP_302_FOUND)
    res.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=cookie_secret,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in production HTTPS
        path="/api/auth/oauth",
        max_age=600,  # 10 minutes
    )
    return res


@router.get(
    "/oauth/google/callback",
    summary="Google OAuth 2.0 authorization callback",
)
def google_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Validates Google authorization code and state token, fetches user profile,
    links/creates account, sets area_session cookie, and redirects user to frontend.
    """
    if error:
        logger.warning(f"Google OAuth authorization error returned by provider: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth authorization rejected: {error}",
        )

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'code' or 'state' parameter in OAuth callback.",
        )

    raw_cookie_secret = request.cookies.get(OAUTH_STATE_COOKIE_NAME)

    account, user_session = oauth_service.process_google_callback(
        db=db,
        code=code,
        state_token=state,
        raw_cookie_secret=raw_cookie_secret,
    )

    # Establish AREA Session via HttpOnly cookie
    redirect_res = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    redirect_res.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=user_session.session_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=86400,
    )
    # Clear short-lived transaction cookie
    redirect_res.delete_cookie(key=OAUTH_STATE_COOKIE_NAME, path="/api/auth/oauth")
    return redirect_res
