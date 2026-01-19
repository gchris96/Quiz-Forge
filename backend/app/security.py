import hashlib
import secrets


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


def generate_salt() -> str:
    return secrets.token_hex(16)
