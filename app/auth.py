"""Hesla (PBKDF2) a tajný klíč pro session cookie."""
import hashlib
import hmac
import secrets

from .config import DB_PATH, SECRET_KEY

ITER = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITER)
    return f"pbkdf2${ITER}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, it, salt, h = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(dk.hex(), h)
    except ValueError:
        return False


def secret_key() -> str:
    if SECRET_KEY:
        return SECRET_KEY
    path = DB_PATH.parent / "secret.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_hex(32))
    return path.read_text().strip()
