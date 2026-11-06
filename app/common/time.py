"""统一UTC时间：数据库DATETIME存无时区UTC，API使用带时区ISO 8601。"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """返回当前无时区UTC，供数据库字段使用；不是伪造设备采样时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_utc(value: datetime | None) -> datetime | None:
    """把数据库UTC值value转为带时区时间；空值保持为空。"""
    if value is None:
        return None
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def db_time(value: datetime) -> datetime:
    """把API带时区采样时间value转为数据库UTC，并截断到SQL DATETIME(3)毫秒精度。"""
    result = value.astimezone(timezone.utc).replace(tzinfo=None)
    return result.replace(microsecond=result.microsecond // 1000 * 1000)
