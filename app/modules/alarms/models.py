"""alarms模块的数据库映射，字段沿用已确认SQL。

仅在独立测试库创建；正式MySQL不自动迁移。字段注释说明身份、单位、状态及UTC时间。"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.modules.assets.models import ID_TYPE


class AlarmEvent(TimestampMixin, Base):
    """alarm_event表：字段含义见各列注释；外键保证跨表归属一致。"""

    __tablename__ = "alarm_event"
    __table_args__ = (
        UniqueConstraint("site_id", "event_key", name="uk_alarm_event_1"),
        UniqueConstraint("site_id", "id", name="uk_alarm_event_2"),
        ForeignKeyConstraint(
            ["site_id", "device_id"], ["device.site_id", "device.id"], name="fk_alarm_event_1"
        ),
        ForeignKeyConstraint(
            ["site_id", "device_id", "point_id"],
            ["device_point.site_id", "device_point.device_id", "device_point.id"],
            name="fk_alarm_event_2",
        ),
        ForeignKeyConstraint(["acknowledged_by"], ["sys_user.id"], name="fk_alarm_event_3"),
    )
    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True, nullable=False)
    # 站点
    site_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    # 设备，站级告警可空
    device_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    # 测点，可空
    point_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    # 发生事件去重键，非规则编码
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    # 发生时间UTC
    raised_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 恢复时间UTC
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 确认时间UTC
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # ACTIVE/RECOVERED/CLOSED，确认独立记录
    status: Mapped[str] = mapped_column(String(24), server_default=text("'ACTIVE'"), nullable=False)
    # 发生时描述快照
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    # INFO/MINOR/MAJOR/CRITICAL
    severity: Mapped[str] = mapped_column(
        String(16), server_default=text("'MINOR'"), nullable=False
    )
    # 发生时阈值与观测值快照，保留历史解释
    trigger_snapshot_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    # 确认用户
    acknowledged_by: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    # 首期简要处理说明
    handling_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
