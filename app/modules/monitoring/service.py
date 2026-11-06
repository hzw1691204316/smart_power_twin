"""监测业务：有类型和来源的采样入库、幂等、最新值排序、断流识别与有界历史。"""

from datetime import timedelta

from sqlalchemy import select

from app.common.access import commit, find, require_writable, result
from app.common.time import as_utc, db_time, utc_now
from app.core.exceptions import BusinessError
from app.modules.alarms.service import evaluate
from app.modules.assets.models import Device
from app.modules.monitoring.models import DevicePoint, PointHistory, PointLatest
from app.modules.monitoring.repository import history_rows
from app.modules.system.service import audit


def require_point(session, principal, point_id):
    """读取测点并校验站点范围；未授权／不存在统一404，不允许按猜测ID读取。"""
    point = find(session, DevicePoint, point_id)
    if point is None or point.site_id not in principal.site_ids:
        raise BusinessError("POINT_NOT_FOUND", "测点不存在或未授权")
    return point


def point_out(point):
    """定义响应包括单位、数据／聚合类型、采样周期和阈值；均为配置而非实时值。"""
    return {
        "id": str(point.id),
        "siteId": str(point.site_id),
        "deviceId": str(point.device_id),
        "code": point.code,
        "name": point.name,
        "unit": point.unit,
        "valueType": point.value_type,
        "aggregationType": point.aggregation_type,
        "sampleIntervalMs": point.sample_interval_ms,
        "staleAfterMs": point.stale_after_ms,
        "enabled": bool(point.enabled),
        "alarmLow": point.alarm_low,
        "alarmHigh": point.alarm_high,
        "directionConvention": point.direction_convention,
    }


def latest_out(point, latest, is_demo, now=None):
    """把最新值、质量、来源和过期状态分开返回；无值为null，ageMs不从页面时钟伪造。"""
    now = now or utc_now()
    age = max(0, int((now - latest.source_time).total_seconds() * 1000)) if latest else None
    stale = latest is None or age > point.stale_after_ms
    return {
        "pointId": str(point.id),
        "code": point.code,
        "name": point.name,
        "unit": point.unit,
        "valueType": point.value_type,
        "aggregationType": point.aggregation_type,
        "valueNumeric": latest.value_numeric if latest else None,
        "valueText": latest.value_text if latest else None,
        "sampledAt": as_utc(latest.source_time) if latest else None,
        "receivedAt": as_utc(latest.received_time) if latest else None,
        "quality": latest.quality if latest else None,
        "isStale": stale,
        "ageMs": age,
        "enabled": bool(point.enabled),
        "source": "SIMULATED" if is_demo else "FIELD",
        "sourceSequence": str(latest.source_sequence) if latest else None,
    }


def validate_sample(point, device, sample, source, now):
    """核对启用、来源、值类型和时间；BAD可无值，普通数值／文本／布尔不得混用。"""
    if not point.enabled:
        raise BusinessError("POINT_DISABLED", "测点已停用", 409)
    if source != ("SIMULATED" if device.is_demo else "FIELD"):
        raise BusinessError("SOURCE_MISMATCH", "采样来源与设备演示身份不一致", 409)
    numeric, text = sample.value_numeric, sample.value_text
    if numeric is not None and text is not None:
        raise BusinessError("VALUE_TYPE_MISMATCH", "数值与文本不能同时填写", 422)
    if point.value_type == "TEXT":
        valid = numeric is None and (text is not None or sample.quality == "BAD")
    else:
        valid = text is None and (numeric is not None or sample.quality == "BAD")
        if point.value_type == "BOOLEAN" and numeric is not None:
            valid = valid and numeric in (0, 1)
    if not valid:
        raise BusinessError("VALUE_TYPE_MISMATCH", "值与测点类型不一致或缺少有效值", 422)
    sampled = db_time(sample.sampled_at)
    if sampled.year < 1970 or sampled > now + timedelta(minutes=5):
        raise BusinessError("INVALID_SAMPLE_TIME", "采样时间过早或超过服务器时间5分钟", 422)
    return sampled


