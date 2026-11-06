"""告警闭环验收：采样质量/顺序/阈值、处置独立状态、事务回滚与范围，不连接用户库。"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.alarms.models import AlarmEvent
from app.modules.system.models import AuditLog
from tests.test_monitoring import point, sample, send


def events(client, **params):
    """读取筛选后的告警分页；断言接口成功再返回响应主体。"""
    response = client.get("/api/v1/alarms", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def raised(client):
    """创建0—50阈值点并用新鲜60触发，返回测点ID、采样及唯一事件。"""
    pid = point(client, alarmLow=0, alarmHigh=50)
    entry = sample(pid, 60)
    assert send(client, entry).status_code == 200
    return pid, entry, events(client)["data"][0]


def test_threshold_lifecycle_ack_recovery_close_and_recurrence(client):
    """持续异常只发生一次；确认不恢复，恢复不关闭，关闭后再次异常产生新事件。"""
    pid, entry, event = raised(client)
    eid = event["id"]
    assert event["source"] == "SIMULATED" and event["isDemo"]
    assert event["deviceId"] == "101" and event["pointId"] == pid
    assert event["triggerSnapshot"]["high"] == 50
    assert send(client, entry).json()["data"]["duplicates"] == 1
    assert send(client, sample(pid, 70, sequence=2)).status_code == 200
    assert events(client)["meta"]["total"] == 1
    assert client.post(f"/api/v1/alarms/{eid}/close", json={}).status_code == 409
    ack = client.post(f"/api/v1/alarms/{eid}/acknowledge", json={"handlingNote": "已检查"})
    assert ack.status_code == 200
    data = ack.json()["data"]
    assert data["status"] == "ACTIVE" and data["recoveredAt"] is None
    assert data["acknowledgedByName"] == "fixture_admin"
    assert (
        client.post(f"/api/v1/alarms/{eid}/acknowledge", json={"handlingNote": "不覆盖"}).json()[
            "data"
        ]
        == data
    )
    assert send(client, sample(pid, 50, sequence=3)).status_code == 200
    recovered = client.get(f"/api/v1/alarms/{eid}").json()["data"]
    assert recovered["status"] == "RECOVERED" and recovered["acknowledgedAt"]
    close = client.post(f"/api/v1/alarms/{eid}/close", json={"handlingNote": "恢复后关闭"})
    assert close.status_code == 200 and close.json()["data"]["status"] == "CLOSED"
    assert (
        client.post(f"/api/v1/alarms/{eid}/close", json={}).json()["data"] == close.json()["data"]
    )
    assert send(client, sample(pid, -1, sequence=4)).status_code == 200
    assert events(client)["meta"]["total"] == 2
    assert events(client, status="ACTIVE")["data"][0]["id"] != eid
    with Session(client.app.state.engine) as session:
        actions = session.scalars(
            select(AuditLog.action).where(AuditLog.action.like("alarm:%"))
        ).all()
        assert actions.count("alarm:raise") == 2
        assert (
            actions.count("alarm:recover")
            == actions.count("alarm:ack")
            == actions.count("alarm:close")
            == 1
        )


@pytest.mark.parametrize("quality", ["BAD", "SUSPECT", "MANUAL", "ESTIMATED"])
def test_low_quality_cannot_raise_or_recover(client, quality):
    """非GOOD既不产生阈值事件，也不能用来宣布已恢复。"""
    pid = point(client, alarmHigh=50)
    assert send(client, sample(pid, 70, quality=quality)).status_code == 200
    assert not events(client)["data"]
    assert send(client, sample(pid, 60, sequence=2)).status_code == 200
    assert send(client, sample(pid, 20, quality=quality, sequence=3)).status_code == 200
    assert events(client)["data"][0]["status"] == "ACTIVE"


def test_stale_future_late_and_disabled_thresholds_do_not_recover(client):
    """旧快照、未来样本、迟到历史及取消阈值均不冒充有效恢复。"""
    pid = point(client, alarmHigh=50, staleAfterMs=10000)
    assert send(client, sample(pid, 70, minutes=-10)).status_code == 200
    assert not events(client)["data"]
    entry = sample(pid, 60)
    assert send(client, entry).status_code == 200
    assert send(client, sample(pid, 10, minutes=-1)).status_code == 200
    assert events(client)["data"][0]["status"] == "ACTIVE"
    assert send(client, sample(pid, 10, minutes=1)).status_code == 200
    assert events(client)["data"][0]["status"] == "ACTIVE"
    # 未来最新值之后的当前样本属于迟到，不参与状态变更。
    assert send(client, sample(pid, 10, sequence=9)).status_code == 200
    assert events(client)["data"][0]["status"] == "ACTIVE"


def test_bounds_config_snapshot_and_recovery_before_ack(client):
    """等于上下限不触发；改单点配置不改发生快照；恢复后仍需确认才可关闭。"""
    pid = point(client, alarmLow=0, alarmHigh=50)
    for value in [0, 50]:
        assert send(client, sample(pid, value)).status_code == 200
    assert not events(client)["data"]
    assert send(client, sample(pid, 60)).status_code == 200
    eid = events(client)["data"][0]["id"]
    assert client.put(f"/api/v1/points/{pid}/config", json={"alarmHigh": 80}).status_code == 200
    assert events(client)["data"][0]["triggerSnapshot"]["high"] == 50
    assert send(client, sample(pid, 60)).status_code == 200
    assert events(client)["data"][0]["status"] == "RECOVERED"
    assert client.post(f"/api/v1/alarms/{eid}/close", json={}).status_code == 409
    assert client.post(f"/api/v1/alarms/{eid}/acknowledge", json={}).status_code == 200
    assert client.post(f"/api/v1/alarms/{eid}/close", json={}).status_code == 200
    # 禁用阈值不撤销已经触发的事件。
    assert send(client, sample(pid, 90)).status_code == 200
    assert client.put(f"/api/v1/points/{pid}/config", json={}).status_code == 200
    assert send(client, sample(pid, 10)).status_code == 200
    assert events(client, status="ACTIVE")["meta"]["total"] == 1


def test_batch_failure_rolls_back_alarm_history_latest_and_audit(client):
    """前条触发后后条采样校验失败，不能残留告警或告警审计。"""
    pid = point(client, alarmHigh=50)
    assert send(client, sample(pid, 60), sample(pid, None, sequence=2)).status_code == 422
    assert not events(client)["data"]
    assert client.get("/api/v1/devices/101/latest").json()["data"][0]["sampledAt"] is None
    with Session(client.app.state.engine) as session:
        assert (
            session.scalar(
                select(func.count()).select_from(AuditLog).where(AuditLog.action == "alarm:raise")
            )
            == 0
        )


def test_imported_events_not_recovered_and_station_level_supported(client):
    """无本引擎规则标记的历史/外部事件不自动恢复；站级告警无设备也能查询。"""
    pid = point(client, alarmHigh=50)
    now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    with Session(client.app.state.engine) as session, session.begin():
        session.add(
            AlarmEvent(
                site_id=1,
                device_id=101,
                point_id=int(pid),
                event_key="imported",
                raised_at=now,
                status="ACTIVE",
                message="导入事件",
                severity="MAJOR",
            )
        )
        session.add(
            AlarmEvent(
                site_id=2,
                event_key="station",
                raised_at=now,
                status="ACTIVE",
                message="站点事件",
                severity="INFO",
            )
        )
    assert send(client, sample(pid, 10)).status_code == 200
    assert events(client, siteId="1")["data"][0]["status"] == "ACTIVE"
    station = events(client, siteId="2")["data"][0]
    assert station["deviceId"] is station["pointId"] is None and station["source"] == "UNKNOWN"


def test_filters_pagination_scope_permissions_and_strict_action(client):
    """筛选总数与边界一致；viewer只读本站，额外动作字段422，越权资源不泄露。"""
    pid, _, event = raised(client)
    eid = event["id"]
    assert events(client, pointId=pid, deviceId="101", acknowledged=False)["meta"]["total"] == 1
    assert not events(client, acknowledged=True)["data"]
    assert events(client, page=2, pageSize=1)["meta"]["total"] == 1
    assert not events(client, severity="CRITICAL")["data"]
    assert events(client, startTime=event["raisedAt"])["meta"]["total"] == 1
    assert not events(client, endTime=event["raisedAt"])["data"]
    assert (
        client.get("/api/v1/alarms", params={"startTime": "2026-10-01T00:00:00"}).status_code == 422
    )
    assert (
        client.get(
            "/api/v1/alarms", params={"startTime": event["raisedAt"], "endTime": event["raisedAt"]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/alarms/{eid}/acknowledge", json={"recoveredAt": event["raisedAt"]}
        ).status_code
        == 422
    )
    login = client.post(
        "/api/v1/auth/login", json={"username": "fixture_viewer", "password": "FixtureViewer!2026"}
    )
    client.headers["Authorization"] = "Bearer " + login.json()["data"]["accessToken"]
    assert events(client)["meta"]["total"] == 1
    for params in [{"siteId": "2"}, {"deviceId": "201"}, {"pointId": "18446744073709551615"}]:
        assert client.get("/api/v1/alarms", params=params).status_code == 404
    assert client.post(f"/api/v1/alarms/{eid}/acknowledge", json={}).status_code == 403
    assert client.post(f"/api/v1/alarms/{eid}/close", json={}).status_code == 403
    assert client.get("/api/v1/alarms/18446744073709551615").status_code == 404


def test_read_only_action_and_no_alarm_read_permission(client):
    """写开关关闭时拒绝处置；撤销读取后查询403，不退回演示事件。"""
    _, _, event = raised(client)
    client.app.state.settings.data_source = "mysql"
    client.app.state.settings.mysql_allow_writes = False
    assert client.post(f"/api/v1/alarms/{event['id']}/acknowledge", json={}).status_code == 409
    from sqlalchemy import delete

    from app.modules.system.models import Permission, RolePermission

    with Session(client.app.state.engine) as session, session.begin():
        pid = session.scalar(select(Permission.id).where(Permission.code == "alarm:read"))
        session.execute(delete(RolePermission).where(RolePermission.permission_id == pid))
    assert client.get("/api/v1/alarms").status_code == 403
