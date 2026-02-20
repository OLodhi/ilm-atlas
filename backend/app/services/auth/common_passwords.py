"""Top common passwords for validation."""

COMMON_PASSWORDS = frozenset({
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "1234567",
    "letmein", "trustno1", "dragon", "baseball", "iloveyou", "master", "sunshine",
    "ashley", "michael", "shadow", "123123", "654321", "superman", "qazwsx",
    "football", "password1", "password123", "batman", "login",
    "admin", "princess", "starwars", "hello", "charlie", "donald", "welcome",
    "jesus", "ninja", "mustang", "password1!", "1234567890", "000000",
    "access", "flower", "hottie", "loveme", "zaq1zaq1", "qwerty123",
    "passw0rd", "p@ssw0rd", "p@ssword", "1q2w3e4r", "123456789",
    "11111111", "12345", "1234", "pass", "test", "guest", "changeme",
})


def is_common_password(password: str) -> bool:
    return password.lower() in COMMON_PASSWORDS
