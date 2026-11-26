"""安全模块：BCrypt 密码 + JWT + 登录失败锁定（方案第十章）。"""
import asyncio
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()

# 进程内登录失败计数（多 worker 各自计数,锁定量级满足管理要求;生产可换 Redis）
_login_fail: dict[str, list[float]] = {}
_lock_until: dict[str, float] = {}
_lock = asyncio.Lock()


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode())
    except ValueError:
        return False


async def check_login_lock(username: str) -> int:
    """返回剩余锁定秒数，0 表示未锁定。"""
    async with _lock:
        until = _lock_until.get(username, 0)
        now = time.time()
        if until > now:
            return int(until - now) + 1
        _lock_until.pop(username, None)
        return 0


async def record_login_fail(username: str) -> None:
    async with _lock:
        now = time.time()
        fails = [t for t in _login_fail.get(username, []) if now - t < 600]
        fails.append(now)
        _login_fail[username] = fails
        if len(fails) >= settings.login_max_fail:
            _lock_until[username] = now + settings.login_lock_minutes * 60
            _login_fail.pop(username, None)


async def clear_login_fail(username: str) -> None:
    async with _lock:
        _login_fail.pop(username, None)
        _lock_until.pop(username, None)


def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": str(user_id), "username": username, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expire_days)
    payload = {"sub": str(user_id), "username": username, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_refresh_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "refresh":
        return None
    return payload


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
