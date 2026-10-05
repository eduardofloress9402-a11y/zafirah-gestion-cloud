import hashlib, hmac, secrets

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64)
    return f"scrypt${salt.hex()}${key.hex()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, key_hex = stored.split("$", 2)
        if scheme != "scrypt": return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(key_hex)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

def csrf_token(session) -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token

def check_csrf(session, supplied: str | None) -> bool:
    expected = session.get("csrf_token")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))
