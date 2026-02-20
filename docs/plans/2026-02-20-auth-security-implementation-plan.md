# Auth, Security & Public Launch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add user authentication, security hardening, and public launch readiness to Ilm Atlas.

**Architecture:** Custom email+password auth built into FastAPI with JWT access/refresh tokens, bcrypt password hashing, Resend for email delivery. Security hardening via CORS lockdown, rate limiting (slowapi), input validation, and security headers. Frontend auth via React context with automatic token refresh.

**Tech Stack:** FastAPI, SQLAlchemy, python-jose[cryptography], passlib[bcrypt], slowapi, resend, Next.js 14, TypeScript

**Design doc:** `docs/plans/2026-02-20-auth-security-public-launch-design.md`

---

## Phase 1: Security Hardening

### Task 1: Install security dependencies

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add dependencies**

Add to `backend/requirements.txt`:
```
# Security
slowapi>=0.1.9
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4

# Email
resend>=2.0.0
```

**Step 2: Install**

Run: `cd backend && pip install -r requirements.txt`

**Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "feat: add security and auth dependencies"
```

---

### Task 2: CORS lockdown + security headers middleware

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`
- Create: `backend/app/middleware/__init__.py`
- Create: `backend/app/middleware/security_headers.py`

**Step 1: Add CORS and frontend URL settings**

In `backend/app/config.py`, add to `Settings`:
```python
    # Frontend URL (for CORS)
    frontend_url: str = "http://localhost:3000"
```

**Step 2: Create security headers middleware**

Create `backend/app/middleware/__init__.py` (empty).

Create `backend/app/middleware/security_headers.py`:
```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
```

**Step 3: Update main.py CORS config**

In `backend/app/main.py`, replace the CORS middleware block:
```python
from app.config import settings
from app.middleware.security_headers import SecurityHeadersMiddleware

# ... after app = FastAPI(...)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
```

Note: `SecurityHeadersMiddleware` is added BEFORE `CORSMiddleware` because middleware executes in reverse order (last added = first executed). CORS must run first (outermost) to handle preflight.

**Step 4: Test manually**

Run: `cd backend && uvicorn app.main:app --reload`
Then: `curl -I http://localhost:8000/health`
Expected: Headers include `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, etc.

**Step 5: Commit**

```bash
git add backend/app/config.py backend/app/main.py backend/app/middleware/
git commit -m "feat: add CORS lockdown and security headers middleware"
```

---

### Task 3: Input validation on existing schemas

**Files:**
- Modify: `backend/app/models/schemas.py`

**Step 1: Add length constraints to all string fields**

Update `ChatSendRequest`:
```python
from pydantic import BaseModel, Field

class ChatSendRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    madhab: str | None = None
    category: str | None = None
```

Update `QueryRequest`:
```python
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    madhab: str | None = None
    category: str | None = None
    top_k: int = Field(default=10, ge=1, le=50)
```

Update `ChatSessionRenameRequest`:
```python
class ChatSessionRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
```

Update `BookCreate` / `UploadRequest`:
```python
class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    author: str = Field(default="", max_length=300)
    language: str = Field(default="both", pattern="^(arabic|english|both)$")
    madhab: str = Field(default="general", pattern="^(hanafi|shafii|maliki|hanbali|general)$")
    category: str = Field(default="general", pattern="^(quran|hadith|fiqh|aqeedah|seerah|tafsir|general)$")
```

**Step 2: Test that validation rejects invalid input**

Run server: `cd backend && uvicorn app.main:app --reload`
Test: `curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{"question": ""}'`
Expected: 422 Unprocessable Entity with validation error

**Step 3: Commit**

```bash
git add backend/app/models/schemas.py
git commit -m "feat: add input validation constraints to all Pydantic schemas"
```

---

### Task 4: Rate limiting with slowapi

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/app/middleware/rate_limit.py`
- Modify: `backend/app/routers/chat.py`
- Modify: `backend/app/routers/query.py`
- Modify: `backend/app/routers/admin.py`

**Step 1: Create rate limiter setup**

Create `backend/app/middleware/rate_limit.py`:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

**Step 2: Register limiter in main.py**

In `backend/app/main.py`, add after app creation:
```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.middleware.rate_limit import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

**Step 3: Add rate limits to endpoints**

In `backend/app/routers/chat.py`, add to message endpoints:
```python
from app.middleware.rate_limit import limiter

@router.post("/sessions/{session_id}/messages")
@limiter.limit("30/minute")
async def send_message(request: Request, session_id: UUID, ...):
    ...
```

In `backend/app/routers/query.py`:
```python
@router.post("")
@limiter.limit("10/minute")
async def query(request: Request, ...):
    ...
```

In `backend/app/routers/admin.py`:
```python
@router.post("/upload")
@limiter.limit("5/minute")
async def upload_file(request: Request, ...):
    ...
```

Note: Each endpoint that uses `@limiter.limit()` must accept `request: Request` as the first parameter.

**Step 4: Test rate limiting**

Hit `/query` endpoint 11 times rapidly.
Expected: 429 Too Many Requests after 10th request.

**Step 5: Commit**

```bash
git add backend/app/middleware/rate_limit.py backend/app/main.py backend/app/routers/
git commit -m "feat: add per-IP rate limiting via slowapi"
```

---

### Task 5: File upload hardening

**Files:**
- Modify: `backend/app/routers/admin.py`
- Modify: `backend/app/services/ingestion.py`

**Step 1: Add file size limit and magic byte validation**

