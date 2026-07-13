import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.config import settings


_development_secret = secrets.token_urlsafe(48)
_TOKEN_ISSUER = "wenheng-workspace"
_TOKEN_AUDIENCE = "wenheng-admin"
_BCRYPT_MAX_PASSWORD_BYTES = 72


def _signing_key() -> str:
    return settings.SECRET_KEY or _development_secret


def generate_card_key(length: int = 16, prefix: str = "") -> str:
    """生成卡密"""
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(chars) for _ in range(length))
    if prefix:
        return f"{prefix}-{random_part}"
    return random_part


def generate_access_link(card_key: str, base_url: str = "http://localhost:9800") -> str:
    """生成访问链接"""
    return f"{base_url}/access/{card_key}"


def generate_session_id() -> str:
    """生成会话ID"""
    return secrets.token_urlsafe(32)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > _BCRYPT_MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode("ascii"))
    except (TypeError, ValueError, UnicodeEncodeError):
        return False


def get_password_hash(password: str) -> str:
    """哈希密码"""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > _BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError("管理员密码的 UTF-8 编码不能超过 72 字节")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("ascii")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": _TOKEN_ISSUER,
        "aud": _TOKEN_AUDIENCE,
        "jti": secrets.token_urlsafe(16),
    })
    encoded_jwt = jwt.encode(to_encode, _signing_key(), algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """验证令牌"""
    try:
        payload = jwt.decode(
            token,
            _signing_key(),
            algorithms=[settings.ALGORITHM],
            issuer=_TOKEN_ISSUER,
            audience=_TOKEN_AUDIENCE,
        )
        return payload
    except InvalidTokenError:
        return None
