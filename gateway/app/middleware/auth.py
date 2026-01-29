import hashlib
import os

from fastapi import Depends, HTTPException, Request

from gateway.app.db.dependencies import SessionDep
from gateway.app.db.crud import lookup_student_by_hash
from gateway.app.db.models import Student


def get_admin_token() -> str:
    """Get admin token from environment variable.
    
    Raises:
        ValueError: If ADMIN_TOKEN environment variable is not set
    """
    token = os.getenv("ADMIN_TOKEN")
    if not token:
        raise ValueError(
            "ADMIN_TOKEN environment variable is not set. "
            "Please set a secure admin token before starting the server."
        )
    return token


def require_admin(request: Request) -> str:
    """Validate admin token for protected endpoints.
    
    Args:
        request: The incoming request
        
    Returns:
        Admin identifier if valid
        
    Raises:
        HTTPException: 401 if admin token is missing or invalid
    """
    token = get_bearer_token(request)
    expected_token = get_admin_token()
    
    if not token:
        raise HTTPException(status_code=401, detail="Missing admin token")
    
    # Use constant-time comparison to prevent timing attacks
    import hmac
    if not hmac.compare_digest(token, expected_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    
    return "admin"


def get_bearer_token(request: Request) -> str | None:
    """Extract Bearer token from Authorization header.
    
    Args:
        request: The incoming request
        
    Returns:
        The token string if present, None otherwise
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return auth.replace("Bearer ", "", 1).strip()


async def require_api_key(
    request: Request,
    session: SessionDep,
) -> Student:
    """Validate API key and return the associated student.
    
    This function uses FastAPI's dependency injection to get a database session.
    Use with Depends() in route definitions.
    
    Args:
        request: The incoming request
        session: Database session injected via SessionDep
        
    Returns:
        The Student object associated with the API key
        
    Raises:
        HTTPException: 401 if API key is missing or invalid
        
    Example:
        @router.post("/chat")
        async def chat(
            request: Request,
            student: Student = Depends(require_api_key)
        ):
            ...
    """
    token = get_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing API key")
    
    # Hash the token and look up the student
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    student = await lookup_student_by_hash(session, token_hash)
    
    if not student:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return student


# Alias for backward compatibility
require_api_key_with_session = require_api_key
