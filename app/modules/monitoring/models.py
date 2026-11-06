"""monitoring模块的数据库映射，字段沿用已确认SQL。

正式运行连接已有MySQL；只有隔离测试创建表。字段注释说明身份、单位、状态及UTC时间。"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.modules.assets.models import ID_TYPE


class DevicePoint(TimestampMixin, Base):
    """device_point表：字段含义见各列注释；外键保证跨表归属一致。"""

    __tablename__ = "device_point"
    __table_args__ = (
        UniqueConstraint("device_id", "code", name="uk_device_point_1"),
        UniqueConstraint("site_id", "device_id", "id", name="uk_device_point_2"),
        UniqueConstraint("site_id", "id", name="uk_device_point_3"),
        ForeignKeyConstraint(
            ["site_id", "device_id"], ["device.site_id", "device.id"], name="fk_device_point_1"
        ),
    )
    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True, nullable=False)
    # 站点
    site_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    # 所属设备
    device_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    # 设备内测点编码
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    # 测点名称
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 建议采样周期毫秒
    sample_interval_ms: Mapped[int] = mapped_column(
        Integer, server_default=text("5000"), nullable=False
    )
    # 数据陈旧阈值毫秒
    stale_after_ms: Mapped[int] = mapped_column(
        Integer, server_default=text("15000"), nullable=False
    )
    # 启用标志
    enabled: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    # kW/kWh/%/BOOL等
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    # NUMERIC/TEXT/BOOLEAN
    value_type: Mapped[str] = mapped_column(
        String(16), server_default=text("'NUMERIC'"), nullable=False
    )
    # INSTANT瞬时/COUNTER累计/STATE状态
    aggregation_type: Mapped[str] = mapped_column(
        String(24), server_default=text("'INSTANT'"), nullable=False
    )
    # 正负方向约定
    direction_convention: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # 简单低阈值，可空
    alarm_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 简单高阈值，可空
    alarm_high: Mapped[float | None] = mapped_column(Float, nullable=True)


class PointLatest(TimestampMixin, Base):
    """point_latest表：字段含义见各列注释；外键保证跨表归属一致。"""

    __tablename__ = "point_latest"
    __table_args__ = (
        ForeignKeyConstraint(["point_id"], ["device_point.id"], name="fk_point_latest_1"),
    )
    # 测点
    point_id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, nullable=False)
    # 源采样时间UTC
    source_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 平台接收时间UTC
    received_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 数值/布尔值
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 文本值
    value_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # GOOD/SUSPECT/BAD/MANUAL/ESTIMATED
    quality: Mapped[str] = mapped_column(String(16), nullable=False)
    # 去重及同时间排序序号
    source_sequence: Mapped[int] = mapped_column(ID_TYPE, server_default=text("0"), nullable=False)


class PointHistory(Base):
    """point_history表：字段含义见各列注释；外键保证跨表归属一致。"""

    __tablename__ = "point_history"
    __table_args__ = (
        ForeignKeyConstraint(["point_id"], ["device_point.id"], name="fk_point_history_1"),
    )
    # 测点
    point_id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, nullable=False)
    # 采样时间UTC
    sampled_at: Mapped[datetime] = mapped_column(DateTime, primary_key=True, nullable=False)
    # 源序号，重传保持相同值
    source_sequence: Mapped[int] = mapped_column(
        ID_TYPE, server_default=text("0"), primary_key=True, nullable=False
    )
    # 接收时间UTC
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 数值
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 文本值
    value_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # GOOD/SUSPECT/BAD/MANUAL/ESTIMATED
    quality: Mapped[str] = mapped_column(String(16), nullable=False)
