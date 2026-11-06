"""大屏只读仓储：站点授权先于省市筛选，设备来源先于测点/告警查询，不提交事务。"""

from sqlalchemy import or_, select

from app.modules.alarms.models import AlarmEvent
from app.modules.assets.models import Device, Site
from app.modules.monitoring.models import DevicePoint
from app.modules.monitoring.repository import latest_values


def records(session, site_ids, province, city, site_id, source):
    """返回授权站点、所选来源设备/测点/最新值/未关闭事件；source为FIELD或SIMULATED。

    站点计数保留全部授权台账；设备和功率按设备is_demo筛选。无设备的站点级事件按站点is_demo区分。
    province支持41/410000，city支持鹤壁/鹤壁市；条件交集无匹配时返回空集合。
    """
    query = select(Site).where(Site.id.in_(site_ids))
    if province:
        query = query.where(Site.province_code.in_([province[:2], province[:2] + "0000"]))
    if city:
        base = city.strip().removesuffix("市")
        query = query.where(Site.city_name.in_([base, base + "市"]))
    if site_id is not None:
        query = query.where(Site.id == site_id)
    sites = list(session.scalars(query.order_by(Site.id)))
    ids = [s.id for s in sites]
    demo = int(source == "SIMULATED")
    devices = list(
        session.scalars(select(Device).where(Device.site_id.in_(ids), Device.is_demo == demo))
    )
    device_ids = [d.id for d in devices]
    points = list(session.scalars(select(DevicePoint).where(DevicePoint.device_id.in_(device_ids))))
    values = latest_values(session, [p.id for p in points])
    site_event_ids = [s.id for s in sites if bool(s.is_demo) == bool(demo)]
    alarms = list(
        session.scalars(
            select(AlarmEvent).where(
                AlarmEvent.site_id.in_(ids),
                AlarmEvent.status != "CLOSED",
                or_(
                    AlarmEvent.device_id.in_(device_ids),
                    (AlarmEvent.device_id.is_(None)) & (AlarmEvent.site_id.in_(site_event_ids)),
                ),
            )
        )
    )
    return sites, devices, points, values, alarms
