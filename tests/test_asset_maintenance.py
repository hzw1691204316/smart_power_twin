"""台账维护规则验收：创建范围、不可变身份、关系、停用、权限和事务；不连接用户库。"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.assets.models import Site
from app.modules.system.models import AuditLog
from tests.test_system import login_as
from tests.test_twin import scenes  # noqa: F401


def site_body(**changes):
    """构造无坐标模拟站点；业务身份明确，字段含义见维护Schemas。"""
    return dict(
        code="NEW_SITE",
        name="新增服务区",
        siteType="SERVICE",
        scaleLevel="L",
        provinceCode="41",
        cityName="郑州市",
        longitude=None,
        latitude=None,
        isDemo=True,
        assetStatus="ACTIVE",
        **changes,
    )


def device_body(**changes):
    """构造本站模拟设备，不创建任何测点。"""
    return dict(
        code="NEW_DEVICE",
        name="储能柜",
        deviceType="ESS_CABINET",
        systemType="ESS",
        isDemo=True,
        assetStatus="ACTIVE",
        **changes,
    )


def site_edit(**changes):
    """完整替换可编辑资料；不含编码、站型及来源。"""
    return dict(
        name="修改服务区",
        scaleLevel="M",
        provinceCode="410000",
        cityName="鹤壁市",
        assetStatus="ACTIVE",
        **changes,
    )


def device_edit(**changes):
    """设备可编辑资料输入，额定字段和空父关系由调用者补充。"""
    return dict(name="修改设备", assetStatus="ACTIVE", **changes)


def test_create_site_scope_audit_and_duplicate(client):
    response = client.post("/api/v1/sites", json=site_body(primaryRouteId="1"))
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    sid = data["id"]
    assert data["provinceCode"] == "410000" and data["scaleLevel"] == "L" and data["isDemo"]
    assert data["routes"][0]["isPrimary"]
    assert client.get("/api/v1/sites/" + sid).status_code == 200
    assert sid in client.get("/api/v1/auth/me").json()["data"]["siteIds"]
    assert client.get("/api/v1/sites/" + sid, headers=login_as(client)).status_code == 404
    assert client.post("/api/v1/sites", json=site_body()).status_code == 409
    with Session(client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Site)) == 3
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "asset:site_create")
            )
            == 1
        )
    # 新台账没有假设备、测点或场景。
    assert client.get(f"/api/v1/sites/{sid}/devices").json()["meta"]["total"] == 0
    assert client.get(f"/api/v1/sites/{sid}/scene").status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        {"longitude": 113.5},
        {"longitude": "181", "latitude": "30"},
        {"provinceCode": "410100"},
        {"name": "  "},
        {"code": "../BAD"},
        {"id": "99"},
    ],
)
def test_site_input_validation(client, change):
    body = site_body()
    body.update(change)
    assert client.post("/api/v1/sites", json=body).status_code == 422


def test_site_edit_keeps_identity_and_relations(client):
    from app.common.time import utc_now

    with Session(client.app.state.engine) as db, db.begin():
        db.get(Site, 1).location_verified_at = utc_now()
    response = client.put(
        "/api/v1/sites/1", json=site_edit(primaryRouteId="1", longitude="114.22", latitude="35.66")
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["code"] == "HEBI_CHAOGE_SERVICE_DEMO"
    with Session(client.app.state.engine) as db:
        assert db.get(Site, 1).location_verified_at is None
    assert client.put("/api/v1/sites/1", json={**site_edit(), "isDemo": False}).status_code == 422
    assert client.put("/api/v1/sites/1", json=site_edit(primaryRouteId="999")).status_code == 404
    assert client.get("/api/v1/sites/1").json()["data"]["longitude"] == 114.22
    assert (
        client.put("/api/v1/sites/2", json=site_edit(), headers=login_as(client)).status_code == 403
    )


def test_device_create_edit_and_same_site_constraints(client):
    response = client.post(
        "/api/v1/sites/1/devices",
        json=device_body(
            areaId="101", parentDeviceId="102", ratedPowerKw="0", ratedEnergyKwh="215.5000"
        ),
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    did = data["id"]
    assert data["ratedPowerKw"] == 0 and data["ratedEnergyKwh"] == 215.5 and data["siteId"] == "1"
    assert client.post("/api/v1/sites/1/devices", json=device_body()).status_code == 409
    assert client.put(f"/api/v1/sites/2/devices/{did}", json=device_edit()).status_code == 404
    assert (
        client.put(f"/api/v1/sites/1/devices/{did}", json=device_edit(areaId="201")).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/v1/sites/1/devices/{did}", json=device_edit(parentDeviceId="202")
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/v1/sites/1/devices/{did}", json=device_edit(parentDeviceId=did)
        ).status_code
        == 409
    )
    # 修改102的父设备为其子设备，形成环时拒绝且原父关系不变。
    assert (
        client.put("/api/v1/sites/1/devices/102", json=device_edit(parentDeviceId=did)).status_code
        == 409
    )
    assert (
        client.put(
            f"/api/v1/sites/1/devices/{did}", json=device_edit(ratedEnergyKwh="300")
        ).status_code
        == 200
    )
    assert client.get(f"/api/v1/sites/1/devices/{did}").json()["data"]["ratedEnergyKwh"] == 300
    assert (
        client.put(
            f"/api/v1/sites/1/devices/{did}", json={**device_edit(), "code": "CHANGED"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/sites/1/devices", json={**device_body(), "ratedPowerKw": -1}
        ).status_code
        == 422
    )


def test_lifecycle_no_deletion_and_readonly(client):
    response = client.put("/api/v1/sites/1", json={**site_edit(), "assetStatus": "INACTIVE"})
    assert response.status_code == 200
    assert client.post("/api/v1/sites/1/devices", json=device_body()).status_code == 409
    assert client.get("/api/v1/sites/1/devices").json()["meta"]["total"] == 4
    assert (
        client.put(
            "/api/v1/sites/1/devices/101", json={**device_edit(), "assetStatus": "MAINTENANCE"}
        ).status_code
        == 200
    )
    assert client.app.state.settings.data_source == "test"
    old = client.app.state.settings
    client.app.state.settings = old.model_copy(
        update={"data_source": "mysql", "mysql_allow_writes": False}
    )
    try:
        assert client.put("/api/v1/sites/1", json=site_edit()).status_code == 409
        assert client.post("/api/v1/sites", json=site_body()).status_code == 409
    finally:
        client.app.state.settings = old


def test_scale_freeze_for_existing_scene(scenes):  # noqa: F811 - pytest复用导入fixture
    assert scenes.put("/api/v1/sites/1", json={**site_edit(), "scaleLevel": "L"}).status_code == 409
    assert scenes.get("/api/v1/sites/1/scene").status_code == 200


def test_failed_new_site_rolls_back_scope_and_identity(client):
    result = client.post("/api/v1/sites", json=site_body(primaryRouteId="999"))
    assert result.status_code == 404
    assert len(client.get("/api/v1/auth/me").json()["data"]["siteIds"]) == 2
    assert client.get("/api/v1/sites?q=NEW_SITE").json()["meta"]["total"] == 0


def test_viewer_cannot_write_and_no_hard_delete(client):
    headers = login_as(client)
    assert client.post("/api/v1/sites", json=site_body(), headers=headers).status_code == 403
    assert (
        client.post("/api/v1/sites/1/devices", json=device_body(), headers=headers).status_code
        == 403
    )
    assert client.delete("/api/v1/sites/1").status_code == 405


def test_primary_route_changes_preserve_all_original_links(client):
    """更换主路线只调整主标记，不能覆盖前一次新建的路线关系。"""
    from app.modules.assets.models import HighwayRoute

    with Session(client.app.state.engine) as db, db.begin():
        db.add_all(
            [
                HighwayRoute(id=2, route_code="G4", name="G4"),
                HighwayRoute(id=3, route_code="G30", name="G30"),
            ]
        )
    for route in ["2", "3", "1"]:
        result = client.put("/api/v1/sites/1", json=site_edit(primaryRouteId=route))
        assert result.status_code == 200, result.text
    links = result.json()["data"]["routes"]
    assert {r["routeId"] for r in links} == {"1", "2", "3"}
    assert [r["routeId"] for r in links if r["isPrimary"]] == ["1"]
