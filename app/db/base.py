"""ORM公共基础：统一MySQL模型元数据及时间字段；临时建表仅限隔离自动化测试。"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有ORM表模型的基类。metadata汇总已注册表；不能对现有MySQL自动create_all。"""

    pass


class TimestampMixin:
    """公共创建／更新时间字段。数据库时间按项目约定使用UTC；不会充当设备采样时间。"""

    # 台账记录创建时间，按项目约定存UTC；不是设备采样时间。
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # 台账记录更新时间；数据库会话UTC设置见session.py。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