In `backend/app/routers/admin.py`, update `upload_file`:
```python
from fastapi import HTTPException

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

MAGIC_BYTES = {
    "pdf": b"%PDF",
    "png": b"\x89PNG",
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "tiff": (b"II\x2a\x00", b"MM\x00\x2a"),
    "bmp": b"BM",
    "webp": b"RIFF",
}

@router.post("/upload", response_model=UploadResponse)
@limiter.limit("5/minute")
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile,
    ...
):
    # Validate file type by extension
    file_type = _detect_file_type(file.filename)

    # Read content and check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 50MB.")

    # Validate magic bytes for binary files
    if file_type in MAGIC_BYTES:
        expected = MAGIC_BYTES[file_type]
        if isinstance(expected, tuple):
            if not any(content.startswith(m) for m in expected):
                raise HTTPException(status_code=400, detail="File content does not match declared type.")
        elif not content.startswith(expected):
            raise HTTPException(status_code=400, detail="File content does not match declared type.")

    # ... rest of upload logic (use `content` instead of re-reading)
```

**Step 2: Test with an invalid file**

Create a file with wrong extension: rename a text file to `.pdf` and try uploading.
Expected: 400 error "File content does not match declared type."

**Step 3: Commit**

```bash
git add backend/app/routers/admin.py
git commit -m "feat: add file size limit and magic byte validation for uploads"
```

---

## Phase 2: User Model + Auth Backend

### Task 6: Create auth models in db.py

**Files:**
- Modify: `backend/app/models/db.py`

**Step 1: Add User, RefreshToken, UsageLog, EmailVerificationToken, PasswordResetToken models**

Add to `backend/app/models/db.py`:
```python
from sqlalchemy import Boolean, Date, Integer, UniqueConstraint


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user")  # user, admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_query_limit: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    usage_logs: Mapped[list["UsageLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    device_info: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class UsageLog(Base):
    __tablename__ = "usage_logs"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_usage_user_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    date: Mapped[datetime] = mapped_column(Date, nullable=False)
    query_count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="usage_logs")


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**Step 2: Add user_id FK to ChatSession**

Update `ChatSession` in `db.py`:
```python
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # nullable during migration
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User | None"] = relationship(back_populates="sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan",
        order_by="ChatMessage.created_at, ChatMessage.id",
    )
```

**Step 3: Commit**

```bash
git add backend/app/models/db.py
git commit -m "feat: add User, RefreshToken, UsageLog, and token models to DB"
```

---

### Task 7: Create Alembic migration

**Files:**
- Create: `backend/alembic/versions/<auto>_add_auth_tables.py` (auto-generated)

**Step 1: Generate migration**

Run from `backend/`:
```bash
cd backend && alembic revision --autogenerate -m "add auth tables and user_id to chat_sessions"
```

**Step 2: Review the generated migration file**

Open the generated file in `backend/alembic/versions/` and verify it creates:
- `users` table
- `refresh_tokens` table
- `usage_logs` table
- `email_verification_tokens` table
- `password_reset_tokens` table
- Adds `user_id` column to `chat_sessions`

**Step 3: Run migration**

```bash
cd backend && alembic upgrade head
```

Expected: All tables created, no errors.

**Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat: add alembic migration for auth tables"
```

---

### Task 8: Auth config settings

**Files:**
- Modify: `backend/app/config.py`

**Step 1: Add auth-related settings**

Add to `Settings` class in `backend/app/config.py`:
```python
    # Auth
    jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Email (Resend)
    resend_api_key: str = ""
    email_from: str = "noreply@ilmatlas.com"
    email_verification_expire_hours: int = 24
    password_reset_expire_hours: int = 1

    # Rate limits
    default_daily_query_limit: int = 50
    anonymous_daily_query_limit: int = 10
```

**Step 2: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add auth and email settings to config"
```

---

### Task 9: Password hashing service

**Files:**
- Create: `backend/app/services/auth/__init__.py`
- Create: `backend/app/services/auth/password.py`

**Step 1: Create password service**

Create `backend/app/services/auth/__init__.py` (empty).

Create `backend/app/services/auth/password.py`:
```python
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)
```

**Step 2: Commit**

```bash
git add backend/app/services/auth/
git commit -m "feat: add password hashing service with bcrypt"
```

---

### Task 10: JWT token service

**Files:**
- Create: `backend/app/services/auth/tokens.py`

**Step 1: Create JWT service**

Create `backend/app/services/auth/tokens.py`:
```python
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings


def create_access_token(user_id: str, role: str) -> str:
    """Create a short-lived JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises JWTError on failure."""
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload


def generate_refresh_token() -> tuple[str, str]:
    """Generate a refresh token. Returns (raw_token, token_hash)."""
    raw_token = str(uuid.uuid4())
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


