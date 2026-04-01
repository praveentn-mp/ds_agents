"""Credential encryption using Fernet."""

from cryptography.fernet import Fernet
import json
from backend.config import settings


def get_fernet() -> Fernet:
    key = settings.fernet_key
    if not key:
        key = Fernet.generate_key().decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_credentials(credentials: dict) -> str:
    f = get_fernet()
    return f.encrypt(json.dumps(credentials).encode()).decode()


def decrypt_credentials(encrypted: str) -> dict:
    f = get_fernet()
    return json.loads(f.decrypt(encrypted.encode()).decode())
