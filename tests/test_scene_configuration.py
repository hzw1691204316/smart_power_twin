"""从模板创建与对象维护的业务验收；使用隔离SQLite，真实MySQL并发另测。"""

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.assets.models import Site
from app.modules.system.models import AuditLog
from app.modules.twin.models import SceneTemplate, TwinBinding, TwinObject, TwinScene
from tests.test_twin import draft, input_bindings, scenes  # noqa: F401


def object_input(scene):
    """响应转对象维护白名单；不提交只读ID、父关系或模拟身份。"""
    return [
        {key: obj[key] for key in ("objectKey", "name", "deviceId")} for obj in scene["objects"]
    ]


def body(**updates):
    """本地中型服务区的一个储能对象；设备101属于站点1。"""
    return {
        "templateId": "1",
        "objects": [{"objectKey": "storage_01", "name": "储能设备", "deviceId": "101"}],
        **updates,
    }


def test_first_scene_create_edit_bind_publish_without_previous(scenes):  # noqa: F811
    """移除旧场景后验收新站首次发布；创建不自动生成绑定或测量值。"""
    with Session(scenes.app.state.engine) as session, session.begin():
        session.execute(delete(TwinBinding).where(TwinBinding.site_id == 1))
        session.execute(delete(TwinObject).where(TwinObject.site_id == 1))
        session.execute(delete(TwinScene).where(TwinScene.site_id == 1))
    response = scenes.post("/api/v1/sites/1/scenes/from-template", json=body())
    assert response.status_code == 201, response.text
    value = response.json()["data"]
    assert value["status"] == "DRAFT" and value["version"] == 1 and not value["bindings"]
    assert scenes.get("/api/v1/sites/1/scene").status_code == 404
    assert scenes.post(f"/api/v1/scenes/{value['id']}/publish").status_code == 409
    rows = object_input(value)
    rows[0]["name"] = "储能柜一号"
    saved = scenes.put(f"/api/v1/scenes/{value['id']}/objects", json={"objects": rows})
    assert (
        saved.status_code == 200
        and saved.json()["data"]["objects"][0]["id"] == value["objects"][0]["id"]
    )
    binding = {
        "objectId": value["objects"][0]["id"],
        "pointId": "10011",
        "propertyCode": "power_kw",
    }
    assert (
        scenes.put(
            f"/api/v1/scenes/{value['id']}/bindings", json={"bindings": [binding]}
        ).status_code
        == 200
    )
    assert scenes.post(f"/api/v1/scenes/{value['id']}/publish").status_code == 200
    assert scenes.get("/api/v1/sites/1/scene").json()["data"]["objects"][0]["name"] == "储能柜一号"
    assert (
        scenes.put(f"/api/v1/scenes/{value['id']}/objects", json={"objects": []}).status_code == 409
    )
    with Session(scenes.app.state.engine) as session:
        assert {"twin:create", "twin:objects", "twin:publish"} <= set(
            session.scalars(select(AuditLog.action))
        )


@pytest.mark.parametrize(
    "problem",
    ["device", "duplicate", "missing_key", "template", "extra", "inactive", "draft_template"],
)
def test_creation_rejection_is_atomic(scenes, problem):  # noqa: F811
    """不匹配、跨站、无资源/停用等失败不生成半个草稿。"""
    payload = body()
    if problem == "device":
        payload["objects"][0]["deviceId"] = "201"
    if problem == "duplicate":
        payload["objects"].append(payload["objects"][0].copy())
    if problem == "missing_key":
        payload["objects"][0]["objectKey"] = "absent"
    if problem == "template":
        payload["templateId"] = "2"
    if problem == "extra":
        payload["isDemo"] = False
    if problem in {"inactive", "draft_template"}:
        with Session(scenes.app.state.engine) as session, session.begin():
            if problem == "inactive":
                session.get(Site, 1).status = "INACTIVE"
            else:
                session.get(SceneTemplate, 1).status = "DRAFT"
    response = scenes.post("/api/v1/sites/1/scenes/from-template", json=payload)
    assert response.status_code in {409, 422}, response.text
    assert scenes.get("/api/v1/sites/1/scenes").json()["meta"]["total"] == 1
    assert scenes.get("/api/v1/sites/1/scene").json()["data"]["id"] == "10"


def test_object_replacement_preserves_bindings_and_rejects_device_change(scenes):  # noqa: F811
    """改显示名保留ID/父关系/绑定；换设备或删除绑定对象必须先清理绑定。"""
    value = draft(scenes)
    rows = object_input(value)
    rows[0]["name"] = "新的显示名"
    response = scenes.put(f"/api/v1/scenes/{value['id']}/objects", json={"objects": rows})
    assert response.status_code == 200, response.text
    saved = response.json()["data"]
    assert saved["bindings"] == value["bindings"]
    assert saved["objects"][1]["parentId"] == value["objects"][1]["parentId"]
    rows[0]["deviceId"] = "104"
    assert (
        scenes.put(f"/api/v1/scenes/{value['id']}/objects", json={"objects": rows}).status_code
        == 409
    )
    assert (
        scenes.put(f"/api/v1/scenes/{value['id']}/objects", json={"objects": []}).status_code == 409
    )
    assert scenes.get(f"/api/v1/scenes/{value['id']}").json()["data"] == saved
    remaining = [b for b in input_bindings(value) if b["objectId"] != value["objects"][0]["id"]]
    assert (
        scenes.put(
            f"/api/v1/scenes/{value['id']}/bindings", json={"bindings": remaining}
        ).status_code
        == 200
    )
    response = scenes.put(f"/api/v1/scenes/{value['id']}/objects", json={"objects": rows[1:]})
    assert response.status_code == 200 and response.json()["data"]["objects"][0]["parentId"] is None


def test_template_catalog_filters_invalid_keys_and_does_not_map_devices(scenes):  # noqa: F811
    with Session(scenes.app.state.engine) as session, session.begin():
        session.get(SceneTemplate, 1).resource_manifest_json = {
            "objectKeys": ["storage_01", "fake", 3, "storage_01"]
        }
    catalog = scenes.get("/api/v1/scene-templates/1/objects")
    assert catalog.status_code == 200 and catalog.json()["data"]["objectKeys"] == ["storage_01"]
    response = scenes.post("/api/v1/sites/1/scenes/from-template", json=body(objects=[]))
    assert response.status_code == 201 and not response.json()["data"]["objects"]


def test_viewer_cannot_create_or_edit_or_read_cross_site(scenes):  # noqa: F811
    value = draft(scenes)
    login = scenes.post(
        "/api/v1/auth/login", json={"username": "fixture_viewer", "password": "FixtureViewer!2026"}
    )
    scenes.headers["Authorization"] = "Bearer " + login.json()["data"]["accessToken"]
    assert scenes.get("/api/v1/scene-templates/1/objects").status_code == 200
    assert scenes.post("/api/v1/sites/1/scenes/from-template", json=body()).status_code == 403
    assert (
        scenes.put(f"/api/v1/scenes/{value['id']}/objects", json={"objects": []}).status_code == 403
    )
    assert scenes.get("/api/v1/sites/2/scenes").status_code == 404
