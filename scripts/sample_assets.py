"""离线SQL素材：朝歌参考坐标与虚构台账，仅给SQL生成器和自动化测试使用。

不注册为后端模块、不用于应用启动，不连接MySQL、不生成实时读数。"""

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.modules import register_models
from app.modules.assets.models import Device, HighwayRoute, Site, SiteArea, SiteRouteLink


def create_sample_database():
    """仅离线工具创建短生命周期SQLite素材库；调用方必须dispose，正式启动绝不调用。"""
    register_models()
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    seed_assets(engine)
    return engine


def seed_assets(engine: Engine):
    """初始化演示引擎engine中的两站、8台设备、6个区域及S26关联。

    不返回值；使用一个事务，站点和区域先flush以满足外键。只供新内存库启动时调用，
    不是可重跑的MySQL导入脚本；业务code、数字ID和方向UNKNOWN均为演示约定。"""
    with Session(engine) as session, session.begin():
        session.add(HighwayRoute(id=1, route_code="S26", name="台辉高速（朝歌站区演示关联）"))
        for site_id, kind, code, lon, lat in [
            (1, "SERVICE", "HEBI_CHAOGE_SERVICE_DEMO", "114.227519", "35.665647"),
            (2, "TOLL", "HEBI_CHAOGE_TOLL_DEMO", "114.224891", "35.664072"),
        ]:
            session.add(
                Site(
                    id=site_id,
                    code=code,
                    name="朝歌服务区" if kind == "SERVICE" else "朝歌收费站",
                    site_type=kind,
                    scale_level="M",
                    complex_code="HEBI_CHAOGE_COMPLEX",
                    longitude=lon,
                    latitude=lat,
                    province_code="410000",
                    city_name="鹤壁市",
                    is_demo=1,
                    location_source="公开参考位置，非实测入口；设备与区域为虚构演示台账，需现场核验",
                    aliases_json=["朝歌", "鹤壁"],
                )
            )
        session.flush()
        for site_id in [1, 2]:
            base = site_id * 100
            session.add_all(
                [
                    SiteArea(
                        id=base + 1,
                        site_id=site_id,
                        code="POWER",
                        area_type="POWER_ROOM",
                        name="配电及储能区（演示）",
                    ),
                    SiteArea(
                        id=base + 2,
                        site_id=site_id,
                        code="PV",
                        area_type="BUILDING",
                        name="光伏区（演示）",
                    ),
                    SiteArea(
                        id=base + 3,
                        site_id=site_id,
                        code="PARK",
                        area_type="PARKING",
                        name="停车充电区（演示）",
                    ),
                ]
            )
        session.flush()
        for site_id in [1, 2]:
            base = site_id * 100
            session.add(
                SiteRouteLink(
                    site_id=site_id,
                    route_id=1,
                    link_code="S26_DEMO",
                    direction_code="UNKNOWN",
                    direction_label="鹤辉高速段，方向待核验",
                    is_primary=1,
                )
            )
            for offset, code, name, kind, system, area, power, energy, capacity in [
                (1, "ESS_01", "储能一体柜01（演示）", "ESS_CABINET", "ESS", 1, "100", "215", None),
                (
                    2,
                    "TRANSFORMER_01",
                    "箱式变压器01（演示）",
                    "TRANSFORMER",
                    "GRID",
                    1,
                    None,
                    None,
                    "630",
                ),
                (3, "PV_01", "光伏阵列（演示）", "PV_ARRAY", "PV", 2, "120", None, None),
                (
                    4,
                    "CHARGER_01",
                    "直流充电桩01（演示）",
                    "DC_CHARGER",
                    "CHARGING",
                    3,
                    "120",
                    None,
                    None,
                ),
            ]:
                session.add(
                    Device(
                        id=base + offset,
                        site_id=site_id,
                        area_id=base + area,
                        code=code,
                        name=name,
                        device_type=kind,
                        system_type=system,
                        is_demo=1,
                        rated_power_kw=power,
                        rated_energy_kwh=energy,
                        rated_capacity_kva=capacity,
                    )
                )
