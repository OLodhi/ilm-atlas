# Ilm Atlas: User Accounts, Security & Public Launch Design

**Date:** 2026-02-20
**Status:** Approved

## Summary

Add user authentication, session management, security hardening, and public launch readiness to Ilm Atlas. This transforms the app from a local development tool into a production-ready public service.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auth model | Email + Password | Full control, no vendor dependency, OAuth addable later |
| Session management | JWT (access + refresh tokens) | Stateless, industry standard for SPAs |
| Deployment target | PaaS (Railway/Render/Fly.io) | Minimal DevOps, managed TLS, easy scaling |
| User roles | User + Admin | Simple, sufficient for launch |
| Rate limiting | Per-user daily limits | Fair, controls LLM costs, easy to understand |
| Email service | Resend | Modern API, generous free tier, excellent DX |
| Auth architecture | Custom (FastAPI-native) | Cleanest fit for the stack, zero external deps |

---

## 1. Database Schema

### New Tables

#### User (`users`)
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| email | String(320) | UNIQUE, NOT NULL |
| email_verified | Boolean | default=False |
| password_hash | String(128) | NOT NULL |
| display_name | String(100) | nullable |
| role | String(20) | default="user" (user \| admin) |
| is_active | Boolean | default=True |
| daily_query_limit | Int | default=50 |
| created_at | DateTime(UTC) | |
| updated_at | DateTime(UTC) | onupdate |

#### RefreshToken (`refresh_tokens`)
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID FK → User | NOT NULL |
| token_hash | String(128) | UNIQUE |
| expires_at | DateTime(UTC) | NOT NULL |
| created_at | DateTime(UTC) | |
| revoked_at | DateTime(UTC) | nullable |
| device_info | String(500) | nullable |

#### UsageLog (`usage_logs`)
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID FK → User | NOT NULL |
| date | Date | NOT NULL |
| query_count | Int | default=0 |
| | | UNIQUE(user_id, date) |

#### EmailVerificationToken (`email_verification_tokens`)
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID FK → User | NOT NULL |
| token_hash | String(128) | UNIQUE |
| expires_at | DateTime(UTC) | 24h from creation |
| used_at | DateTime(UTC) | nullable |
| created_at | DateTime(UTC) | |

#### PasswordResetToken (`password_reset_tokens`)
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID FK → User | NOT NULL |
| token_hash | String(128) | UNIQUE |
| expires_at | DateTime(UTC) | 1h from creation |
| used_at | DateTime(UTC) | nullable |
| created_at | DateTime(UTC) | |

### Modified Tables

#### ChatSession (`chat_sessions`)
- Add `user_id: UUID FK → User, NOT NULL`
- Migration: add as nullable, backfill to system user, then set NOT NULL

---

## 2. Auth API Endpoints

