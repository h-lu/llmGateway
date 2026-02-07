import hashlib
import asyncio
import os
import time
from collections import OrderedDict
from typing import Optional, Tuple

from fastapi import HTTPException, Request

from gateway.app.db.dependencies import SessionDep
from gateway.app.db.crud import lookup_student_by_hash
from gateway.app.db.models import Student

# API Key 内存缓存 (使用 OrderedDict 实现 LRU Cache)
# 结构: {token_hash: (student_dict, timestamp)}
# 注意: 缓存 dict 而不是 ORM 对象，避免 DetachedInstanceError
# OrderedDict 保持插入顺序，支持 popitem(last=False) 移除最旧的条目
_api_key_cache: OrderedDict[str, Tuple[dict, float]] = OrderedDict()
_cache_ttl_seconds = 60  # 缓存 60 秒
_cache_max_size = 10000  # 最大缓存条目
_cache_lock = asyncio.Lock()  # 保护缓存的锁


async def _get_cached_student(token_hash: str) -> Optional[Student]:
    """从缓存获取学生信息（线程安全）.

    实现完整的 LRU 逻辑：访问时将条目移到末尾，保持访问顺序。

    Returns:
        Student 对象或 None（如果缓存未命中或已过期）
    """
    async with _cache_lock:
        if token_hash in _api_key_cache:
            student_dict, timestamp = _api_key_cache[token_hash]
            if time.time() - timestamp < _cache_ttl_seconds:
                # LRU: 将访问的条目移到末尾（最近使用）
                # 先删除再重新插入以保持插入顺序
                value = _api_key_cache.pop(token_hash)
                _api_key_cache[token_hash] = value

                # 从 dict 重建 Student 对象（不绑定到 Session）
                student = Student(
                    id=student_dict["id"],
                    name=student_dict["name"],
                    email=student_dict["email"],
                    api_key_hash=student_dict["api_key_hash"],
                    created_at=student_dict["created_at"],
                    current_week_quota=student_dict["current_week_quota"],
                    used_quota=student_dict["used_quota"],
                    provider_api_key_encrypted=student_dict.get(
                        "provider_api_key_encrypted"
                    ),
                    provider_type=student_dict.get("provider_type", "deepseek"),
                )
                return student
            else:
                # 过期清理
                del _api_key_cache[token_hash]
    return None


async def _cache_student(token_hash: str, student: Student) -> None:
    """缓存学生信息（线程安全）.

    将 Student ORM 对象转换为 dict 存储，避免 Session 绑定问题。
    使用锁保护缓存操作，防止并发访问导致的竞争条件。

    LRU 实现：使用 OrderedDict，访问时移到末尾，驱逐时移除最旧的条目。
    """
    async with _cache_lock:
        # 如果 key 已存在，先删除（会在下面重新添加到末尾）
        if token_hash in _api_key_cache:
            del _api_key_cache[token_hash]

        # LRU: 如果缓存满了，删除最旧的条目（插入顺序的第一个）
        if len(_api_key_cache) >= _cache_max_size:
            # 移除最旧的 20% 条目，减少驱逐频率
            remove_count = max(1, int(_cache_max_size * 0.2))
            for _ in range(remove_count):
                if _api_key_cache:
                    _api_key_cache.popitem(last=False)

        # 提取学生数据为 dict（避免缓存 ORM 对象）
        student_dict = {
            "id": student.id,
            "name": student.name,
            "email": student.email,
            "api_key_hash": student.api_key_hash,
            "created_at": student.created_at,
            "current_week_quota": student.current_week_quota,
            "used_quota": student.used_quota,
            "provider_api_key_encrypted": student.provider_api_key_encrypted,
            "provider_type": student.provider_type,
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
    if not hasattr(get_admin_token, "_cached_token"):
        token = os.getenv("ADMIN_TOKEN")
        if token is not None:
            # Normalize accidental whitespace/newline from env/secret stores.
            token = token.strip()
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
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")

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
        HTTPException: 400 if API key is too long (DoS protection)
    """
    token = get_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing API key")

    # Validate API key length to prevent DoS via extremely long keys
    # This must be done before hashing to prevent CPU exhaustion on long inputs
    if len(token) > 512:
        raise HTTPException(
            status_code=400, detail="API key too long (max 512 characters)"
        )

    # Hash the token
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # 1. 先查内存缓存
    cached_student = await _get_cached_student(token_hash)
    if cached_student:
        return cached_student

    # 2. 缓存未命中，查数据库
    student = await lookup_student_by_hash(session, token_hash)

    if not student:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # 3. 写入缓存
    await _cache_student(token_hash, student)

    return student


# Alias for backward compatibility
require_api_key_with_session = require_api_key
