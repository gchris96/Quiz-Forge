# Password hashing and salt utilities.
import hashlib
import secrets

# Hash a password with a salt using SHA-256.
def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()

# Generate a random salt string for password hashing.
def generate_salt() -> str:
    return secrets.token_hex(16)
