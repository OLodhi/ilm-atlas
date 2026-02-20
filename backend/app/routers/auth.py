import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.dependencies import get_current_user
from app.middleware.rate_limit import limiter
from app.models.db import (
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    User,
)
from app.models.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UsageResponse,
    UserResponse,
    UserUpdateRequest,
    VerifyEmailRequest,
)
from app.services.auth.common_passwords import is_common_password
from app.services.auth.usage import get_usage
from app.services.auth.email import send_password_reset_email, send_verification_email
from app.services.auth.password import hash_password, verify_password
from app.services.auth.tokens import (
    create_access_token,
    generate_refresh_token,
    generate_verification_token,
    hash_token,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"


def _is_production() -> bool:
    """Check if running in production (frontend served over HTTPS)."""
    return settings.frontend_url.startswith("https")


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    """Set the refresh token as an httpOnly secure cookie."""
    is_prod = _is_production()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=is_prod,
        samesite="strict" if is_prod else "lax",
        path="/auth",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
    )


def _delete_refresh_cookie(response: Response) -> None:
    """Delete the refresh token cookie."""
    is_prod = _is_production()
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=is_prod,
        samesite="strict" if is_prod else "lax",
        path="/auth",
    )


# ---------------------------------------------------------------------------
# 1. POST /auth/register
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("3/hour")
async def register(
    request: Request,
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """Register a new user account."""
    # Check for common password
    if is_common_password(body.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password is too common. Please choose a stronger password.",
        )

    # Check if email is already taken
    existing = await session.execute(
        select(User).where(User.email == body.email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Create user
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        email_verified=False,
    )
    session.add(user)
    await session.flush()  # Populate user.id

    # Generate verification token
    raw_token, token_hash = generate_verification_token()
    verification = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.email_verification_expire_hours),
    )
    session.add(verification)
    await session.commit()
    await session.refresh(user)

    # Send verification email (fire-and-forget, don't block registration)
    await send_verification_email(user.email, raw_token, user.display_name)

    logger.info("New user registered: %s", user.email[:3] + "***")
    return user


# ---------------------------------------------------------------------------
# 2. POST /auth/login
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
@limiter.limit("20/minute")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate user and return access + refresh tokens."""
    # Find user by email
    result = await session.execute(
        select(User).where(User.email == body.email)
    )
    user = result.scalar_one_or_none()

    # Check if account is locked
    if user and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        remaining = int((user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Account temporarily locked. Try again in {remaining} minute(s).",
        )

    # Verify password (constant-time even if user not found)
    if user is None or not verify_password(body.password, user.password_hash):
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Check account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Please contact support.",
        )

    # Reset failed login attempts on successful login
    user.failed_login_attempts = 0
    user.locked_until = None

    # Create access token
    access_token = create_access_token(str(user.id), user.role)

    # Create refresh token
    raw_refresh, refresh_hash = generate_refresh_token()
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(refresh_record)
    await session.commit()

    # Set refresh token cookie
    _set_refresh_cookie(response, raw_refresh)

    logger.info("User logged in: %s", user.email[:3] + "***")
    return TokenResponse(access_token=access_token)


# ---------------------------------------------------------------------------
# 3. POST /auth/refresh
# ---------------------------------------------------------------------------


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """Refresh the access token using the refresh token cookie (with rotation)."""
    # Read refresh token from cookie
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    # Hash and find in DB
    token_hash = hash_token(raw_token)
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    token_record = result.scalar_one_or_none()

    if token_record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Check expiry
    if token_record.expires_at < datetime.now(timezone.utc):
        # Revoke the expired token
        token_record.revoked_at = datetime.now(timezone.utc)
        await session.commit()
        _delete_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    # Load user and check active
    user = await session.get(User, token_record.user_id)
    if user is None or not user.is_active:
        token_record.revoked_at = datetime.now(timezone.utc)
        await session.commit()
        _delete_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Revoke old token (rotation)
    token_record.revoked_at = datetime.now(timezone.utc)

    # Issue new refresh token
    raw_new, new_hash = generate_refresh_token()
    new_refresh = RefreshToken(
        user_id=user.id,
        token_hash=new_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(new_refresh)

    # Issue new access token
    access_token = create_access_token(str(user.id), user.role)

    await session.commit()

    # Set new cookie
    _set_refresh_cookie(response, raw_new)

    return TokenResponse(access_token=access_token)


# ---------------------------------------------------------------------------
# 4. POST /auth/logout
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Revoke the refresh token and clear the cookie."""
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_token:
        token_hash = hash_token(raw_token)
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
        )
        token_record = result.scalar_one_or_none()
        if token_record is not None:
            token_record.revoked_at = datetime.now(timezone.utc)
            await session.commit()

    _delete_refresh_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# 5. POST /auth/verify-email