def hash_token(token: str) -> str:
    """Hash a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_verification_token() -> tuple[str, str]:
    """Generate an email verification or password reset token. Returns (raw_token, token_hash)."""
    raw_token = uuid.uuid4().hex
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash
```

**Step 2: Commit**

```bash
git add backend/app/services/auth/tokens.py
git commit -m "feat: add JWT and token generation service"
```

---

### Task 11: Email service (Resend)

**Files:**
- Create: `backend/app/services/auth/email.py`

**Step 1: Create email service**

Create `backend/app/services/auth/email.py`:
```python
import logging

import resend

from app.config import settings

logger = logging.getLogger(__name__)


def _init_resend():
    if settings.resend_api_key:
        resend.api_key = settings.resend_api_key


async def send_verification_email(to_email: str, token: str, display_name: str | None = None) -> bool:
    """Send email verification link."""
    _init_resend()
    name = display_name or "there"
    verify_url = f"{settings.frontend_url}/verify-email?token={token}"

    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [to_email],
            "subject": "Verify your Ilm Atlas account",
            "html": f"""
                <h2>Assalamu Alaikum {name},</h2>
                <p>Welcome to Ilm Atlas! Please verify your email address by clicking the link below:</p>
                <p><a href="{verify_url}">Verify Email Address</a></p>
                <p>This link expires in {settings.email_verification_expire_hours} hours.</p>
                <p>If you didn't create an account, you can safely ignore this email.</p>
                <br>
                <p>Ilm Atlas Team</p>
            """,
        })
        return True
    except Exception:
        logger.exception("Failed to send verification email to %s", to_email[:3] + "***")
        return False


async def send_password_reset_email(to_email: str, token: str, display_name: str | None = None) -> bool:
    """Send password reset link."""
    _init_resend()
    name = display_name or "there"
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"

    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [to_email],
            "subject": "Reset your Ilm Atlas password",
            "html": f"""
                <h2>Assalamu Alaikum {name},</h2>
                <p>We received a request to reset your password. Click the link below:</p>
                <p><a href="{reset_url}">Reset Password</a></p>
                <p>This link expires in {settings.password_reset_expire_hours} hour(s).</p>
                <p>If you didn't request this, you can safely ignore this email.</p>
                <br>
                <p>Ilm Atlas Team</p>
            """,
        })
        return True
    except Exception:
        logger.exception("Failed to send password reset email to %s", to_email[:3] + "***")
        return False
```

**Step 2: Commit**

```bash
git add backend/app/services/auth/email.py
git commit -m "feat: add email service with Resend for verification and password reset"
```

---

### Task 12: Auth Pydantic schemas

**Files:**
- Modify: `backend/app/models/schemas.py`

**Step 1: Add auth request/response schemas**

Add to `backend/app/models/schemas.py`:
```python
import re

from pydantic import BaseModel, EmailStr, Field, field_validator


# --- Auth ---

class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=320)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str | None = Field(default=None, min_length=2, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[a-zA-Z0-9 ]+$", v):
            raise ValueError("Display name can only contain letters, numbers, and spaces")
        return v


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=320)
    password: str = Field(..., max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    email_verified: bool
    display_name: str | None
    role: str
    daily_query_limit: int
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=100)
    current_password: str | None = Field(default=None, max_length=128)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[a-zA-Z0-9 ]+$", v):
            raise ValueError("Display name can only contain letters, numbers, and spaces")
        return v


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class UsageResponse(BaseModel):
    used: int
    limit: int
    date: str
```

Note: Also add `pydantic[email]` to requirements if you want `EmailStr`, but regex validation is sufficient and avoids the extra dependency.

**Step 2: Commit**

```bash
git add backend/app/models/schemas.py
git commit -m "feat: add auth Pydantic schemas for register, login, tokens, user profile"
```

---

### Task 13: Common passwords list

**Files:**
- Create: `backend/app/services/auth/common_passwords.py`

**Step 1: Create common passwords checker**

Create `backend/app/services/auth/common_passwords.py`:
```python
"""Top 1000 common passwords for validation. Sourced from SecLists."""

# Top 100 most common (expand to 1000+ in production)
COMMON_PASSWORDS = frozenset({
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "1234567",
    "letmein", "trustno1", "dragon", "baseball", "iloveyou", "master", "sunshine",
    "ashley", "michael", "shadow", "123123", "654321", "superman", "qazwsx",
    "michael", "football", "password1", "password123", "batman", "login",
    "admin", "princess", "starwars", "hello", "charlie", "donald", "welcome",
    "jesus", "ninja", "mustang", "password1!", "1234567890", "000000",
    "access", "flower", "hottie", "loveme", "zaq1zaq1", "qwerty123",
    "passw0rd", "P@ssw0rd", "p@ssword", "1q2w3e4r", "123456789",
    "11111111", "12345", "1234", "pass", "test", "guest", "changeme",
})


def is_common_password(password: str) -> bool:
    return password.lower() in COMMON_PASSWORDS
```

**Step 2: Commit**

```bash
git add backend/app/services/auth/common_passwords.py
git commit -m "feat: add common passwords list for password validation"
```

---

### Task 14: FastAPI auth dependencies

**Files:**
- Create: `backend/app/dependencies.py`

**Step 1: Create auth dependency injection**

Create `backend/app/dependencies.py`:
```python
import logging
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.db import User
from app.services.auth.tokens import decode_access_token

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Extract and validate JWT, return the User. Raises 401 if invalid."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Like get_current_user but returns None for unauthenticated requests."""
    if credentials is None:
        return None

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        return None

    return user


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Require the current user to be an admin."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
```

**Step 2: Commit**

```bash
git add backend/app/dependencies.py
git commit -m "feat: add FastAPI auth dependencies (get_current_user, require_admin)"
```

---

### Task 15: Auth router — register + login

**Files:**
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/main.py`

**Step 1: Create auth router**

