# Pre-Launch Security Checklist

## Authentication
- [ ] JWT_SECRET_KEY is a cryptographically random 64+ character string
- [ ] Default passwords are not used in production
- [ ] Bcrypt cost factor is 12
- [ ] Account lockout is working (5 failures -> 15 min lock)
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
- [ ] Query: 10/minute per IP for anonymous
- [ ] File upload: 5/minute per IP + admin only

## Input Validation
- [ ] Chat messages capped at 2,000 chars
- [ ] Query questions capped at 500 chars
- [ ] File uploads capped at 50MB with magic byte validation
- [ ] Email addresses are validated and normalized

## Infrastructure
- [ ] HTTPS enabled (PaaS TLS termination)
- [ ] CORS restricted to frontend domain only
- [ ] Security headers present (X-Content-Type-Options, X-Frame-Options, etc.)
- [ ] Database uses SSL connections
- [ ] All secrets in environment variables (not in code)
- [ ] .env files not committed to git
- [ ] Qdrant API key set in production

## Data Protection
- [ ] No PII in server logs (emails masked)
- [ ] Refresh tokens stored as SHA-256 hashes (not plaintext)
- [ ] Account deletion anonymizes user data
- [ ] forgot-password always returns same response (no email enumeration)

## Cookies
- [ ] Refresh token cookie is httpOnly
- [ ] Refresh token cookie is Secure
- [ ] Refresh token cookie is SameSite=strict
- [ ] Refresh token cookie path is /auth
