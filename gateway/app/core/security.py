import hashlib
import secrets


def hash_api_key(raw_key: str) -> str:
    """Hash an API key using SHA256.
    
    DEPRECATED: This function is kept for backward compatibility.
    New code should use hash_api_key_with_salt() for better security.
    
    Args:
        raw_key: The raw API key to hash
        
    Returns:
        The SHA256 hex digest of the key
    """
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def hash_api_key_with_salt(raw_key: str, salt: str | None = None) -> tuple[str, str]:
    """Hash an API key using PBKDF2 with SHA256.
    
    This is the recommended method for new code. It uses PBKDF2 with
    100,000 iterations and a random salt for secure key storage.
    
    Args:
        raw_key: The raw API key to hash
        salt: Optional salt. If not provided, a random salt will be generated.
        
    Returns:
        A tuple of (salt, hashed_key)
    """
    if salt is None:
        salt = secrets.token_hex(16)
    
    # Use PBKDF2 with 100,000 iterations for security
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        raw_key.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    
    return salt, hashed


def verify_api_key(raw_key: str, salt: str, hashed_key: str) -> bool:
    """Verify a raw API key against a hashed key.
    
    Args:
        raw_key: The raw API key to verify
        salt: The salt used for hashing
        hashed_key: The previously hashed key
        
    Returns:
        True if the key matches, False otherwise
    """
    _, computed_hash = hash_api_key_with_salt(raw_key, salt)
    return secrets.compare_digest(computed_hash, hashed_key)


# ============================================
# API Key Encryption (Balance Architecture)
# ============================================

import base64
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from gateway.app.core.config import settings


def _get_encryption_key() -> bytes:
    """Get or derive encryption key from settings."""
    key = settings.api_key_encryption_key
    
    if not key:
        # Development fallback - generate a deterministic key
        # WARNING: In production, always set API_KEY_ENCRYPTION_KEY
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"teachproxy_fixed_salt_dev_only",
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(b"dev_key"))
    
    return key.encode() if isinstance(key, str) else key


def encrypt_api_key(api_key: str, cipher: Optional[Fernet] = None) -> str:
    """Encrypt an API key for storage.
    
    Args:
        api_key: The plain text API key
        cipher: Optional Fernet instance (for testing)
        
    Returns:
        Base64 encoded encrypted string
    """
    if cipher is None:
        cipher = Fernet(_get_encryption_key())
    
    encrypted = cipher.encrypt(api_key.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_api_key(encrypted_key: str, cipher: Optional[Fernet] = None) -> str:
    """Decrypt an encrypted API key.
    
    Args:
        encrypted_key: The encrypted API key string
        cipher: Optional Fernet instance (for testing)
        
    Returns:
        Plain text API key
    """
    if cipher is None:
        cipher = Fernet(_get_encryption_key())
    
    encrypted_bytes = base64.urlsafe_b64decode(encrypted_key.encode())
    return cipher.decrypt(encrypted_bytes).decode()


def generate_encryption_key() -> str:
    """Generate a new encryption key for .env file.
    
    Run: python -c "from gateway.app.core.security import generate_encryption_key; print(generate_encryption_key())"
    """
    return Fernet.generate_key().decode()