Create `backend/app/routers/auth.py`:
```python
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
    UserResponse,
    UserUpdateRequest,
    UsageResponse,
    VerifyEmailRequest,
)
from app.services.auth.common_passwords import is_common_password
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


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/hour")
async def register(
    request: Request,
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new user account."""
    # Check common passwords
    if is_common_password(body.password):
        raise HTTPException(status_code=400, detail="This password is too common. Please choose a stronger one.")

    # Check if email already exists
    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    # Create user
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        daily_query_limit=settings.default_daily_query_limit,
    )
    session.add(user)
    await session.flush()

    # Generate and store email verification token
    raw_token, token_hash = generate_verification_token()
    verification = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.email_verification_expire_hours),
    )
    session.add(verification)
    await session.commit()

    # Send verification email (non-blocking — don't fail registration if email fails)
    await send_verification_email(user.email, raw_token, user.display_name)

    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("20/minute")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate and return access + refresh tokens."""
    # Find user
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled.")

    # Create access token
    access_token = create_access_token(str(user.id), user.role)

    # Create refresh token
    raw_refresh, refresh_hash = generate_refresh_token()
    refresh = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        device_info=request.headers.get("User-Agent", "")[:500],
    )
    session.add(refresh)
    await session.commit()

    # Set refresh token as httpOnly cookie
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/auth",
    )

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """Rotate refresh token and issue new access token."""
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_token:
        raise HTTPException(status_code=401, detail="No refresh token provided.")

    token_hash = hash_token(raw_token)
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    stored_token = result.scalar_one_or_none()

    if stored_token is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token.")

    if stored_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired.")

    # Load user
    user = await session.get(User, stored_token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive.")

    # Revoke old token
    stored_token.revoked_at = datetime.now(timezone.utc)

    # Issue new refresh token (rotation)
    new_raw, new_hash = generate_refresh_token()
    new_refresh = RefreshToken(
        user_id=user.id,
        token_hash=new_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        device_info=request.headers.get("User-Agent", "")[:500],
    )
    session.add(new_refresh)

    # New access token
    access_token = create_access_token(str(user.id), user.role)

    await session.commit()

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=new_raw,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/auth",
    )

    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Revoke refresh token and clear cookie."""
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_token:
        token_hash = hash_token(raw_token)
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        stored = result.scalar_one_or_none()
        if stored:
            stored.revoked_at = datetime.now(timezone.utc)
            await session.commit()

    response.delete_cookie(REFRESH_COOKIE_NAME, path="/auth")


@router.post("/verify-email")
@limiter.limit("10/minute")
async def verify_email(
    request: Request,
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_session),
):
    """Verify a user's email address via token."""
    token_hash = hash_token(body.token)
    result = await session.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.used_at.is_(None),
        )
    )
    stored = result.scalar_one_or_none()

    if stored is None:
        raise HTTPException(status_code=400, detail="Invalid or already used verification token.")

    if stored.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification token has expired.")

    # Mark token as used
    stored.used_at = datetime.now(timezone.utc)

    # Verify user's email
    user = await session.get(User, stored.user_id)
    if user:
        user.email_verified = True

    await session.commit()
    return {"message": "Email verified successfully."}


@router.post("/resend-verification")
@limiter.limit("3/hour")
async def resend_verification(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Resend email verification link."""
    if user.email_verified:
        raise HTTPException(status_code=400, detail="Email is already verified.")

    raw_token, token_hash = generate_verification_token()
    verification = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.email_verification_expire_hours),
    )
    session.add(verification)
    await session.commit()

    await send_verification_email(user.email, raw_token, user.display_name)
    return {"message": "Verification email sent."}


@router.post("/forgot-password")
@limiter.limit("5/hour")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """Send password reset email. Always returns success to prevent email enumeration."""
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user:
        raw_token, token_hash = generate_verification_token()
        reset = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.password_reset_expire_hours),
        )
        session.add(reset)
        await session.commit()
        await send_password_reset_email(user.email, raw_token, user.display_name)

    # Always return success to prevent email enumeration
    return {"message": "If an account with that email exists, a reset link has been sent."}


@router.post("/reset-password")
@limiter.limit("10/hour")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """Reset password using a reset token."""
    if is_common_password(body.new_password):
        raise HTTPException(status_code=400, detail="This password is too common.")

    token_hash = hash_token(body.token)
    result = await session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
        )
    )
    stored = result.scalar_one_or_none()

    if stored is None:
        raise HTTPException(status_code=400, detail="Invalid or already used reset token.")

    if stored.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token has expired.")

    stored.used_at = datetime.now(timezone.utc)

    user = await session.get(User, stored.user_id)
    if user:
        user.password_hash = hash_password(body.new_password)

    await session.commit()
    return {"message": "Password reset successfully."}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get the current user's profile."""
    return user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update the current user's profile or password."""
    if body.display_name is not None:
        user.display_name = body.display_name

    if body.new_password is not None:
        if body.current_password is None:
            raise HTTPException(status_code=400, detail="Current password is required to change password.")
        if not verify_password(body.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
        if is_common_password(body.new_password):
            raise HTTPException(status_code=400, detail="New password is too common.")
        user.password_hash = hash_password(body.new_password)

    await session.commit()
    await session.refresh(user)
    return user
```

**Step 2: Register auth router in main.py**

In `backend/app/main.py`, add:
```python
from app.routers import admin, auth, chat, query

app.include_router(auth.router)
```

**Step 3: Test register and login**

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "securepass123", "display_name": "Test User"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "securepass123"}'
```

Expected: Register returns user object with 201. Login returns `{"access_token": "...", "token_type": "bearer"}`.

**Step 4: Commit**

```bash
git add backend/app/routers/auth.py backend/app/main.py
git commit -m "feat: add complete auth router (register, login, refresh, logout, verify, reset)"
```

---

### Task 16: Protect admin endpoints

**Files:**
- Modify: `backend/app/routers/admin.py`

**Step 1: Add require_admin dependency to all admin routes**

In `backend/app/routers/admin.py`, update each endpoint:
```python
from app.dependencies import require_admin
from app.models.db import Book, Source, User

@router.post("/upload", response_model=UploadResponse)
@limiter.limit("5/minute")
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile,
    title: str = Form(...),
    author: str = Form(""),
    language: str = Form("both"),
    madhab: str = Form("general"),
    category: str = Form("general"),
    chunk_type: str = Form("paragraph"),
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    ...

@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    ...

