from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


# Pre-computed bcrypt hash of a random string, used to equalise timing
# when no user is found (prevents timing-based email enumeration).
DUMMY_HASH = _pwd_context.hash("__timing_dummy_do_not_use__")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)
