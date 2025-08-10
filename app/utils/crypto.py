import base64
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def get_fernet() -> Optional[Fernet]:
    key = current_app.config.get('ENCRYPTION_KEY')
    if not key:
        return None
    try:
        # Validate key
        base64.urlsafe_b64decode(key)
        return Fernet(key)
    except Exception:
        return None


def encrypt_value(value: str) -> bytes:
    f = get_fernet()
    if not f:
        raise RuntimeError('Encryption key not configured')
    return f.encrypt(value.encode())


def decrypt_value(token: bytes) -> str:
    f = get_fernet()
    if not f:
        raise RuntimeError('Encryption key not configured')
    try:
        return f.decrypt(token).decode()
    except InvalidToken:
        raise RuntimeError('Invalid encryption token')
