"""本机学习版明文密码比较与短期Bearer令牌；JWT仍使用HS256签名，密码不入日志。"""

from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from uuid import uuid4

import jwt

from app.core.exceptions import BusinessError


def password_matches(password: str, stored: str) -> bool:
    """比较输入密码password与数据库明文stored；UTF-8字节支持中文，不回显密码。

    按用户要求使用明文存储；旧哈希未迁移时拒绝将哈希字符串本身当密码登录。
    """
    if not isinstance(stored, str) or stored.startswith("$argon2"):
        return False
    return compare_digest(password.encode("utf-8"), stored.encode("utf-8"))


def issue_token(user_id: int, secret: str, minutes: int) -> str:
    """参数为用户主键、应用签名密钥及有效分钟；返回含过期时间的访问令牌，角色仍每次查库。"""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=minutes),
            "iss": "smart-power-twin",
            "aud": "smart-power-api",
            "jti": uuid4().hex,
        },
        secret,
        algorithm="HS256",
    )


def token_subject(token: str, secret: str) -> int:
    """校验token签名、用途、期限和主体；失败统一401，不泄露解码细节。"""
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            issuer="smart-power-twin",
            audience="smart-power-api",
            options={"require": ["sub", "iat", "exp", "iss", "aud", "jti"]},
        )
        subject = payload["sub"]
        if (
            not isinstance(subject, str)
            or not subject.isascii()
            or not subject.isdecimal()
            or not 0 < int(subject) <= 18446744073709551615
        ):
            raise ValueError("invalid subject")
        return int(subject)
    except (jwt.PyJWTError, ValueError, TypeError):
        raise BusinessError("UNAUTHENTICATED", "登录令牌无效或已过期", 401) from None
