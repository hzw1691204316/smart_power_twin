"""台账ORM映射：对应现有19表方案中的5张表，只表达存储字段和归属关系。

字段注释沿用桌面SQL；接口字段见schemas，查询见repository。
这些模型只在进程内演示库建表，不用于重建或迁移已有MySQL。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

ID_TYPE = BIGINT(unsigned=True).with_variant(Integer, "sqlite")


class Site(TimestampMixin, Base):
    """site站点表：收费站或服务区的身份、规模、坐标、来源和生命周期；没有实时读数。"""

    __tablename__ = "site"
    __table_args__ = (UniqueConstraint("id", "site_type"),)

    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    # 唯一站点业务编码
    code: Mapped[str] = mapped_column(String(64), unique=True)
    # 真实站点名称
    name: Mapped[str] = mapped_column(String(150))
    # TOLL收费站/SERVICE服务区
    site_type: Mapped[str] = mapped_column(String(16))
    # S小/M中/L大，业务展示分级
    scale_level: Mapped[str] = mapped_column(String(1))
    # 独立上下行站点的共同分组码
    complex_code: Mapped[str | None] = mapped_column(String(64))
    # 经度
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(11, 7))
    # 纬度
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    # 坐标系统，按实际数据修改
    coordinate_system: Mapped[str] = mapped_column(String(32), default="WGS84")
    # 坐标来源
    location_source: Mapped[str | None] = mapped_column(String(500))
    # 坐标核验时间UTC
    location_verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    # 业务时区
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    # 1为演示站点
    is_demo: Mapped[int] = mapped_column(Integer, default=0)
    # ACTIVE/INACTIVE/RETIRED
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    # 管理单位名称，首期不建组织树
    management_name: Mapped[str | None] = mapped_column(String(150))
    # 省级编码，例如41；编码规范由应用统一
    province_code: Mapped[str] = mapped_column(String(16))
    # 地市名称
    city_name: Mapped[str | None] = mapped_column(String(100))
    # 站点简称/别名字符串数组
    aliases_json: Mapped[list | None] = mapped_column(JSON)


class SiteArea(TimestampMixin, Base):
    """site_area区域表：同一站点内的区域树；复合外键保证父区域不能跨站。"""

    __tablename__ = "site_area"
    __table_args__ = (
        UniqueConstraint("site_id", "code"),
        UniqueConstraint("site_id", "id"),
        ForeignKeyConstraint(["site_id", "parent_id"], ["site_area.site_id", "site_area.id"]),
    )

    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    # 站点
    site_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("site.id"))
    # 上级区域，须同站
    parent_id: Mapped[int | None] = mapped_column(ID_TYPE)
    # 站内区域编码
    code: Mapped[str] = mapped_column(String(64))
    # DIRECTION/BUILDING/PARKING/POWER_ROOM等
    area_type: Mapped[str] = mapped_column(String(32))
    # 区域名称
    name: Mapped[str] = mapped_column(String(150))


class Device(TimestampMixin, Base):
    """device设备表：唯一归属站点，可归属站内区域或父设备；额定参数不是当前读数。"""

    __tablename__ = "device"
    __table_args__ = (
        UniqueConstraint("site_id", "code"),
        UniqueConstraint("site_id", "id"),
        ForeignKeyConstraint(["site_id", "area_id"], ["site_area.site_id", "site_area.id"]),
        ForeignKeyConstraint(["site_id", "parent_device_id"], ["device.site_id", "device.id"]),
    )

    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    # 唯一所属站点
    site_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("site.id"))
    # 物理安装区域
    area_id: Mapped[int | None] = mapped_column(ID_TYPE)
    # 组成关系中的父设备
    parent_device_id: Mapped[int | None] = mapped_column(ID_TYPE)
    # 站内设备编码
    code: Mapped[str] = mapped_column(String(64))
    # 设备名称
    name: Mapped[str] = mapped_column(String(150))
    # 设备类型，须与型号一致
    device_type: Mapped[str] = mapped_column(String(32))
    # 额定功率kW
    rated_power_kw: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    # 额定储能电量kWh
    rated_energy_kwh: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    # 额定视在容量kVA
    rated_capacity_kva: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    # 演示设备标志
    is_demo: Mapped[int] = mapped_column(Integer, default=0)
    # ACTIVE/MAINTENANCE/INACTIVE/RETIRED
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE")
    # PV/ESS/CHARGING/GRID/LOAD/AUX
    system_type: Mapped[str] = mapped_column(String(24), default="AUX")
    # 设备厂家
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    # 厂家型号
    model_code: Mapped[str | None] = mapped_column(String(100))


class HighwayRoute(TimestampMixin, Base):
    """highway_route路线身份表：业务编号唯一，可关联GeoJSON地址和来源版本。"""

    __tablename__ = "highway_route"

    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    # 路线编号，例如G4
    route_code: Mapped[str] = mapped_column(String(32), unique=True)
    # 路线名称
    name: Mapped[str] = mapped_column(String(150))
    # 路线别名，检索可后续规范化
    aliases_json: Mapped[list | None] = mapped_column(JSON)
    # ACTIVE/INACTIVE
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    # 路线GeoJSON等资源地址，前端按省范围展示
    geometry_uri: Mapped[str | None] = mapped_column(String(1000))
    # 路线几何坐标系统
    coordinate_system: Mapped[str] = mapped_column(String(32), default="WGS84")
    # 路线数据来源
    source_url: Mapped[str | None] = mapped_column(String(1000))
    # 地图资源授权依据
    license_ref: Mapped[str | None] = mapped_column(String(1000))
    # 路网资源版本
    data_version: Mapped[str | None] = mapped_column(String(100))


class SiteRouteLink(TimestampMixin, Base):
    """site_route_link关联表：站点连接哪条路线、哪个方向；一个站点可有多条关联。"""

    __tablename__ = "site_route_link"
    __table_args__ = (
        UniqueConstraint("site_id", "link_code"),
        UniqueConstraint("site_id", "id"),
        ForeignKeyConstraint(["site_id", "area_id"], ["site_area.site_id", "site_area.id"]),
    )

    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    # 站点
    site_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("site.id"))
    # 具体上下行区域
    area_id: Mapped[int | None] = mapped_column(ID_TYPE)
    # 高速路线
    route_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("highway_route.id"))
    # 站内关联编码
    link_code: Mapped[str] = mapped_column(String(64))
    # UP/DOWN/BOTH/UNKNOWN
    direction_code: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    # 例如往郑州方向
    direction_label: Mapped[str | None] = mapped_column(String(100))
    # 该路线该方向里程桩号，单位米
    chainage_m: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    # DIRECT/INTERCHANGE/OTHER
    access_type: Mapped[str] = mapped_column(String(24), default="DIRECT")
    # 主路线标志，唯一性由服务校验
    is_primary: Mapped[int] = mapped_column(Integer, default=0)
