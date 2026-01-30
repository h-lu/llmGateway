import hashlib
import os
import time
from typing import Dict, Optional, Tuple

from fastapi import Depends, HTTPException, Request

from gateway.app.db.dependencies import SessionDep
from gateway.app.db.crud import lookup_student_by_hash
from gateway.app.db.models import Student

# API Key 内存缓存 (LRU Cache)
# 结构: {token_hash: (student_dict, timestamp)}
# 注意: 缓存 dict 而不是 ORM 对象，避免 DetachedInstanceError
_api_key_cache: Dict[str, Tuple[dict, float]] = {}
_cache_ttl_seconds = 60  # 缓存 60 秒
_cache_max_size = 10000  # 最大缓存条目


def _get_cached_student(token_hash: str) -> Optional[Student]:
    """从缓存获取学生信息.
    
    Returns:
        Student 对象或 None（如果缓存未命中或已过期）
    """
    if token_hash in _api_key_cache:
        student_dict, timestamp = _api_key_cache[token_hash]
        if time.time() - timestamp < _cache_ttl_seconds:
            # 从 dict 重建 Student 对象（不绑定到 Session）
            student = Student(
                id=student_dict['id'],
                name=student_dict['name'],
                email=student_dict['email'],
                api_key_hash=student_dict['api_key_hash'],
                created_at=student_dict['created_at'],
                current_week_quota=student_dict['current_week_quota'],
                used_quota=student_dict['used_quota']
            )
            return student
        else:
            # 过期清理
            del _api_key_cache[token_hash]
    return None


def _cache_student(token_hash: str, student: Student) -> None:
    """缓存学生信息.
    
    将 Student ORM 对象转换为 dict 存储，避免 Session 绑定问题。
    """
    # LRU: 如果缓存满了，删除最旧的条目
    if len(_api_key_cache) >= _cache_max_size:
        oldest_key = min(_api_key_cache, key=lambda k: _api_key_cache[k][1])
        del _api_key_cache[oldest_key]
    
    # 提取学生数据为 dict（避免缓存 ORM 对象）
    student_dict = {
        'id': student.id,
        'name': student.name,
        'email': student.email,
        'api_key_hash': student.api_key_hash,
        'created_at': student.created_at,
        'current_week_quota': student.current_week_quota,
        'used_quota': student.used_quota
    }
    _api_key_cache[token_hash] = (student_dict, time.time())


def get_admin_token() -> str:
    """Get admin token from environment variable.
    
    The token is cached on first access to avoid repeated environment
    variable lookups and reduce timing attack window.
    
    Raises:
        ValueError: If ADMIN_TOKEN environment variable is not set
    """
    # Use a simple module-level cache
    if not hasattr(get_admin_token, '_cached_token'):
        token = os.getenv("ADMIN_TOKEN")
        if not token:
            raise ValueError(
                "ADMIN_TOKEN environment variable is not set. "
                "Please set a secure admin token before starting the server."
            )
        get_admin_token._cached_token = token
    return get_admin_token._cached_token


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
    
    # Use empty string if token is None to prevent timing differences
    # Always perform comparison to prevent enumeration via timing analysis
    if token is None:
        token = ""
    
    # Use constant-time comparison to prevent timing attacks
    import hmac
    if not hmac.compare_digest(token, expected_token):
        # Use consistent error message to prevent token enumeration
        raise HTTPException(
            status_code=401, 
            detail="Invalid or missing admin token"
        )
    
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
    
    Uses in-memory LRU cache to avoid database lookup on every request,
    significantly improving performance under high concurrency.
    
    Args:
        request: The incoming request
        session: Database session injected via SessionDep
        
    Returns:
        The Student object associated with the API key
        
    Raises:
        HTTPException: 401 if API key is missing or invalid
    """
    token = get_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing API key")
    
    # Hash the token
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    # 1. 先查内存缓存
    cached_student = _get_cached_student(token_hash)
    if cached_student:
        return cached_student
    
    # 2. 缓存未命中，查数据库
    student = await lookup_student_by_hash(session, token_hash)
    
    if not student:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # 3. 写入缓存
    _cache_student(token_hash, student)
    
    return student


# Alias for backward compatibility
require_api_key_with_session = require_api_key
