"""只读汇总规则：来源隔离、质量/时间校验、唯一代表测点、显式缺数；不创建日计量结果。"""

from collections import defaultdict
from math import fsum, isfinite

from app.common.time import as_utc, utc_now
from app.modules.dashboard import repository

SYSTEMS = ("GRID", "PV", "ESS", "CHARGING")


def summarize(session, principal, province, city, site_id, source="FIELD"):
    """按授权范围和省市/站点交集统计；source仅筛选设备、功率及事件，台账站点总数不随来源改变。

    各站各系统只采用唯一启用active_power数值瞬时kW测点；停用站点/设备不参与功率。
    无数据返回None；负值保留（方向见点表），不把并网点功率称为负荷或计算能量平衡。
    """
    sites, devices, points, values, alarms = repository.records(
        session, principal.site_ids, province, city, site_id, source
    )
    now = utc_now()
    by_device = {d.id: d for d in devices}
    by_site = {s.id: s for s in sites}
    by_device_points = defaultdict(list)
    candidates = defaultdict(list)
    for point in points:
        by_device_points[point.device_id].append(point)
        device = by_device[point.device_id]
        # 先识别逻辑候选，单位或类型不对不能通过排除它来掩盖同系统的计量歧义。
        if point.enabled and point.code == "active_power" and device.status == "ACTIVE":
            candidates[(point.site_id, device.system_type)].append(point)

    def valid(point, numeric=False):
        """GOOD且时间落在[现在-陈旧阈值,现在]；0为有效值，NaN/无穷/空值不是有效采样。"""
        latest = values.get(point.id)
        if not point.enabled or not latest or latest.quality != "GOOD":
            return False
        age = (as_utc(now) - as_utc(latest.source_time)).total_seconds() * 1000
        if not 0 <= age <= point.stale_after_ms:
            return False
        if point.value_type == "TEXT" and not numeric:
            return latest.value_text is not None
        return latest.value_numeric is not None and isfinite(latest.value_numeric)

    warnings = {e.device_id for e in alarms if e.status == "ACTIVE" and e.device_id is not None}
    states = {"normal": 0, "warning": 0, "offline": 0, "unknown": 0}
    for device in devices:
        definitions = [p for p in by_device_points[device.id] if p.enabled]
        state = (
            "unknown"
            if device.status != "ACTIVE" or by_site[device.site_id].status != "ACTIVE"
            else "warning"
            if device.id in warnings
            else "unknown"
            if not definitions
            else "normal"
            if any(valid(p) for p in definitions)
            else "offline"
        )
        states[state] += 1
    active = [s for s in sites if s.status == "ACTIVE"]
    power = {}
    for system in SYSTEMS:
        numbers, times = [], []
        ambiguous = 0
        for site in active:
            eligible = candidates[(site.id, system)]
            if len(eligible) > 1:
                ambiguous += 1
                continue
            if len(eligible) != 1:
                continue
            point = eligible[0]
            if (
                point.unit != "kW"
                or point.value_type != "NUMERIC"
                or point.aggregation_type != "INSTANT"
                or not valid(point, numeric=True)
            ):
                continue
            numbers.append(values[point.id].value_numeric)
            times.append(as_utc(values[point.id].source_time))
        try:
            total = fsum(numbers) if numbers else None
        except OverflowError:
            total = None
        # 极端溢出结果不能输出非法JSON；不把任何数值截断或篡改为0。
        if total is not None and not isfinite(total):
            total = None
        power[system] = {
            "valueKw": total,
            "contributingSites": len(numbers),
            "ambiguousSites": ambiguous,
            "missingSites": len(active) - len(numbers),
            "isPartial": total is None or len(numbers) < len(active),
            "eligibleSites": len(active),
            "oldestSampledAt": min(times) if times else None,
            "newestSampledAt": max(times) if times else None,
        }
    return {
        "asOf": as_utc(now),
        "source": source,
        "siteCount": len(sites),
        "demoSiteCount": sum(bool(s.is_demo) for s in sites),
        "activeSiteCount": len(active),
        "serviceCount": sum(s.site_type == "SERVICE" for s in sites),
        "tollCount": sum(s.site_type == "TOLL" for s in sites),
        "deviceCount": len(devices),
        "deviceStates": states,
        "activeAlarmCount": sum(e.status == "ACTIVE" for e in alarms),
        "unacknowledgedAlarmCount": sum(e.acknowledged_at is None for e in alarms),
        "power": power,
        "dailyEnergyKwh": None,
        "note": "站点数为授权台账全量；设备、功率和事件仅含所选来源。各系统代表功率独立，缺测不当0、多候选不相加；GOOD且新鲜才计入，非同刻完整计量。日用电/自给率口径尚未配置。",
    }
