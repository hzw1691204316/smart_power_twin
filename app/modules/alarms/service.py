"""告警闭环：新鲜数值触发/恢复，与采样同事务；确认/关闭持事件锁并追加审计。"""

from uuid import uuid4

from app.common.access import commit, find, require_writable, result
from app.common.time import as_utc, utc_now
from app.core.exceptions import BusinessError
from app.modules.alarms.models import AlarmEvent
from app.modules.alarms.repository import RULE, active_event
from app.modules.assets.models import Device, Site
from app.modules.monitoring.models import DevicePoint
from app.modules.system.models import User
from app.modules.system.service import audit


def evaluate(session, principal, point, device, sample, sampled_at, now):
    """仅由采样最新值推进分支调用，参数时间均为UTC无时区数据库时刻。

    要求启用数值点、至少一条阈值、GOOD且时间处于[现在-陈旧周期,现在]。
    等于边界正常；持续异常不重复。无后台定时器，不产生断流/离线告警。
    规则固定MINOR，不擅定现场等级；模拟/现场来源由监测入口先校验。
    """
    age_ms = (now - sampled_at).total_seconds() * 1000
    if (
        not point.enabled
        or point.value_type != "NUMERIC"
        or sample.quality != "GOOD"
        or sample.value_numeric is None
        or not 0 <= age_ms <= point.stale_after_ms
        or (point.alarm_low is None and point.alarm_high is None)
    ):
        return
    low = point.alarm_low is not None and sample.value_numeric < point.alarm_low
    high = point.alarm_high is not None and sample.value_numeric > point.alarm_high
    event = active_event(session, point.id)
    if low or high:
        if event is not None:
            return
        event = AlarmEvent(
            site_id=point.site_id,
            device_id=point.device_id,
            point_id=point.id,
            event_key=f"threshold-{point.id}-{uuid4().hex}",
            raised_at=sampled_at,
            status="ACTIVE",
            severity="MINOR",
            message=f"{point.name}低于下限" if low else f"{point.name}高于上限",
            trigger_snapshot_json={
                "rule": RULE,
                "source": "SIMULATED" if device.is_demo else "FIELD",
                "value": sample.value_numeric,
                "low": point.alarm_low,
                "high": point.alarm_high,
                "unit": point.unit,
                "pointCode": point.code,
                "sampledAt": as_utc(sampled_at).isoformat(),
                "sourceSequence": str(sample.source_sequence),
            },
        )
        session.add(event)
        session.flush()
        operation = "alarm:raise"
    elif event is not None:
        event.status = "RECOVERED"
        event.recovered_at = sampled_at
        operation = "alarm:recover"
    else:
        return
    audit(
        session,
        principal,
        operation,
        "alarm",
        event.id,
        event.site_id,
        {"status": event.status, "pointId": str(point.id), "rule": RULE},
    )


def alarm_out(session, event):
    """返回已通过范围校验的事件；名称按当前台账读取，发生快照不被后来的配置覆盖。"""
    site = session.get(Site, event.site_id)
    device = session.get(Device, event.device_id) if event.device_id else None
    point = session.get(DevicePoint, event.point_id) if event.point_id else None
    user = session.get(User, event.acknowledged_by) if event.acknowledged_by else None
    snapshot = event.trigger_snapshot_json
    source = snapshot.get("source") if isinstance(snapshot, dict) else None
    return {
        "id": str(event.id),
        "siteId": str(event.site_id),
        "siteName": site.name,
        "deviceId": str(event.device_id) if event.device_id else None,
        "deviceName": device.name if device else None,
        "pointId": str(event.point_id) if event.point_id else None,
        "pointName": point.name if point else None,
        "unit": point.unit if point else None,
        "status": event.status,
        "severity": event.severity,
        "message": event.message,
        "raisedAt": as_utc(event.raised_at),
        "recoveredAt": as_utc(event.recovered_at),
        "acknowledgedAt": as_utc(event.acknowledged_at),
        "acknowledgedBy": str(event.acknowledged_by) if event.acknowledged_by else None,
        "acknowledgedByName": user.username if user else None,
        "handlingNote": event.handling_note,
        "triggerSnapshot": snapshot,
        "isDemo": bool(site.is_demo or (device and device.is_demo)),
        "source": source if source in ("SIMULATED", "FIELD") else "UNKNOWN",
    }


def require_event(session, principal, event_id, *, lock=False):
    """按ID和站点范围读取；越权/不存在统一404，写入时锁定读取最新行。"""
    event = find(session, AlarmEvent, event_id)
    if event is None or event.site_id not in principal.site_ids:
        raise BusinessError("ALARM_NOT_FOUND", "告警不存在或未授权")
    if lock:
        session.refresh(event, with_for_update=True)
    return event


def act(session, settings, principal, event_id, body, operation):
    """operation限ack/close；首次确认与关闭才写审计，重复请求保留原确认人与说明。

    关闭须已恢复且确认；手动确认不能恢复设备，不提供伪造恢复接口。
    """
    require_writable(settings)
    event = require_event(session, principal, event_id, lock=True)
    if operation == "ack":
        if event.acknowledged_at is not None:
            return result(alarm_out(session, event), settings)
        if event.status == "CLOSED":
            raise BusinessError("ALARM_NOT_READY", "已关闭事件不能补写确认", 409)
        now = utc_now()
        if now < event.raised_at:
            raise BusinessError("ALARM_NOT_READY", "事件发生时间在未来，请先核对导入时间", 409)
        event.acknowledged_at = now
        event.acknowledged_by = principal.user_id
    elif operation == "close":
        if event.status == "CLOSED":
            return result(alarm_out(session, event), settings)
        if event.status != "RECOVERED" or event.acknowledged_at is None:
            raise BusinessError("ALARM_NOT_READY", "必须先恢复并人工确认后才能关闭", 409)
        event.status = "CLOSED"
    else:
        raise ValueError("未知告警操作")
    if body.handling_note:
        event.handling_note = body.handling_note
    audit(
        session,
        principal,
        "alarm:" + operation,
        "alarm",
        event.id,
        event.site_id,
        {"status": event.status, "handlingNote": body.handling_note},
    )
    commit(session)
    return result(alarm_out(session, event), settings)
