import hashlib
import secrets


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """В базе лежит только хэш: украденная база не даёт токенов."""
    return hashlib.sha256(token.encode()).hexdigest()