Router prefix: `/auth`

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/auth/register` | POST | No | Create account |
| `/auth/login` | POST | No | Authenticate → tokens |
| `/auth/refresh` | POST | Refresh cookie | Rotate refresh token |
| `/auth/logout` | POST | Yes | Revoke refresh token |
| `/auth/verify-email` | POST | No | Verify email via token |
| `/auth/resend-verification` | POST | Yes | Resend verification email |
| `/auth/forgot-password` | POST | No | Send reset email |
| `/auth/reset-password` | POST | No | Reset password via token |
| `/auth/me` | GET | Yes | Get current user |
| `/auth/me` | PATCH | Yes | Update profile/password |

### Token Mechanics

- **Access token:** JWT in `Authorization: Bearer` header. 15-minute expiry. Payload: `{sub: user_id, role, exp, iat}`.
- **Refresh token:** Opaque UUID. Stored as SHA-256 hash in DB. Sent via `httpOnly`, `Secure`, `SameSite=Strict` cookie. 30-day expiry. Rotated on each use.
- **Password hashing:** bcrypt, cost factor 12.

### Registration Flow

1. Submit email + password + display_name
2. Validate: email format, password min 8 chars, not in top 10k common passwords
3. Hash password (bcrypt), create User with `email_verified=False`
4. Generate verification token, send email via Resend
5. Return success — user can login but sees "verify email" banner

### Endpoint Protection

- `/chat/*` — requires authentication, scoped to user
- `/admin/*` — requires `role=admin`
- `/query` — open for anonymous with IP-based rate limit (10/day)

---

## 3. Security Hardening

### 3a. Input Validation
- Chat messages: max 2,000 characters
- Query questions: max 500 characters
- Display name: 2-100 chars, alphanumeric + spaces
- Email: RFC 5322 validation + lowercase normalization
- Password: 8-128 chars, checked against top 10k common passwords
- File uploads: 50MB max, magic byte validation, admin-only

### 3b. Rate Limiting
- **Global:** 100 req/sec (DDoS protection)
- **Auth endpoints:** 20 req/min per IP (brute-force protection)
- **Per-user daily:** 50 chat messages (configurable per-user)
- **Anonymous /query:** 10/day per IP
- **Registration:** 3 accounts per IP per hour
- Implementation: `slowapi` for IP-based, DB for daily counters

### 3c. CORS
- Replace `allow_origins=["*"]` with explicit frontend domain
- `allow_credentials=True` (for httpOnly cookies)
- Explicit `allow_methods` and `allow_headers`

### 3d. Security Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy: default-src 'self'`
- `X-XSS-Protection: 0`
- `Referrer-Policy: strict-origin-when-cross-origin`

### 3e. Account Security
- Bcrypt cost 12
- Constant-time token comparison
- Account lockout: 5 failed attempts → 15-minute lockout
- Password reset tokens: single-use, 1-hour expiry
- Email verification tokens: single-use, 24-hour expiry
- Refresh token rotation on each use

### 3f. Data Protection
- Chat sessions scoped to `user_id` in every query
- List endpoints return only authenticated user's data
- Soft delete: account data anonymized for 30 days before hard delete
- No PII in server logs

### 3g. Infrastructure (PaaS)
- HTTPS only (PaaS TLS termination)
- Secrets via PaaS environment variables
- Managed PostgreSQL with SSL
- Qdrant API key authentication

---

## 4. Frontend Auth Integration

### New Pages
- `/login` — Email + password
- `/register` — Email + password + display name
- `/verify-email?token=...` — Email verification
- `/forgot-password` — Request reset
- `/reset-password?token=...` — Set new password
- `/settings` — Profile, password change, account deletion

### Auth State
- `AuthProvider` context wrapping the app
- State: `user`, `accessToken`, `isAuthenticated`, `isLoading`
- On load: check refresh cookie → `/auth/refresh` → set token in memory
- Access token in memory only (never localStorage)
- Auto-refresh: intercept 401 → `/auth/refresh` → retry

### Protected Routes
- Next.js middleware redirects unauthenticated from `/chat/*` to `/login`
- `/admin/*` requires `role=admin`
- `/login` and `/register` redirect to `/chat` if authenticated

### UI Changes
- Header: user display name + logout button
- Sidebar: only current user's sessions
- "Verify email" banner for unverified accounts
- Daily usage counter ("12/50 queries used today")

---

## 5. Stripe Preparation

No implementation now. Future-proofing via data model:

- `daily_query_limit` on User — paid tiers adjust this value
- `role` field supports future values (`premium`) without schema changes
- `UsageLog` already tracks daily usage for billing visibility

Future integration path:
1. Add `stripe_customer_id` + `subscription_tier` to User
2. Stripe webhook endpoint for subscription events
3. Frontend pricing page + Stripe Checkout redirect

---

## 6. Implementation Phases

### Phase 1: Security Hardening
- CORS lockdown + security headers middleware
- Input validation (message/query length caps, file size limits)
- Rate limiting (per-IP via slowapi)
- File upload hardening (magic bytes, size limits)

### Phase 2: User Model + Auth Backend
- Alembic migrations for all new tables
- Auth service (register, login, token management, password hashing)
- Email service (Resend SDK for verification + reset emails)
- FastAPI dependency: `get_current_user`, `require_admin`
- Admin role enforcement on `/admin/*`

### Phase 3: User-Scoped Data
- Add `user_id` to ChatSession + migration
- Scope all chat endpoints to authenticated user
- Per-user daily usage tracking + enforcement
- Anonymous `/query` with IP-based limits

### Phase 4: Frontend Auth
- Auth pages (login, register, verify-email, forgot-password, reset-password)
- AuthProvider context + automatic token refresh
- Protected routes middleware
- Settings page
- Usage counter in UI

### Phase 5: Pre-Launch Polish
- Account lockout logic
- Soft delete / account deletion flow
- Production environment configuration
- Deployment pipeline
- Security audit checklist

---

## Dependencies

### Backend (new)
- `python-jose[cryptography]` — JWT encoding/decoding
- `passlib[bcrypt]` — Password hashing
- `resend` — Email delivery
- `slowapi` — Rate limiting

### Frontend (new)
- `js-cookie` — Cookie utilities (if needed for CSRF)
- No new major dependencies expected