@router.get("/books", response_model=list[BookResponse])
async def list_books(
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    ...
```

**Step 2: Test that admin endpoints require auth**

```bash
curl http://localhost:8000/admin/books
```
Expected: 401 Unauthorized

**Step 3: Commit**

```bash
git add backend/app/routers/admin.py
git commit -m "feat: protect admin endpoints with require_admin dependency"
```

---

## Phase 3: User-Scoped Data

### Task 17: Scope chat endpoints to authenticated user

**Files:**
- Modify: `backend/app/routers/chat.py`

**Step 1: Add get_current_user to all chat endpoints and filter by user_id**

In `backend/app/routers/chat.py`, update each endpoint:

For `create_session`:
```python
from app.dependencies import get_current_user
from app.models.db import ChatMessage, ChatSession, User

@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chat_session = ChatSession(user_id=user.id)
    session.add(chat_session)
    await session.commit()
    await session.refresh(chat_session)
    return chat_session
```

For `list_sessions` — filter by user_id:
```python
@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()
    return ChatSessionListResponse(sessions=sessions)
```

For `get_session_detail`, `send_message`, `stream_message`, `rename_session`, `delete_session` — add ownership check:
```python
async def _get_user_session(session_id: UUID, user: User, db: AsyncSession) -> ChatSession:
    """Fetch a chat session and verify ownership."""
    chat_session = await db.get(ChatSession, session_id)
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if chat_session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")  # 404 not 403 to prevent enumeration
    return chat_session
```

Use this helper in all session-specific endpoints.

**Step 2: Test that sessions are user-scoped**

Register two users, create a session with user A, try to access it with user B's token.
Expected: 404 Not Found.

**Step 3: Commit**

```bash
git add backend/app/routers/chat.py
git commit -m "feat: scope all chat endpoints to authenticated user"
```

---

### Task 18: Per-user daily usage tracking

**Files:**
- Create: `backend/app/services/auth/usage.py`
- Modify: `backend/app/routers/chat.py`

**Step 1: Create usage tracking service**

Create `backend/app/services/auth/usage.py`:
```python
from datetime import date, timezone, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import UsageLog, User


async def check_and_increment_usage(user: User, db: AsyncSession) -> tuple[bool, int, int]:
    """
    Check if user has remaining queries today and increment if allowed.
    Returns (allowed, used_count, daily_limit).
    """
    today = datetime.now(timezone.utc).date()

    result = await db.execute(
        select(UsageLog).where(
            UsageLog.user_id == user.id,
            UsageLog.date == today,
        )
    )
    usage = result.scalar_one_or_none()

    if usage is None:
        usage = UsageLog(user_id=user.id, date=today, query_count=0)
        db.add(usage)
        await db.flush()

    if usage.query_count >= user.daily_query_limit:
        return False, usage.query_count, user.daily_query_limit

    usage.query_count += 1
    await db.flush()
    return True, usage.query_count, user.daily_query_limit


async def get_usage(user: User, db: AsyncSession) -> tuple[int, int]:
    """Get current usage count and limit."""
    today = datetime.now(timezone.utc).date()

    result = await db.execute(
        select(UsageLog).where(
            UsageLog.user_id == user.id,
            UsageLog.date == today,
        )
    )
    usage = result.scalar_one_or_none()
    used = usage.query_count if usage else 0
    return used, user.daily_query_limit
```

**Step 2: Add usage check to chat message endpoints**

In `backend/app/routers/chat.py`, before processing the message in `send_message` and `stream_message`:
```python
from app.services.auth.usage import check_and_increment_usage

# Inside the endpoint, after getting user and session:
allowed, used, limit = await check_and_increment_usage(user, session)
if not allowed:
    raise HTTPException(
        status_code=429,
        detail=f"Daily query limit reached ({limit}/{limit}). Resets at midnight UTC."
    )
```

**Step 3: Add usage endpoint to auth router**

In `backend/app/routers/auth.py`:
```python
from app.services.auth.usage import get_usage

@router.get("/usage", response_model=UsageResponse)
async def get_my_usage(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get current user's daily usage."""
    used, limit = await get_usage(user, session)
    today = datetime.now(timezone.utc).date().isoformat()
    return UsageResponse(used=used, limit=limit, date=today)
```

**Step 4: Commit**

```bash
git add backend/app/services/auth/usage.py backend/app/routers/chat.py backend/app/routers/auth.py
git commit -m "feat: add per-user daily usage tracking and enforcement"
```

---

### Task 19: Anonymous query with IP-based limits

**Files:**
- Modify: `backend/app/routers/query.py`

**Step 1: Update query endpoint with optional auth and IP limits**

The `/query` endpoint stays open for anonymous users but with stricter rate limits. Authenticated users get their per-user limit.

In `backend/app/routers/query.py`:
```python
from app.dependencies import get_optional_user
from app.models.db import User

@router.post("")
@limiter.limit("10/day")  # IP-based limit for anonymous
async def query(
    request: Request,
    body: QueryRequest,
    user: User | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    # If authenticated, also check per-user limits
    if user:
        allowed, used, limit = await check_and_increment_usage(user, session)
        if not allowed:
            raise HTTPException(status_code=429, detail="Daily query limit reached.")
    ...
```

**Step 2: Commit**

```bash
git add backend/app/routers/query.py
git commit -m "feat: add optional auth and IP-based rate limiting to query endpoint"
```

---

## Phase 4: Frontend Auth

### Task 20: Auth API client functions

**Files:**
- Modify: `frontend/src/lib/api-client.ts`

**Step 1: Add auth functions to api-client.ts**

Add to `frontend/src/lib/api-client.ts`:
```typescript
// --- Auth ---

export interface RegisterData {
  email: string;
  password: string;
  display_name?: string;
}

export interface LoginData {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserProfile {
  id: string;
  email: string;
  email_verified: boolean;
  display_name: string | null;
  role: string;
  daily_query_limit: number;
  created_at: string;
}

export interface UsageInfo {
  used: number;
  limit: number;
  date: string;
}

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

async function authFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...((options.headers as Record<string, string>) || {}),
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }
  return apiFetch<T>(path, { ...options, headers, credentials: "include" });
}

export async function register(data: RegisterData): Promise<UserProfile> {
  return apiFetch<UserProfile>("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function login(data: LoginData): Promise<TokenResponse> {
  const response = await apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    credentials: "include",
  });
  setAccessToken(response.access_token);
  return response;
}

export async function refreshToken(): Promise<TokenResponse> {
  const response = await apiFetch<TokenResponse>("/auth/refresh", {
    method: "POST",
    credentials: "include",
  });
  setAccessToken(response.access_token);
  return response;
}

export async function logout(): Promise<void> {
  await authFetch("/auth/logout", { method: "POST" });
  setAccessToken(null);
}

export async function getMe(): Promise<UserProfile> {
  return authFetch<UserProfile>("/auth/me");
}

export async function updateMe(data: { display_name?: string; current_password?: string; new_password?: string }): Promise<UserProfile> {
  return authFetch<UserProfile>("/auth/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function getUsage(): Promise<UsageInfo> {
  return authFetch<UsageInfo>("/auth/usage");
}

export async function verifyEmail(token: string): Promise<{ message: string }> {
  return apiFetch("/auth/verify-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}

export async function forgotPassword(email: string): Promise<{ message: string }> {
  return apiFetch("/auth/forgot-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(token: string, new_password: string): Promise<{ message: string }> {
  return apiFetch("/auth/reset-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password }),
  });
}
```

Also update the existing `apiFetch` to pass `credentials: "include"` by default, and update all existing API calls (chat, query) to use `authFetch` instead of `apiFetch` so they include the Authorization header.

**Step 2: Commit**

```bash
git add frontend/src/lib/api-client.ts
git commit -m "feat: add auth API client functions (register, login, refresh, etc.)"
```

---

### Task 21: AuthProvider context

**Files:**
- Create: `frontend/src/contexts/auth-context.tsx`
- Modify: `frontend/src/app/layout.tsx`

**Step 1: Create AuthProvider**

Create `frontend/src/contexts/auth-context.tsx`:
```tsx
"use client";

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from "react";
import { getMe, login as apiLogin, logout as apiLogout, refreshToken, setAccessToken, type LoginData, type UserProfile } from "@/lib/api-client";

interface AuthContextType {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: LoginData) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const profile = await getMe();
      setUser(profile);
    } catch {
      setUser(null);
      setAccessToken(null);
    }
  }, []);

  // On mount: try to refresh the access token using the httpOnly cookie
  useEffect(() => {
    async function init() {
      try {
        await refreshToken();
        await refreshUser();
      } catch {
        // No valid refresh token — user is not logged in
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    }
    init();
  }, [refreshUser]);

  const login = useCallback(async (data: LoginData) => {
    await apiLogin(data);
    await refreshUser();
  }, [refreshUser]);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: user !== null,
      isLoading,
      login,
      logout,
      refreshUser,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
```

**Step 2: Wrap app in AuthProvider**

In `frontend/src/app/layout.tsx`, wrap `{children}` with `<AuthProvider>`:
```tsx
import { AuthProvider } from "@/contexts/auth-context";

export default function RootLayout({ children }: ...) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${amiri.variable} font-sans antialiased`}>
        <AuthProvider>
          <Header />
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/contexts/auth-context.tsx frontend/src/app/layout.tsx
git commit -m "feat: add AuthProvider context with automatic token refresh"
```

---

### Task 22: Login page

**Files:**
- Create: `frontend/src/app/login/page.tsx`

**Step 1: Create login page**

Create `frontend/src/app/login/page.tsx` with:
- Email + password form fields using shadcn Input
- Error display for invalid credentials
- Link to register and forgot-password
- On success: redirect to `/chat` (or to the page they were trying to access)
- Use `useAuth().login()` for authentication
- Redirect to `/` if already authenticated

Use the existing shadcn `Button`, `Input`, `Label`, and `Card` components.

**Step 2: Commit**

```bash
git add frontend/src/app/login/page.tsx
git commit -m "feat: add login page"
```

---

### Task 23: Register page

**Files:**
- Create: `frontend/src/app/register/page.tsx`

**Step 1: Create register page**

Create `frontend/src/app/register/page.tsx` with:
- Email, password, confirm password, display name fields
- Client-side validation: password min 8 chars, passwords match
- Error display for duplicate email, common password, etc.
- Link to login page
- On success: redirect to `/login` with success message
- Use `register()` from api-client

**Step 2: Commit**

```bash
git add frontend/src/app/register/page.tsx
git commit -m "feat: add register page"
```

---

### Task 24: Email verification page

**Files:**
- Create: `frontend/src/app/verify-email/page.tsx`

**Step 1: Create verify-email page**

Create `frontend/src/app/verify-email/page.tsx` with:
- Read `token` from URL search params
- On mount: call `verifyEmail(token)` from api-client
- Display success or error message
- Link to login on success

**Step 2: Commit**

```bash
git add frontend/src/app/verify-email/page.tsx
git commit -m "feat: add email verification page"
```

---

### Task 25: Forgot password + reset password pages

**Files:**
- Create: `frontend/src/app/forgot-password/page.tsx`
- Create: `frontend/src/app/reset-password/page.tsx`

**Step 1: Create forgot-password page**

Create `frontend/src/app/forgot-password/page.tsx` with:
- Email input field
- On submit: call `forgotPassword(email)` from api-client
- Show success message regardless (prevents email enumeration)

**Step 2: Create reset-password page**

Create `frontend/src/app/reset-password/page.tsx` with:
- Read `token` from URL search params
- New password + confirm password fields
- On submit: call `resetPassword(token, password)`
- Redirect to login on success

**Step 3: Commit**

```bash
git add frontend/src/app/forgot-password/page.tsx frontend/src/app/reset-password/page.tsx
git commit -m "feat: add forgot-password and reset-password pages"
```

---

### Task 26: Protected routes via Next.js middleware

**Files:**
- Create: `frontend/src/middleware.ts`
- Create: `frontend/src/components/shared/auth-guard.tsx`

**Step 1: Create client-side auth guard component**

Since the access token is in memory (not cookies), Next.js middleware can't check auth server-side. Instead, create a client-side guard:

Create `frontend/src/components/shared/auth-guard.tsx`:
```tsx
"use client";

import { useAuth } from "@/contexts/auth-context";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export function AuthGuard({ children, requireAdmin = false }: { children: React.ReactNode; requireAdmin?: boolean }) {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
    if (!isLoading && requireAdmin && user?.role !== "admin") {
      router.replace("/");
    }
  }, [isLoading, isAuthenticated, user, requireAdmin, router]);

  if (isLoading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  if (!isAuthenticated) return null;
  if (requireAdmin && user?.role !== "admin") return null;

  return <>{children}</>;
}
```

**Step 2: Wrap protected pages**

In `frontend/src/app/chat/[sessionId]/page.tsx`, wrap content with `<AuthGuard>`.
In `frontend/src/app/admin/page.tsx`, wrap content with `<AuthGuard requireAdmin>`.

**Step 3: Commit**

```bash
git add frontend/src/components/shared/auth-guard.tsx frontend/src/app/chat/ frontend/src/app/admin/
git commit -m "feat: add AuthGuard component for protected routes"
```

---

### Task 27: Settings page

**Files:**
- Create: `frontend/src/app/settings/page.tsx`

**Step 1: Create settings page**

Create `frontend/src/app/settings/page.tsx` with:
- Display name edit field
- Change password section (current + new + confirm)
- Email verification status
- Resend verification button (if not verified)
- Account deletion button (with confirmation dialog)
- Daily usage display
- Wrapped in `<AuthGuard>`

**Step 2: Commit**

```bash
git add frontend/src/app/settings/page.tsx
git commit -m "feat: add user settings page"
```

---

### Task 28: Update Header with auth state

**Files:**
- Modify: `frontend/src/components/shared/header.tsx`

**Step 1: Update Header to show auth state**

Update `frontend/src/components/shared/header.tsx`:
- If authenticated: show user display name, settings link, logout button
- If not authenticated: show login + register links
- Use `useAuth()` hook for state
- Add dropdown menu for user actions (settings, logout)

**Step 2: Commit**

```bash
git add frontend/src/components/shared/header.tsx
git commit -m "feat: update header with auth state (user menu, login/register links)"
```

---

### Task 29: Update existing hooks to use auth

**Files:**
- Modify: `frontend/src/hooks/use-chat.ts`
- Modify: `frontend/src/hooks/use-chat-sessions.ts`

**Step 1: Update hooks to pass auth headers**

Update `use-chat.ts` and `use-chat-sessions.ts` to use `authFetch` (or ensure the api-client functions include the Authorization header). The access token is managed by the api-client module, so these hooks should work via the updated `apiFetch` that includes credentials.

Verify that streaming (`streamChatMessage`) also passes the Authorization header:
```typescript
// In the streaming function, add the Authorization header to the fetch call
const headers: Record<string, string> = { "Content-Type": "application/json" };
const token = getAccessToken();
if (token) {
  headers["Authorization"] = `Bearer ${token}`;
}
```

**Step 2: Commit**

```bash
git add frontend/src/hooks/ frontend/src/lib/api-client.ts
git commit -m "feat: update hooks and API client to include auth headers"
```

---

### Task 30: Add usage counter to chat UI

**Files:**
- Create: `frontend/src/hooks/use-usage.ts`
- Modify: `frontend/src/components/chat/chat-layout.tsx`

**Step 1: Create usage hook**

Create `frontend/src/hooks/use-usage.ts`:
```typescript
"use client";

import { useState, useEffect, useCallback } from "react";
import { getUsage, type UsageInfo } from "@/lib/api-client";
import { useAuth } from "@/contexts/auth-context";

export function useUsage() {
  const { isAuthenticated } = useAuth();
  const [usage, setUsage] = useState<UsageInfo | null>(null);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const data = await getUsage();
      setUsage(data);
    } catch {
      // ignore
    }
  }, [isAuthenticated]);

  useEffect(() => { refresh(); }, [refresh]);

  return { usage, refresh };
}
```

**Step 2: Add usage display to chat layout**

In `frontend/src/components/chat/chat-layout.tsx`, show a small counter like "12/50 queries" in the sidebar footer or below the chat input.

**Step 3: Commit**

```bash
git add frontend/src/hooks/use-usage.ts frontend/src/components/chat/chat-layout.tsx
git commit -m "feat: add daily usage counter to chat UI"
```

---

## Phase 5: Pre-Launch Polish

### Task 31: Account lockout after failed login attempts

**Files:**
- Modify: `backend/app/routers/auth.py`
- Modify: `backend/app/models/db.py`

**Step 1: Add failed login tracking to User model**

Add to `User` in `backend/app/models/db.py`:
```python
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**Step 2: Generate and run migration**

```bash
cd backend && alembic revision --autogenerate -m "add login lockout fields to users"
cd backend && alembic upgrade head
```

**Step 3: Update login endpoint**

In `backend/app/routers/auth.py`, update the `login` function:
```python
# Check lockout
if user.locked_until and user.locked_until > datetime.now(timezone.utc):
    remaining = int((user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60)
    raise HTTPException(
        status_code=429,
        detail=f"Account temporarily locked. Try again in {remaining} minute(s)."
    )

# On failed login:
if not verify_password(body.password, user.password_hash):
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= 5:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    await session.commit()
    raise HTTPException(status_code=401, detail="Invalid email or password.")

# On successful login, reset counter:
user.failed_login_attempts = 0
user.locked_until = None
```

**Step 4: Commit**

```bash
git add backend/app/models/db.py backend/app/routers/auth.py backend/alembic/versions/
git commit -m "feat: add account lockout after 5 failed login attempts"
```

---

### Task 32: Soft delete (account deletion)

**Files:**
- Modify: `backend/app/routers/auth.py`

**Step 1: Add delete account endpoint**

In `backend/app/routers/auth.py`:
```python
@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Soft-delete the current user's account."""
    user.is_active = False
    user.email = f"deleted-{user.id}@deleted.invalid"
    user.display_name = None
    user.password_hash = "DELETED"

    # Revoke all refresh tokens
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    for token in result.scalars():
        token.revoked_at = datetime.now(timezone.utc)

    await session.commit()
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/auth")
```

**Step 2: Commit**

```bash
git add backend/app/routers/auth.py
git commit -m "feat: add soft-delete account endpoint"
```

---

### Task 33: Production environment config

**Files:**
- Create: `backend/.env.example` (update with all new variables)
- Modify: `backend/app/config.py`

**Step 1: Update .env.example with all settings**

Create/update `backend/.env.example`:
```env
# Database
DATABASE_URL=postgresql+asyncpg://ilmatlas:CHANGE_ME@localhost:5432/ilmatlas

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# LLM
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=qwen/qwen3-max

# Embedding
EMBEDDING_MODEL=BAAI/bge-m3

# Uploads
UPLOAD_DIR=./uploads

# Auth
JWT_SECRET_KEY=CHANGE-ME-generate-a-64-char-random-string
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# Email (Resend)
RESEND_API_KEY=your_resend_api_key_here
EMAIL_FROM=noreply@ilmatlas.com

# Frontend
FRONTEND_URL=http://localhost:3000

# Rate Limits
DEFAULT_DAILY_QUERY_LIMIT=50
ANONYMOUS_DAILY_QUERY_LIMIT=10
```

**Step 2: Add production safety check**

In `backend/app/config.py`, add a validation:
```python
from pydantic import model_validator

class Settings(BaseSettings):
    ...

    @model_validator(mode="after")
    def check_production_secrets(self):
        if self.jwt_secret_key == "CHANGE-ME-IN-PRODUCTION":
            import warnings
            warnings.warn("JWT_SECRET_KEY is using the default value! Change this in production.", stacklevel=2)
        return self
```

**Step 3: Commit**

```bash
git add backend/.env.example backend/app/config.py
git commit -m "feat: update env example and add production secret validation"
```

---

### Task 34: Create first admin user script

**Files:**
- Create: `scripts/create_admin.py`

**Step 1: Create admin creation script**

Create `scripts/create_admin.py`:
```python
"""Create an admin user. Run: python scripts/create_admin.py"""
import asyncio
import sys
sys.path.insert(0, "backend")

from app.config import settings
from app.database import async_session
from app.models.db import User
from app.services.auth.password import hash_password


async def main():
    email = input("Admin email: ").strip().lower()
    password = input("Admin password: ").strip()
    name = input("Display name: ").strip() or None

    async with async_session() as session:
        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=name,
            role="admin",
            email_verified=True,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print(f"Admin user created: {email} (id: {user.id})")


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Commit**

```bash
git add scripts/create_admin.py
git commit -m "feat: add script to create admin user"
```

---

### Task 35: Security audit checklist

**Files:**
- Create: `docs/security-checklist.md`

**Step 1: Write pre-launch security checklist**

Create `docs/security-checklist.md`:
```markdown
# Pre-Launch Security Checklist

## Authentication
- [ ] JWT_SECRET_KEY is a cryptographically random 64+ character string
- [ ] Default passwords are not used in production
- [ ] Bcrypt cost factor is 12
- [ ] Account lockout is working (5 failures → 15 min lock)
- [ ] Password reset tokens are single-use and expire in 1 hour
- [ ] Email verification tokens expire in 24 hours

## Authorization
- [ ] Admin endpoints return 401 for unauthenticated requests
- [ ] Admin endpoints return 403 for non-admin users
- [ ] Chat sessions are user-scoped (no cross-user access)
- [ ] GET /chat/sessions returns only the authenticated user's sessions

## Rate Limiting
- [ ] Registration: 3/hour per IP
- [ ] Login: 20/minute per IP
- [ ] Chat messages: 30/minute per IP + daily per-user limit
- [ ] Query: 10/day per IP for anonymous
- [ ] File upload: 5/minute per IP + admin only

## Input Validation
- [ ] Chat messages capped at 2000 chars
- [ ] Query questions capped at 500 chars
- [ ] File uploads capped at 50MB with magic byte validation
- [ ] Email addresses are validated and normalized

## Infrastructure
- [ ] HTTPS enabled (PaaS TLS termination)
- [ ] CORS restricted to frontend domain
- [ ] Security headers present (X-Content-Type-Options, X-Frame-Options, etc.)
- [ ] Database uses SSL connections
- [ ] All secrets in environment variables (not in code)
- [ ] .env files not committed to git

## Data Protection
- [ ] No PII in server logs (emails masked)
- [ ] Refresh tokens stored as SHA-256 hashes (not plaintext)
- [ ] Account deletion anonymizes user data
- [ ] forgot-password always returns same response (no email enumeration)
```

**Step 2: Commit**

```bash
git add docs/security-checklist.md
git commit -m "docs: add pre-launch security audit checklist"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| Phase 1 | Tasks 1-5 | Security hardening (CORS, headers, validation, rate limiting, upload hardening) |
| Phase 2 | Tasks 6-16 | User model, auth backend (models, migrations, services, endpoints, admin protection) |
| Phase 3 | Tasks 17-19 | User-scoped data (chat sessions, usage tracking, anonymous limits) |
| Phase 4 | Tasks 20-30 | Frontend auth (API client, context, pages, guards, header, usage counter) |
| Phase 5 | Tasks 31-35 | Pre-launch polish (lockout, soft delete, config, admin script, security checklist) |

**Total:** 35 tasks across 5 phases.