def ingest(session, settings, principal, body):
    """body为1—500条采样；整批锁点、校验、历史幂等、更新最新、审计后提交。

    返回新增/重复/最新更新条数；任何冲突整批回滚，包括阈值事件与审计。
    仅推进最新值的新鲜GOOD数值参与告警，迟到历史及重复样本不改变当前事件。
    """
    require_writable(settings)
    now = utc_now()
    points = {}
    for sample in body.samples:
        point = require_point(session, principal, sample.point_id)
        points[point.id] = point
    # 真实数据库按相同顺序锁定测点，保护首次最新值与活动告警，降低相反批次顺序死锁风险。
    session.scalars(
        select(DevicePoint)
        .where(DevicePoint.id.in_(points))
        .order_by(DevicePoint.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    inserted = duplicates = updated = 0
    site_stats = {}
    for sample in sorted(
        body.samples, key=lambda item: (int(item.point_id), item.sampled_at, item.source_sequence)
    ):
        point = points[int(sample.point_id)]
        stats = site_stats.setdefault(
            point.site_id, {"inserted": 0, "duplicates": 0, "latestUpdated": 0}
        )
        device = session.get(Device, point.device_id)
        sampled = validate_sample(point, device, sample, body.source, now)
        existing = session.scalar(
            select(PointHistory)
            .where(
                PointHistory.point_id == point.id,
                PointHistory.sampled_at == sampled,
                PointHistory.source_sequence == sample.source_sequence,
            )
            .with_for_update()
        )
        if existing:
            if (existing.value_numeric, existing.value_text, existing.quality) != (
                sample.value_numeric,
                sample.value_text,
                sample.quality,
            ):
                raise BusinessError("SAMPLE_CONFLICT", "相同采样身份的内容不一致，整批已拒绝", 409)
            duplicates += 1
            stats["duplicates"] += 1
            continue
        session.add(
            PointHistory(
                point_id=point.id,
                sampled_at=sampled,
                source_sequence=sample.source_sequence,
                received_at=now,
                value_numeric=sample.value_numeric,
                value_text=sample.value_text,
                quality=sample.quality,
            )
        )
        latest = session.scalar(
            select(PointLatest)
            .where(PointLatest.point_id == point.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if latest is None or (sampled, sample.source_sequence) > (
            latest.source_time,
            latest.source_sequence,
        ):
            if latest is None:
                latest = PointLatest(point_id=point.id)
                session.add(latest)
            latest.source_time = sampled
            latest.source_sequence = sample.source_sequence
            latest.received_time = now
            latest.value_numeric = sample.value_numeric
            latest.value_text = sample.value_text
            latest.quality = sample.quality
            evaluate(session, principal, point, device, sample, sampled, now)
            updated += 1
            stats["latestUpdated"] += 1
        inserted += 1
        stats["inserted"] += 1
        session.flush()  # 同批内重复身份／持续告警立即可见，不提前提交。
    for site_id in {point.site_id for point in points.values()}:
        audit(
            session,
            principal,
            "telemetry:write",
            "batch",
            "samples",
            site_id,
            {"source": body.source, **site_stats[site_id]},
        )
    commit(session)
    return result(
        {
            "inserted": inserted,
            "duplicates": duplicates,
            "latestUpdated": updated,
            "source": body.source,
        },
        settings,
    )


def history(session, settings, principal, point_id, start, end, limit, grain):
    """查询UTC[start,end)历史，最长31天。raw限制返回点数；聚合先限制原始1万条，再按类型均值／末值。"""
    point = require_point(session, principal, point_id)
    start, end = db_time(start), db_time(end)
    if end <= start or end - start > timedelta(days=31):
        raise BusinessError("INVALID_TIME_RANGE", "时间范围须递增且不超过31天", 422)
    cap = limit if grain == "raw" else 10000
    rows = history_rows(session, point.id, start, end, cap)
    if grain != "raw" and len(rows) > cap:
        raise BusinessError("HISTORY_TOO_LARGE", "聚合原始数据超过1万条，请缩小范围", 413)
    if grain == "raw":
        items = [
            {
                "sampledAt": as_utc(r.sampled_at),
                "sourceSequence": str(r.source_sequence),
                "valueNumeric": r.value_numeric,
                "valueText": r.value_text,
                "quality": r.quality,
            }
            for r in rows[:limit]
        ]
        method = "raw"
        has_more = len(rows) > limit
    else:
        seconds = {"1m": 60, "5m": 300, "1h": 3600}[grain]
        buckets = {}
        # 同一采样时刻先保留最大源序号，避免同时间修订数据被重复计权。
        by_time = {r.sampled_at: r for r in rows}
        for row in by_time.values():
            key = int(as_utc(row.sampled_at).timestamp()) // seconds * seconds
            buckets.setdefault(key, []).append(row)
        from datetime import datetime, timezone

        items = []
        method = (
            "mean"
            if point.aggregation_type == "INSTANT" and point.value_type == "NUMERIC"
            else "last"
        )
        for key, values in sorted(buckets.items()):
            good = [r for r in values if r.quality == "GOOD"]
            if method == "mean":
                numbers = [r.value_numeric for r in good if r.value_numeric is not None]
                value = sum(numbers) / len(numbers) if numbers else None
                text = None
            else:
                last = values[-1]
                value = last.value_numeric if last.quality == "GOOD" else None
                text = last.value_text if last.quality == "GOOD" else None
            items.append(
                {
                    "sampledAt": datetime.fromtimestamp(key, timezone.utc),
                    "valueNumeric": value,
                    "valueText": text,
                    "quality": "GOOD"
                    if good and (value is not None or text is not None)
                    else "BAD",
                    "sampleCount": len(values),
                    "validCount": len(good),
                }
            )
        has_more = len(items) > limit
        items = items[:limit]
    return result(
        {
            "pointId": str(point.id),
            "unit": point.unit,
            "grain": grain,
            "aggregation": method,
            "items": items,
            "hasMore": has_more,
            "note": "缺口不补0；COUNTER聚合返回末值，不直接累加累计电量。",
        },
        settings,
    )


def create_point(session, settings, principal, device, body):
    """在已授权device内创建定义，校验编码唯一；不生成最新值或历史，不擅自绑定模型。"""
    require_writable(settings)
    if session.scalar(
        select(DevicePoint.id).where(
            DevicePoint.device_id == device.id, DevicePoint.code == body.code
        )
    ):
        raise BusinessError("POINT_DUPLICATE", "该设备下测点编码已存在", 409)
    fields = body.model_dump()
    fields["enabled"] = int(fields["enabled"])
    point = DevicePoint(site_id=device.site_id, device_id=device.id, **fields)
    session.add(point)
    session.flush()
    audit(
        session,
        principal,
        "monitor:create",
        "point",
        point.id,
        point.site_id,
        {"code": point.code, "unit": point.unit},
    )
    commit(session)
    return result(point_out(point), settings)


def configure_point(session, settings, principal, point_id, body):
    """完整替换采样配置；对既有非数值测点禁止数值阈值，历史与旧告警快照保持原样。"""
    require_writable(settings)
    point = require_point(session, principal, point_id)
    session.refresh(point, with_for_update=True)
    if point.value_type != "NUMERIC" and (
        body.alarm_low is not None or body.alarm_high is not None
    ):
        raise BusinessError("INVALID_POINT_CONFIG", "非数值测点不能配置数值阈值", 422)
    for key, value in body.model_dump().items():
        setattr(point, key, int(value) if key == "enabled" else value)
    audit(
        session,
        principal,
        "monitor:configure",
        "point",
        point.id,
        point.site_id,
        body.model_dump(by_alias=True),
    )
    commit(session)
    return result(point_out(point), settings)
