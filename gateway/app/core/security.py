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
