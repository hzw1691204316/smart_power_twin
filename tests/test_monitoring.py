"""监测闭环测试：独立SQLite仅测业务规则；实际MySQL另外验收，不接触用户库。"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.monitoring.models import PointHistory, PointLatest
from scripts.simulate_telemetry import make_sample, validate_api_url


def point(client, code="active_power", **kwargs):
    """在测试设备101创建测点；kwargs可指定单位/类型/阈值，返回API十进制字符串ID。"""
    body = {"code": code, "name": code, "unit": "kW", **kwargs}
    response = client.post("/api/v1/devices/101/points", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def sample(point_id, value=12.5, minutes=0, sequence=1, **kwargs):
    """返回带UTC毫秒时刻的采样；负minutes用于迟到/陈旧数据，kwargs用于质量/文本测试。"""
    time = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return {
        "pointId": point_id,
        "sampledAt": time.isoformat(timespec="milliseconds"),
        "sourceSequence": sequence,
        "valueNumeric": value,
        **kwargs,
    }


def send(client, *samples, source="SIMULATED"):
    """经真实HTTP业务入口提交整批，返回响应供验证成功或错误语义。"""
    return client.post(
        "/api/v1/telemetry/batches", json={"source": source, "samples": list(samples)}
    )


def history(client, point_id, grain="raw", **kwargs):
    """默认查UTC过去一天到未来1分钟，参数可覆盖时间/粒度/上限。"""
    now = datetime.now(timezone.utc)
    return client.get(
        f"/api/v1/points/{point_id}/history",
        params={
            "startTime": (now - timedelta(days=1)).isoformat(),
            "endTime": (now + timedelta(minutes=1)).isoformat(),
            "grain": grain,
            **kwargs,
        },
    )


def test_latest_missing_typed_and_stale(client):
    """无采样为空，正常0仍有值；陈旧与BAD质量相互独立。"""
    pid = point(client, staleAfterMs=10000)
    latest = client.get("/api/v1/devices/101/latest").json()["data"][0]
    assert latest["pointId"] == pid and latest["valueNumeric"] is None and latest["isStale"]
    assert send(client, sample(pid, 0, minutes=-10)).status_code == 200
    latest = client.get("/api/v1/devices/101/latest").json()["data"][0]
    assert latest["valueNumeric"] == 0 and latest["quality"] == "GOOD" and latest["isStale"]
    assert send(client, sample(pid, None, quality="BAD")).status_code == 200
    latest = client.get("/api/v1/devices/101/latest").json()["data"][0]
    assert latest["valueNumeric"] is None and latest["quality"] == "BAD" and not latest["isStale"]


def test_ingest_duplicate_conflict_and_whole_batch_rollback(client):
    """幂等重传不重复；相同身份不同内容409；后半批失败时撤销前半批历史与最新值。"""
    pid = point(client)
    entry = sample(pid, 8, sequence=9007199254740993)
    assert send(client, entry, entry).json()["data"] == {
        "inserted": 1,
        "duplicates": 1,
        "latestUpdated": 1,
        "source": "SIMULATED",
    }
    assert send(client, entry).json()["data"]["duplicates"] == 1
    changed = {**entry, "valueNumeric": 9}
    fresh = sample(pid, 20, minutes=-1, sequence=2)
    assert send(client, fresh, changed).status_code == 409
    assert history(client, pid).json()["data"]["items"][0]["sourceSequence"] == "9007199254740993"
    assert len(history(client, pid).json()["data"]["items"]) == 1
    assert client.get("/api/v1/devices/101/latest").json()["data"][0]["valueNumeric"] == 8


def test_late_samples_do_not_replace_latest_and_submillisecond_dedup(client):
    """按源时间/序号排序，迟到仅入历史；API时间统一到MySQL毫秒精度。"""
    pid = point(client)
    current = sample(pid, 30, sequence=3)
    assert send(client, current).status_code == 200
    assert send(client, sample(pid, 10, minutes=-2)).json()["data"]["latestUpdated"] == 0
    same_time = {**current, "sourceSequence": 4, "valueNumeric": 40}
    assert send(client, same_time).json()["data"]["latestUpdated"] == 1
    assert client.get("/api/v1/devices/101/latest").json()["data"][0]["valueNumeric"] == 40


@pytest.mark.parametrize("case", ["source", "text", "boolean", "future", "disabled", "both"])
def test_sample_validation(client, case):
    """来源、值类型、未来时间、停用和双值错误均不可部分入库。"""
    kwargs = (
        {"unit": "BOOL", "valueType": "BOOLEAN", "aggregationType": "STATE"}
        if case == "boolean"
        else {}
    )
    pid = point(client, **kwargs)
    entry = sample(pid, 3 if case == "boolean" else 10, minutes=10 if case == "future" else 0)
    if case in {"text", "both"}:
        entry["valueText"] = "错误文本"
        if case == "text":
            entry["valueNumeric"] = None
    if case == "disabled":
        assert (
            client.put(f"/api/v1/points/{pid}/config", json={"enabled": False}).status_code == 200
        )
    response = send(client, entry, source="FIELD" if case == "source" else "SIMULATED")
    assert response.status_code in (409, 422), response.text
    with Session(client.app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(PointHistory)) == 0
        assert session.scalar(select(func.count()).select_from(PointLatest)) == 0


def test_history_aggregation_limits_and_units(client):
    """瞬时值均值剔除BAD、累计取末值而不求和，时区与截断标志明确。"""
    pid = point(client)
    anchor = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(
        hours=1
    )
    entries = [
        {
            **sample(pid, value, sequence=i),
            "sampledAt": (anchor + timedelta(minutes=i)).isoformat(),
            "quality": quality,
        }
        for i, (value, quality) in enumerate([(10, "GOOD"), (None, "BAD"), (30, "GOOD")])
    ]
    assert send(client, *entries).status_code == 200
    data = history(client, pid, "1h").json()["data"]
    assert data["aggregation"] == "mean" and data["items"][0]["valueNumeric"] == 20
    assert data["items"][0]["validCount"] == 2
    assert history(client, pid, limit=1).json()["data"]["hasMore"]
    counter = point(client, "total_energy", unit="kWh", aggregationType="COUNTER")
    assert (
        send(
            client,
            *[
                {**e, "pointId": counter, "valueNumeric": 100 + i * 10, "quality": "GOOD"}
                for i, e in enumerate(entries)
            ],
        ).status_code
        == 200
    )
    assert history(client, counter, "1h").json()["data"]["items"][0]["valueNumeric"] == 120
    assert (
        history(
            client, pid, startTime="2026-10-01T00:00:00", endTime="2026-10-02T00:00:00Z"
        ).status_code
        == 422
    )
    assert (
        history(
            client, pid, startTime="2026-08-01T00:00:00Z", endTime="2026-10-02T00:00:00Z"
        ).status_code
        == 422
    )


def test_permission_scope_and_unused_modules(client):
    """观察员可读本站，不能写或看收费站；大屏汇总仍未启用。"""
    pid = point(client)
    login = client.post(
        "/api/v1/auth/login", json={"username": "fixture_viewer", "password": "FixtureViewer!2026"}
    )
    client.headers["Authorization"] = "Bearer " + login.json()["data"]["accessToken"]
    assert client.get("/api/v1/devices/101/latest").status_code == 200
    assert client.get("/api/v1/devices/201/latest").status_code == 404
    assert send(client, sample(pid)).status_code == 403
    assert client.put(f"/api/v1/points/{pid}/config", json={}).status_code == 403
    assert history(client, "18446744073709551615").status_code == 404
    assert client.get("/api/v1/alarms").status_code == 200
    assert client.get("/api/v1/scene-templates").status_code == 200
    assert client.get("/api/v1/dashboard/summary").status_code == 200


def test_simulator_local_scope_and_typed_counter():
    """模拟工具不接受远端凭据目标；沿当前累计表底递增，不编造未知测点。"""
    import argparse

    assert validate_api_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"
    for url in [
        "http://evil.test:8000",
        "http://127.0.0.1:8000/path",
        "http://user:password@localhost:8000",
    ]:
        with pytest.raises(argparse.ArgumentTypeError):
            validate_api_url(url)
    definition = {
        "id": "1001",
        "code": "total_energy",
        "valueType": "NUMERIC",
        "_counterBase": 12000,
    }
    now = datetime.now(timezone.utc)
    assert make_sample(definition, "PV_01", 0, now, 123)["valueNumeric"] == 12000.25
    assert make_sample({**definition, "code": "unknown"}, "PV_01", 0, now, 123) is None
