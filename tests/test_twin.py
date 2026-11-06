"""三维场景业务验收：隔离SQLite测规则，MySQL另测事务/并发；不连接用户数据库。"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.time import utc_now
from app.modules.monitoring.models import DevicePoint
from app.modules.system.models import AuditLog
from app.modules.twin.models import SceneTemplate, TwinBinding, TwinObject, TwinScene

KEYS = ["storage_01", "transformer_01", "pv_canopy", "charger_01"]


@pytest.fixture
def scenes(client):
    """为两站各建当前版本、四对象、八绑定；ID故意与设备ID不同，父对象也随克隆迁移。"""
    with Session(client.app.state.engine) as session, session.begin():
        for site_id, kind, uri in [
            (1, "SERVICE", "/models/service_medium.glb"),
            (2, "TOLL", "/models/toll_medium.glb"),
        ]:
            template = SceneTemplate(
                id=site_id,
                template_code=kind + "_M",
                name=kind,
                site_type=kind,
                scale_level="M",
                version_no=1,
                status="PUBLISHED",
                model_uri=uri,
            )
            session.add(template)
            session.flush()
            scene = TwinScene(
                id=site_id * 10,
                site_id=site_id,
                site_type=kind,
                template_id=template.id,
                version_no=1,
                status="PUBLISHED",
                is_demo=1,
                published_at=utc_now(),
            )
            session.add(scene)
            session.flush()
            for offset, key in enumerate(KEYS, 1):
                obj = TwinObject(
                    id=site_id * 1000 + offset,
                    site_id=site_id,
                    scene_id=scene.id,
                    object_key=key,
                    name=key,
                    device_id=site_id * 100 + offset,
                    is_demo=1,
                )
                session.add(obj)
                session.flush()
                if offset == 2:
                    obj.parent_id = site_id * 1000 + 1
                for ordinal, (code, unit) in enumerate(
                    [("active_power", "kW"), ("temperature", "°C")], 1
                ):
                    p = DevicePoint(
                        id=site_id * 10000 + offset * 10 + ordinal,
                        site_id=site_id,
                        device_id=obj.device_id,
                        code=code,
                        name=code,
                        unit=unit,
                    )
                    session.add(p)
                    session.flush()
                    session.add(
                        TwinBinding(
                            site_id=site_id,
                            device_id=obj.device_id,
                            object_id=obj.id,
                            point_id=p.id,
                            property_code=code,
                        )
                    )
    return client


def draft(client):
    """复制服务区当前场景，返回新版本JSON；失败时仅输出脱敏API响应。"""
    response = client.post("/api/v1/sites/1/scenes", json={})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def input_bindings(scene):
    """将响应绑定转回完整替换协议，不携带只读名称/单位/数据库绑定ID。"""
    return [
        {k: b[k] for k in ("objectId", "pointId", "propertyCode", "mappingConfig")}
        for b in scene["bindings"]
    ]


def test_published_scene_uses_database_object_device_and_point_ids(scenes):
    scene = scenes.get("/api/v1/sites/1/scene").json()["data"]
    assert scene["modelUrl"] == "/models/service_medium.glb" and len(scene["bindings"]) == 8
    for obj in scene["objects"]:
        assert obj["id"] != obj["deviceId"] and obj["device"]["id"] == obj["deviceId"]
        assert obj["device"]["isDemo"] is True
        for binding in [b for b in scene["bindings"] if b["objectId"] == obj["id"]]:
            assert binding["deviceId"] == obj["deviceId"] and binding["unit"] in {"kW", "°C"}
    assert scenes.get("/api/v1/sites/999/scene").status_code == 404


def test_clone_preserves_current_and_copies_parent_and_binding_identity(scenes):
    old = scenes.get("/api/v1/sites/1/scene").json()["data"]
    new = draft(scenes)
    assert new["version"] == 2 and new["status"] == "DRAFT" and new["publishedAt"] is None
    assert scenes.get("/api/v1/sites/1/scene").json()["data"]["id"] == old["id"]
    assert {o["id"] for o in old["objects"]}.isdisjoint(o["id"] for o in new["objects"])
    first = next(o for o in new["objects"] if o["objectKey"] == KEYS[0])
    second = next(o for o in new["objects"] if o["objectKey"] == KEYS[1])
    assert second["parentId"] == first["id"]
    assert {b["objectId"] for b in new["bindings"]} == {o["id"] for o in new["objects"]}
    assert scenes.get("/api/v1/sites/1/scenes?pageSize=1").json()["meta"]["hasNext"] is True


@pytest.mark.parametrize("problem", ["site", "device", "duplicate", "oversize", "old_object"])
def test_replace_binding_rejects_invalid_full_set_without_deleting_old(scenes, problem):
    new = draft(scenes)
    rows = input_bindings(new)
    if problem == "site":
        rows[0]["pointId"] = "20011"
    if problem == "device":
        rows[0]["pointId"] = "10041"
    if problem == "duplicate":
        rows.append(rows[0].copy())
    if problem == "oversize":
        rows[0]["mappingConfig"] = {"note": "汉" * 3000}
    if problem == "old_object":
        rows[0]["objectId"] = "1001"
    response = scenes.put(f"/api/v1/scenes/{new['id']}/bindings", json={"bindings": rows})
    assert response.status_code == 422, response.text
    assert scenes.get(f"/api/v1/scenes/{new['id']}").json()["data"]["bindings"] == new["bindings"]


def test_save_publish_archive_retry_and_monitoring_relation(scenes):
    new = draft(scenes)
    rows = input_bindings(new)
    rows[0]["pointId"] = rows[1]["pointId"]  # 同一设备将展示属性改指向温度，证明属性名不决定测点。
    assert (
        scenes.put(f"/api/v1/scenes/{new['id']}/bindings", json={"bindings": rows}).status_code
        == 200
    )
    assert scenes.get("/api/v1/sites/1/scene").json()["data"]["id"] == "10"
    response = scenes.post(f"/api/v1/scenes/{new['id']}/publish")
    assert response.status_code == 200, response.text
    current = scenes.get("/api/v1/sites/1/scene").json()["data"]
    assert current["id"] == new["id"] and current["bindings"][0]["pointCode"] == "temperature"
    assert scenes.get("/api/v1/scenes/10").json()["data"]["status"] == "ARCHIVED"
    assert scenes.post(f"/api/v1/scenes/{new['id']}/publish").status_code == 200
    assert scenes.post("/api/v1/scenes/10/publish").status_code == 409
    assert (
        scenes.put(f"/api/v1/scenes/{new['id']}/bindings", json={"bindings": []}).status_code == 409
    )
    with Session(scenes.app.state.engine) as session:
        assert (
            len(session.scalars(select(AuditLog).where(AuditLog.action == "twin:publish")).all())
            == 1
        )


@pytest.mark.parametrize("problem", ["missing_key", "empty_bindings", "model_file", "transform"])
def test_failed_publish_keeps_previous_current(scenes, problem):
    new = draft(scenes)
    with Session(scenes.app.state.engine) as session, session.begin():
        scene = session.get(TwinScene, int(new["id"]))
        if problem == "model_file":
            scene.model_uri = "/models/not_present.glb"
        if problem in {"missing_key", "transform"}:
            obj = session.get(TwinObject, int(new["objects"][0]["id"]))
            if problem == "missing_key":
                obj.object_key = "missing_actual_mesh"
            else:
                obj.transform_json = {"position": [1, 2, 3]}
    if problem == "empty_bindings":
        assert (
            scenes.put(f"/api/v1/scenes/{new['id']}/bindings", json={"bindings": []}).status_code
            == 200
        )
    assert scenes.post(f"/api/v1/scenes/{new['id']}/publish").status_code == 409
    assert scenes.get("/api/v1/sites/1/scene").json()["data"]["id"] == "10"


def test_viewer_cannot_read_draft_publish_or_cross_site(scenes):
    new = draft(scenes)
    login = scenes.post(
        "/api/v1/auth/login", json={"username": "fixture_viewer", "password": "FixtureViewer!2026"}
    )
    scenes.headers["Authorization"] = "Bearer " + login.json()["data"]["accessToken"]
    assert scenes.get("/api/v1/sites/1/scene").status_code == 200
    assert scenes.get("/api/v1/sites/2/scene").status_code == 404
    assert scenes.get(f"/api/v1/scenes/{new['id']}").status_code == 404
    assert scenes.get("/api/v1/sites/1/scenes").json()["meta"]["total"] == 1
    assert scenes.post(f"/api/v1/scenes/{new['id']}/publish").status_code == 403


@pytest.mark.parametrize(
    "url", ["https://evil.test/model.glb", "/models/../x.glb", "/models/x.glb?x=1"]
)
def test_clone_rejects_unsafe_model_url(scenes, url):
    assert scenes.post("/api/v1/sites/1/scenes", json={"modelUrl": url}).status_code == 422
