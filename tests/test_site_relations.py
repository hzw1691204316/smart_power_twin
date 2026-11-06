"""站内关系规则验收：父树、方向、主关联、只读/越权及资料保持；隔离MySQL另测锁和回滚。"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.assets.models import Device, HighwayRoute, Site, SiteRouteLink
from app.modules.system.models import AuditLog
from tests.test_asset_maintenance import site_edit
from tests.test_system import login_as


def area_body(**changes):
    """新区域；不传父区域表示顶层，编码和设备身份无关。"""
    return {
        "code": "NORTH_POWER",
        "name": "北侧配电房",
        "areaType": "POWER_ROOM",
        "parentId": None,
        **changes,
    }


def link_body(**changes):
    """路线关联使用真实查询ID；桩号字符串保留米制3位小数，不把0当未知。"""
    return {
        "linkCode": "S26_TEST_UP",
        "routeId": "1",
        "areaId": None,
        "directionCode": "UP",
        "directionLabel": "往郑州方向（测试）",
        "chainageM": "0",
        "accessType": "DIRECT",
        "isPrimary": True,
        **changes,
    }


def edit_body(body):
    """从创建白名单移除不可变编码，构造编辑输入。"""
    return {k: v for k, v in body.items() if k not in {"code", "linkCode"}}


def create_area(client, **changes):
    """返回新区域响应；不暴露数据库连接信息。"""
    response = client.post("/api/v1/sites/1/areas", json=area_body(**changes))
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_area_hierarchy_rename_and_existing_device_reference(client):
    root = create_area(client)
    child = create_area(client, code="NORTH_CHARGING", parentId=root["id"], name="北侧充电区")
    with Session(client.app.state.engine) as session, session.begin():
        session.get(Device, 101).area_id = int(child["id"])
    renamed = edit_body(area_body(name="北侧能源区"))
    assert client.put(f"/api/v1/sites/1/areas/{root['id']}", json=renamed).status_code == 200
    cycle = {**renamed, "parentId": child["id"]}
    assert client.put(f"/api/v1/sites/1/areas/{root['id']}", json=cycle).status_code == 409
    assert (
        client.put(
            f"/api/v1/sites/1/areas/{root['id']}", json={**renamed, "parentId": root["id"]}
        ).status_code
        == 409
    )
    assert client.get("/api/v1/sites/1/devices/101").json()["data"]["areaId"] == child["id"]
    areas = client.get("/api/v1/sites/1/areas").json()["data"]
    assert next(a for a in areas if a["id"] == root["id"])["parentId"] is None
    assert client.post("/api/v1/sites/1/areas", json=area_body()).status_code == 409


def test_cross_site_relations_and_viewer_cannot_write(client):
    root = create_area(client)
    other = client.get("/api/v1/sites/2/areas").json()["data"][0]["id"]
    assert (
        client.post(
            "/api/v1/sites/1/areas", json=area_body(code="BAD_PARENT", parentId=other)
        ).status_code
        == 404
    )
    assert (
        client.put(f"/api/v1/sites/2/areas/{root['id']}", json=edit_body(area_body())).status_code
        == 404
    )
    assert client.post("/api/v1/sites/1/routes", json=link_body(areaId=other)).status_code == 404
    headers = login_as(client)
    assert client.get("/api/v1/sites/1/areas", headers=headers).status_code == 200
    assert (
        client.post("/api/v1/sites/1/areas", json=area_body(), headers=headers).status_code == 403
    )
    assert (
        client.post("/api/v1/sites/1/routes", json=link_body(), headers=headers).status_code == 403
    )
    assert (
        client.put(
            f"/api/v1/sites/1/areas/{root['id']}", json=edit_body(area_body()), headers=headers
        ).status_code
        == 403
    )
    assert client.get("/api/v1/sites/2", headers=headers).status_code == 404


def test_primary_direction_survives_site_save_and_other_records_stay(client):
    up = client.post("/api/v1/sites/1/routes", json=link_body()).json()["data"]
    down_body = link_body(
        linkCode="S26_TEST_DOWN",
        directionCode="DOWN",
        chainageM="23456.125",
        directionLabel="往鹤壁方向",
    )
    down = client.post("/api/v1/sites/1/routes", json=down_body).json()["data"]
    assert down["chainageM"] == 23456.125 and up["chainageM"] == 0
    assert client.put("/api/v1/sites/1", json=site_edit(primaryRouteId="1")).status_code == 200
    links = client.get("/api/v1/sites/1").json()["data"]["routes"]
    assert [r["id"] for r in links if r["isPrimary"]] == [down["id"]]
    assert next(r for r in links if r["id"] == up["id"])["directionCode"] == "UP"
    response = client.put(
        f"/api/v1/sites/1/routes/{down['id']}",
        json=edit_body({**down_body, "isPrimary": False, "chainageM": None}),
    )
    assert response.status_code == 200 and response.json()["data"]["chainageM"] is None
    links = client.get("/api/v1/sites/1").json()["data"]["routes"]
    assert not any(r["isPrimary"] for r in links)
    assert {up["id"], down["id"]} <= {r["id"] for r in links}
    with Session(client.app.state.engine) as session:
        assert "asset:route_link_update" in set(session.scalars(select(AuditLog.action)))


@pytest.mark.parametrize(
    "change",
    [
        {"chainageM": "-1"},
        {"chainageM": "0.0001"},
        {"chainageM": "1000000000"},
        {"chainageM": "NaN"},
        {"directionCode": "NORTH"},
        {"accessType": "FAKE"},
        {"linkCode": "../BAD"},
        {"siteId": "2"},
    ],
)
def test_route_input_rejects_invalid_values_without_changing_primary(client, change):
    before = client.get("/api/v1/sites/1").json()["data"]["routes"]
    assert client.post("/api/v1/sites/1/routes", json=link_body(**change)).status_code == 422
    assert client.get("/api/v1/sites/1").json()["data"]["routes"] == before


def test_inactive_sites_routes_and_fixed_codes(client):
    area = create_area(client)
    response = client.post("/api/v1/sites/1/routes", json=link_body(isPrimary=False))
    link = response.json()["data"]
    assert client.post("/api/v1/sites/1/routes", json=link_body()).status_code == 409
    assert (
        client.put(f"/api/v1/sites/2/routes/{link['id']}", json=edit_body(link_body())).status_code
        == 404
    )
    assert client.put(f"/api/v1/sites/1/routes/{link['id']}", json=link_body()).status_code == 422
    assert client.put(f"/api/v1/sites/1/areas/{area['id']}", json=area_body()).status_code == 422
    with Session(client.app.state.engine) as session, session.begin():
        session.get(HighwayRoute, 1).status = "INACTIVE"
    assert (
        client.post("/api/v1/sites/1/routes", json=link_body(linkCode="NEW_ROUTE")).status_code
        == 409
    )
    assert (
        client.put(f"/api/v1/sites/1/routes/{link['id']}", json=edit_body(link_body())).status_code
        == 409
    )
    assert (
        client.put(
            f"/api/v1/sites/1/routes/{link['id']}", json=edit_body(link_body(isPrimary=False))
        ).status_code
        == 200
    )
    with Session(client.app.state.engine) as session, session.begin():
        session.get(Site, 1).status = "INACTIVE"
    assert client.post("/api/v1/sites/1/areas", json=area_body(code="LATE")).status_code == 409
    assert (
        client.put(f"/api/v1/sites/1/areas/{area['id']}", json=edit_body(area_body())).status_code
        == 200
    )


def test_legacy_multiple_primary_can_be_explicitly_repaired(client):
    extra = client.post("/api/v1/sites/1/routes", json=link_body(isPrimary=False)).json()["data"]
    third = client.post(
        "/api/v1/sites/1/routes", json=link_body(linkCode="THIRD", isPrimary=False)
    ).json()["data"]
    with Session(client.app.state.engine) as session, session.begin():
        for row in session.scalars(select(SiteRouteLink).where(SiteRouteLink.site_id == 1)):
            row.is_primary = 1
    assert (
        client.put(
            f"/api/v1/sites/1/routes/{extra['id']}", json=edit_body(link_body(isPrimary=False))
        ).status_code
        == 409
    )
    assert (
        client.put(f"/api/v1/sites/1/routes/{third['id']}", json=edit_body(link_body())).status_code
        == 200
    )
    links = client.get("/api/v1/sites/1").json()["data"]["routes"]
    assert [r["id"] for r in links if r["isPrimary"]] == [third["id"]]
