"""告警仓储：范围过滤后分页；采样持有测点锁，活动事件使用MySQL锁定当前读。"""

from sqlalchemy import select

from app.modules.alarms.models import AlarmEvent
from app.modules.assets.repository import page_rows

RULE = "numeric_threshold_v1"


def active_event(session, point_id):
    """只返回本引擎管理的活动事件，不能自动恢复导入样例或外部平台事件。

    调用方必须已按升序持有测点行锁；锁定当前读避免首次建事件的并发重复。
    """
    rows = session.scalars(
        select(AlarmEvent)
        .where(AlarmEvent.point_id == point_id, AlarmEvent.status == "ACTIVE")
        .order_by(AlarmEvent.id.desc())
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return next(
        (
            e
            for e in rows
            if isinstance(e.trigger_snapshot_json, dict)
            and e.trigger_snapshot_json.get("rule") == RULE
        ),
        None,
    )


def list_events(session, site_ids, page, page_size, **filters):
    """先限制site_ids，再按身份/状态/级别/确认/发生时间筛选，返回(页内记录,总数)。"""
    statement = select(AlarmEvent).where(AlarmEvent.site_id.in_(site_ids))
    for key in ("site_id", "device_id", "point_id", "status", "severity"):
        if filters.get(key) is not None:
            statement = statement.where(getattr(AlarmEvent, key) == filters[key])
    if filters.get("acknowledged") is not None:
        condition = AlarmEvent.acknowledged_at.is_not(None)
        statement = statement.where(condition if filters["acknowledged"] else ~condition)
    if filters.get("start") is not None:
        statement = statement.where(AlarmEvent.raised_at >= filters["start"])
    if filters.get("end") is not None:
        statement = statement.where(AlarmEvent.raised_at < filters["end"])
    return page_rows(
        session,
        statement.order_by(AlarmEvent.raised_at.desc(), AlarmEvent.id.desc()),
        page,
        page_size,
    )
