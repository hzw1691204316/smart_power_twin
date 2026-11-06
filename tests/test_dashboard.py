"""汇总验收：来源隔离、权限/范围、计量歧义与质量时间边界，不接触用户MySQL。"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.common.time import utc_now
from app.modules.alarms.models import AlarmEvent
from app.modules.assets.models import Device, Site
from app.modules.monitoring.models import DevicePoint, PointLatest
from app.modules.system.models import Permission, RolePermission, UserSiteScope
from tests.test_system import login_as


def summary(client, **params):
    """默认查询模拟来源并断言成功；返回大屏数据，测试来源缺省时另行直接请求。"""
    result = client.get("/api/v1/dashboard/summary", params={"source": "SIMULATED", **params})
    assert result.status_code == 200, result.text
    return result.json()["data"]


def reading(client, device_id=102, value=12.5, **changes):
    """向隔离库写可控定义和最新值，changes可指定质量/时间/单位/启用；无HTTP采集副作用。"""
    now = utc_now()
    with Session(client.app.state.engine) as db, db.begin():
        device = db.get(Device, device_id)
        p = DevicePoint(
            site_id=device.site_id,
            device_id=device_id,
            code="active_power",
            name="功率",
            unit=changes.get("unit", "kW"),
            enabled=changes.get("enabled", 1),
            value_type=changes.get("value_type", "NUMERIC"),
            aggregation_type=changes.get("aggregation_type", "INSTANT"),
            stale_after_ms=15000,
        )
        db.add(p)
        db.flush()
        db.add(
            PointLatest(
                point_id=p.id,
                source_time=changes.get("time", now),
                received_time=now,
                value_numeric=value,
                quality=changes.get("quality", "GOOD"),
            )
        )
        return p.id


def test_empty_scope_and_null_not_zero(client):
    data = summary(client)
    assert data["siteCount"] == 2 and data["demoSiteCount"] == 2 and data["deviceCount"] == 8
    assert data["dailyEnergyKwh"] is None and data["deviceStates"]["unknown"] == 8
    assert all(
        p["valueKw"] is None and p["missingSites"] == 2 and p["isPartial"]
        for p in data["power"].values()
    )
    empty = summary(client, provinceCode="370000")
    assert (
        empty["siteCount"] == 0
        and empty["deviceCount"] == 0
        and empty["power"]["GRID"]["valueKw"] is None
    )
    assert summary(client, provinceCode="41")["siteCount"] == 2
    assert summary(client, cityName="鹤壁市")["siteCount"] == 2
    assert summary(client, provinceCode="37", cityName="鹤壁")["siteCount"] == 0


def test_zero_negative_and_source_separation(client):
    reading(client, 102, 0)
    reading(client, 202, -8)
    data = summary(client)["power"]["GRID"]
    assert data["valueKw"] == -8 and data["contributingSites"] == 2 and not data["isPartial"]
    assert data["oldestSampledAt"] and data["newestSampledAt"]
    with Session(client.app.state.engine) as db, db.begin():
        db.get(Device, 202).is_demo = 0
    assert summary(client)["power"]["GRID"]["valueKw"] == 0
    field = client.get("/api/v1/dashboard/summary").json()["data"]
    assert (
        field["source"] == "FIELD"
        and field["deviceCount"] == 1
        and field["power"]["GRID"]["valueKw"] == -8
    )
    assert field["siteCount"] == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"quality": "BAD"},
        {"quality": "MANUAL"},
        {"unit": "W"},
        {"enabled": 0},
        {"aggregation_type": "COUNTER"},
        {"value_type": "TEXT"},
        {"time": "old"},
        {"time": "future"},
    ],
)
def test_bad_or_stale_or_future_not_counted(client, changes):
    if changes.get("time") == "old":
        changes["time"] = utc_now() - timedelta(minutes=1)
    if changes.get("time") == "future":
        changes["time"] = utc_now() + timedelta(minutes=1)
    reading(client, **changes)
    assert summary(client)["power"]["GRID"]["valueKw"] is None


def test_stale_boundary_and_duplicate_candidates(client):
    fixed = utc_now()
    reading(client, time=fixed - timedelta(seconds=15))
    with patch("app.modules.dashboard.service.utc_now", return_value=fixed):
        assert summary(client)["power"]["GRID"]["valueKw"] == 12.5
    # 同站同系统第二计量点即使质量坏或单位错误，仍构成歧义，不能静默挑一个相加。
    with Session(client.app.state.engine) as db, db.begin():
        db.get(Device, 104).system_type = "GRID"
    reading(client, 104, 100, unit="W", quality="BAD")
    data = summary(client)["power"]["GRID"]
    assert data["valueKw"] is None and data["ambiguousSites"] == 1 and data["missingSites"] == 2


def test_inactive_device_site_and_numeric_null(client):
    reading(client, 102, None)
    assert summary(client)["power"]["GRID"]["valueKw"] is None
    with Session(client.app.state.engine) as db, db.begin():
        db.scalar(select(PointLatest)).value_numeric = 10
        db.get(Device, 102).status = "MAINTENANCE"
    assert summary(client)["power"]["GRID"]["valueKw"] is None
    with Session(client.app.state.engine) as db, db.begin():
        db.get(Device, 102).status = "ACTIVE"
        db.get(Site, 1).status = "INACTIVE"
    data = summary(client)
    assert data["activeSiteCount"] == 1 and data["power"]["GRID"]["valueKw"] is None


def test_scope_permission_and_query_validation(client):
    reading(client, 102, 8)
    reading(client, 202, 999)
    headers = login_as(client)
    viewer = client.get("/api/v1/dashboard/summary?source=SIMULATED", headers=headers).json()[
        "data"
    ]
    assert viewer["siteCount"] == 1 and viewer["power"]["GRID"]["valueKw"] == 8
    assert client.get("/api/v1/dashboard/summary?siteId=2", headers=headers).status_code == 404
    assert client.get("/api/v1/dashboard/summary?siteId=18446744073709551615").status_code == 404
    for query in ["source=ALL", "siteId=0", "provinceCode=410100", "cityName=%20%20"]:
        assert client.get("/api/v1/dashboard/summary?" + query).status_code == 422
    assert client.get("/api/v1/dashboard/summary", headers={"Authorization": ""}).status_code == 401
    with Session(client.app.state.engine) as db, db.begin():
        pid = db.scalar(select(Permission.id).where(Permission.code == "dashboard:read"))
        db.execute(
            delete(RolePermission).where(
                RolePermission.role_id == 2, RolePermission.permission_id == pid
            )
        )
    assert client.get("/api/v1/dashboard/summary", headers=headers).status_code == 403


def test_alarm_counts_recovery_ack_and_source(client):
    now = utc_now()
    with Session(client.app.state.engine) as db, db.begin():
        for device, status, ack in [
            (102, "ACTIVE", now),
            (103, "RECOVERED", None),
            (202, "ACTIVE", None),
            (204, "CLOSED", None),
        ]:
            db.add(
                AlarmEvent(
                    site_id=1 if device < 200 else 2,
                    device_id=device,
                    severity="MINOR",
                    event_key=f"dashboard-event-{device}",
                    message="event",
                    status=status,
                    raised_at=now,
                    acknowledged_at=ack,
                )
            )
    data = summary(client)
    assert data["activeAlarmCount"] == 2 and data["unacknowledgedAlarmCount"] == 2
    assert data["deviceStates"]["warning"] == 2
    viewer = client.get(
        "/api/v1/dashboard/summary?source=SIMULATED", headers=login_as(client)
    ).json()["data"]
    assert viewer["activeAlarmCount"] == 1 and viewer["unacknowledgedAlarmCount"] == 1
    assert client.get("/api/v1/dashboard/summary").json()["data"]["activeAlarmCount"] == 0


def test_empty_authorization_and_read_only_no_write(client):
    with Session(client.app.state.engine) as db, db.begin():
        db.execute(delete(UserSiteScope))
    assert summary(client)["siteCount"] == 0