# ---------------------------------------------------------------------------


@router.post("/verify-email")
@limiter.limit("10/minute")
async def verify_email(
    request: Request,
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_session),
):
    """Verify a user's email address using the token sent via email."""
    token_hash = hash_token(body.token)
    result = await session.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.used_at.is_(None),
        )
    )
    token_record = result.scalar_one_or_none()

    if token_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already used verification token.",
        )

    # Check expiry
    if token_record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired. Please request a new one.",
        )

    # Mark token as used
    token_record.used_at = datetime.now(timezone.utc)

    # Mark user email as verified
    user = await session.get(User, token_record.user_id)
    if user is not None:
        user.email_verified = True

    await session.commit()

    logger.info("Email verified for user_id=%s", token_record.user_id)
    return {"message": "Email verified successfully."}


# ---------------------------------------------------------------------------
# 6. POST /auth/resend-verification
# ---------------------------------------------------------------------------


@router.post("/resend-verification")
@limiter.limit("3/hour")
async def resend_verification(
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Resend the email verification link."""
    if current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified.",
        )

    # Generate new verification token
    raw_token, token_hash = generate_verification_token()
    verification = EmailVerificationToken(
        user_id=current_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.email_verification_expire_hours),
    )
    session.add(verification)
    await session.commit()

    # Send the email
    await send_verification_email(current_user.email, raw_token, current_user.display_name)

    return {"message": "Verification email sent."}


# ---------------------------------------------------------------------------
# 7. POST /auth/forgot-password
# ---------------------------------------------------------------------------


@router.post("/forgot-password")
@limiter.limit("5/hour")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """Request a password reset link. Always returns the same response to prevent email enumeration."""
    # Always return the same message regardless of whether the email exists
    _response_message = "If an account with that email exists, a password reset link has been sent."

    result = await session.execute(
        select(User).where(User.email == body.email)
    )
    user = result.scalar_one_or_none()

    if user is not None:
        raw_token, token_hash = generate_verification_token()
        reset_record = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.password_reset_expire_hours),
        )
        session.add(reset_record)
        await session.commit()

        await send_password_reset_email(user.email, raw_token, user.display_name)

    return {"message": _response_message}


# ---------------------------------------------------------------------------
# 8. POST /auth/reset-password
# ---------------------------------------------------------------------------


@router.post("/reset-password")
@limiter.limit("10/hour")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """Reset a user's password using the token from the reset email."""
    # Check for common password
    if is_common_password(body.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password is too common. Please choose a stronger password.",
        )

    token_hash = hash_token(body.token)
    result = await session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
        )
    )
    token_record = result.scalar_one_or_none()

    if token_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already used reset token.",
        )

    # Check expiry
    if token_record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired. Please request a new one.",
        )

    # Mark token as used
    token_record.used_at = datetime.now(timezone.utc)

    # Update user password
    user = await session.get(User, token_record.user_id)
    if user is not None:
        user.password_hash = hash_password(body.new_password)

    await session.commit()

    logger.info("Password reset for user_id=%s", token_record.user_id)
    return {"message": "Password has been reset successfully."}


# ---------------------------------------------------------------------------
# 9. GET /auth/me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Return the current authenticated user's profile."""
    return current_user


# ---------------------------------------------------------------------------
# 10. PATCH /auth/me
# ---------------------------------------------------------------------------


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update the current user's profile (display name, password)."""
    # Update display_name if provided
    if body.display_name is not None:
        current_user.display_name = body.display_name

    # Update password if new_password provided
    if body.new_password is not None:
        # Require current_password
        if body.current_password is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is required to set a new password.",
            )

        # Verify current password
        if not verify_password(body.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )

        # Check not common
        if is_common_password(body.new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This password is too common. Please choose a stronger password.",
            )

        current_user.password_hash = hash_password(body.new_password)

    await session.commit()
    await session.refresh(current_user)

    return current_user


# ---------------------------------------------------------------------------
# 11. GET /auth/usage
# ---------------------------------------------------------------------------


@router.get("/usage", response_model=UsageResponse)
async def get_my_usage(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get current user's daily usage."""
    used, limit = await get_usage(current_user, session)
    today = datetime.now(timezone.utc).date().isoformat()
    return UsageResponse(used=used, limit=limit, date=today)


# ---------------------------------------------------------------------------
# 12. DELETE /auth/me
# ---------------------------------------------------------------------------


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Soft-delete the current user's account."""
    current_user.is_active = False
    current_user.email = f"deleted-{current_user.id}@deleted.invalid"
    current_user.display_name = None
    current_user.password_hash = "DELETED"

    # Revoke all refresh tokens
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    for token in result.scalars():
        token.revoked_at = datetime.now(timezone.utc)

    await session.commit()
    _delete_refresh_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
