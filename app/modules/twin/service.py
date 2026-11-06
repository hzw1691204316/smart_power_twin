"""三维业务：版本隔离、同设备绑定、GLB键校验与原子发布；模型继续由前端资源服务提供。"""

import json
import re
import struct

from sqlalchemy import delete, select

from app.common.access import commit, find, require_site, require_writable, result
from app.common.time import as_utc, utc_now
from app.core.config import PROJECT_ROOT
from app.core.exceptions import BusinessError
from app.modules.assets.models import Device, Site
from app.modules.monitoring.models import DevicePoint
from app.modules.system.service import audit
from app.modules.twin import repository
from app.modules.twin.models import SceneTemplate, TwinBinding, TwinObject, TwinScene


def require_scene(session, principal, scene_id):
    """返回已授权站点的场景版本；不存在或不在用户范围统一404。"""
    scene = find(session, TwinScene, scene_id)
    if (
        scene is None
        or scene.site_id not in principal.site_ids
        or (scene.status != "PUBLISHED" and "twin:publish" not in principal.permissions)
    ):
        raise BusinessError("SCENE_NOT_FOUND", "场景不存在或未授权")
    return scene


def scene_summary(session, scene):
    """返回版本身份/资源；scene为已授权ORM对象，modelUrl由本站覆盖或模板提供。"""
    template = session.get(SceneTemplate, scene.template_id)
    return {
        "id": str(scene.id),
        "siteId": str(scene.site_id),
        "templateId": str(scene.template_id),
        "version": scene.version_no,
        "status": scene.status,
        "isDemo": bool(scene.is_demo),
        "publishedAt": as_utc(scene.published_at),
        "modelUrl": scene.model_uri or template.model_uri,
    }


def scene_out(session, scene):
    """按当前版本批量关联设备/测点元数据，不读取最新值，不靠对象名或设备编码猜绑定。"""
    objects = repository.scene_objects(session, scene.id)
    bindings = repository.scene_bindings(session, scene.id)
    devices = {
        d.id: d
        for d in session.scalars(
            select(Device).where(Device.id.in_([o.device_id for o in objects if o.device_id]))
        )
    }
    points = {
        p.id: p
        for p in session.scalars(
            select(DevicePoint).where(DevicePoint.id.in_([b.point_id for b in bindings]))
        )
    }
    if any(d.site_id != scene.site_id for d in devices.values()) or any(
        b.point_id not in points
        or points[b.point_id].site_id != scene.site_id
        or points[b.point_id].device_id != b.device_id
        for b in bindings
    ):
        raise BusinessError("BINDING_MISMATCH", "场景数据归属不一致，请核对导入资料", 409)
    return {
        **scene_summary(session, scene),
        "objects": [
            {
                "id": str(o.id),
                "parentId": str(o.parent_id) if o.parent_id else None,
                "objectKey": o.object_key,
                "name": o.name,
                "deviceId": str(o.device_id) if o.device_id else None,
                "device": {
                    "id": str(devices[o.device_id].id),
                    "code": devices[o.device_id].code,
                    "name": devices[o.device_id].name,
                    "systemType": devices[o.device_id].system_type,
                    "assetStatus": devices[o.device_id].status,
                    "isDemo": bool(devices[o.device_id].is_demo),
                }
                if o.device_id in devices
                else None,
                "areaId": str(o.area_id) if o.area_id else None,
                "transform": o.transform_json,
                "isDemo": bool(o.is_demo),
            }
            for o in objects
        ],
        "bindings": [
            {
                "id": str(b.id),
                "objectId": str(b.object_id),
                "deviceId": str(b.device_id),
                "pointId": str(b.point_id),
                "propertyCode": b.property_code,
                "mappingConfig": b.mapping_config_json,
                "pointCode": points[b.point_id].code,
                "pointName": points[b.point_id].name,
                "unit": points[b.point_id].unit,
                "enabled": bool(points[b.point_id].enabled),
            }
            for b in bindings
        ],
    }


def clone(session, settings, principal, site_id, body):
    """从当前发布场景复制新DRAFT；对象和绑定获得新ID，旧发布版本保持可读。"""
    require_writable(settings)
    site = require_site(session, principal, site_id)
    session.refresh(site, with_for_update=True)
    current = repository.current_scene(session, site.id, lock=True)
    if current is None:
        raise BusinessError("SCENE_NOT_FOUND", "尚无可复制的发布场景")
    # MySQL默认可重复读：版本号必须使用锁定当前读，不能用旧事务快照的MAX造成并发重号。
    version = (
        session.scalar(
            select(TwinScene.version_no)
            .where(TwinScene.site_id == site.id)
            .order_by(TwinScene.version_no.desc())
            .limit(1)
            .with_for_update()
        )
        or 0
    ) + 1
    if version > 4294967295:
        raise BusinessError("VERSION_EXHAUSTED", "场景版本号已达上限", 409)
    if body.model_url:
        model_names(body.model_url)
    draft = TwinScene(
        site_id=site.id,
        site_type=site.site_type,
        template_id=current.template_id,
        version_no=version,
        status="DRAFT",
        is_demo=current.is_demo,
        model_uri=body.model_url or current.model_uri,
    )
    session.add(draft)
    session.flush()
    mapping = {}
    objects = repository.scene_objects(session, current.id, lock=True)
    for obj in objects:
        copy = TwinObject(
            site_id=site.id,
            scene_id=draft.id,
            object_key=obj.object_key,
            name=obj.name,
            device_id=obj.device_id,
            area_id=obj.area_id,
            transform_json=obj.transform_json,
            is_demo=obj.is_demo,
            model_uri=obj.model_uri,
        )
        session.add(copy)
        session.flush()
        mapping[obj.id] = copy
    for obj in objects:
        if obj.parent_id:
            mapping[obj.id].parent_id = mapping[obj.parent_id].id
    for binding in repository.scene_bindings(session, current.id, lock=True):
        session.add(
            TwinBinding(
                site_id=site.id,
                device_id=binding.device_id,
                object_id=mapping[binding.object_id].id,
                point_id=binding.point_id,
                property_code=binding.property_code,
                mapping_config_json=binding.mapping_config_json,
            )
        )
    audit(session, principal, "twin:clone", "scene", draft.id, site.id, {"version": version})
    commit(session)
    return result(scene_out(session, draft), settings)


def replace_bindings(session, settings, principal, scene_id, body):
    """完整替换DRAFT绑定；先校验全集再删除旧记录，拒绝跨场景、跨站、跨设备和重复属性。"""
    require_writable(settings)
    scene = require_scene(session, principal, scene_id)
    site = session.get(Site, scene.site_id)
    session.refresh(site, with_for_update=True)  # 所有场景写入统一按站点→场景顺序上锁。
    session.refresh(scene, with_for_update=True)
    if scene.status != "DRAFT":
        raise BusinessError("SCENE_IMMUTABLE", "已发布或归档场景不能编辑，请先复制草稿", 409)
    objects = {o.id: o for o in repository.scene_objects(session, scene.id, lock=True)}
    seen = set()
    rows = []
    for item in body.bindings:
        obj = objects.get(int(item.object_id))
        point = find(session, DevicePoint, item.point_id)
        if (
            obj is None
            or point is None
            or obj.device_id is None
            or point.site_id != scene.site_id
            or point.device_id != obj.device_id
        ):
            raise BusinessError("BINDING_MISMATCH", "对象和测点必须在本场景、同站且属于同设备", 422)
        key = (obj.id, item.property_code)
        if key in seen:
            raise BusinessError("BINDING_DUPLICATE", "同一对象属性不能重复绑定", 422)
        seen.add(key)
        if (
            item.mapping_config is not None
            and len(json.dumps(item.mapping_config, ensure_ascii=False).encode("utf-8")) > 8192
        ):
            raise BusinessError("MAPPING_TOO_LARGE", "显示映射最多8192字符", 422)
        rows.append(
            TwinBinding(
                site_id=scene.site_id,
                device_id=obj.device_id,
                object_id=obj.id,
                point_id=point.id,
                property_code=item.property_code,
                mapping_config_json=item.mapping_config,
            )
        )
    session.execute(delete(TwinBinding).where(TwinBinding.object_id.in_(objects)))
    session.add_all(rows)
    audit(
        session, principal, "twin:bindings", "scene", scene.id, scene.site_id, {"count": len(rows)}
    )
    commit(session)
    return result(scene_out(session, scene), settings)


def model_names(uri):
    """只解析前端/models目录下GLB的JSON块，返回节点名；拒绝任意路径、不下载外部资源。"""
    root = (PROJECT_ROOT / "smart_power_web/public/models").resolve()
    if not uri or not re.fullmatch(r"/models/[A-Za-z0-9_-]+\.glb", uri):
        raise BusinessError("MODEL_UNAVAILABLE", "缺少本站GLB资源", 409)
    path = (root / uri.removeprefix("/models/")).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != ".glb" or not path.is_file():
        raise BusinessError("MODEL_UNAVAILABLE", "GLB文件不存在或路径不合法", 409)
    try:
        with path.open("rb") as stream:
            magic, version, total = struct.unpack("<III", stream.read(12))
            size, kind = struct.unpack("<II", stream.read(8))
            if (
                magic != 0x46546C67
                or version != 2
                or kind != 0x4E4F534A
                or size > 16000000
                or total != path.stat().st_size
                or size + 20 > total
            ):
                raise ValueError("invalid GLB")
            data = json.loads(stream.read(size))
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("nodes", []), list)
            or any(
                not isinstance(node, dict) or not isinstance(node.get("name", ""), str)
                for node in data.get("nodes", [])
            )
        ):
            raise ValueError("invalid GLB nodes")
        return {node.get("name", "") for node in data.get("nodes", [])}
    except (OSError, ValueError, struct.error, TypeError):
        raise BusinessError("MODEL_INVALID", "无法解析GLB节点，请检查资源", 409) from None


def publish(session, settings, principal, scene_id):
    """校验类型、规模、资源键及绑定后原子发布；旧当前版本归档，数据库限制同站唯一发布。"""
    require_writable(settings)
    scene = require_scene(session, principal, scene_id)
    site = session.get(Site, scene.site_id)
    session.refresh(site, with_for_update=True)
    session.refresh(scene, with_for_update=True)
    if scene.status == "PUBLISHED":
        return result(scene_out(session, scene), settings)
    if scene.status != "DRAFT":
        raise BusinessError("SCENE_IMMUTABLE", "归档场景不能重新发布", 409)
    template = session.get(SceneTemplate, scene.template_id)
    if (
        template.site_type != site.site_type
        or scene.site_type != site.site_type
        or template.scale_level != site.scale_level
    ):
        raise BusinessError("TEMPLATE_MISMATCH", "站型或规模与模板不匹配", 409)
    if template.status != "PUBLISHED":
        raise BusinessError("TEMPLATE_UNPUBLISHED", "模板未发布，不能发布站点场景", 409)
    names = model_names(scene.model_uri or template.model_uri)
    objects = repository.scene_objects(session, scene.id)
    if not objects:
        raise BusinessError("SCENE_EMPTY", "场景无对象，不能发布", 409)
    for obj in objects:
        if obj.model_uri or (
            isinstance(obj.transform_json, dict)
            and any(k in obj.transform_json for k in ("position", "rotation", "scale"))
        ):
            raise BusinessError(
                "OBJECT_RESOURCE_UNSUPPORTED",
                "当前仅支持整场景GLB及其内置变换，不支持独立对象模型或JSON位姿覆盖",
                409,
            )
        if obj.device_id:
            device = session.get(Device, obj.device_id)
            if device is None or device.site_id != site.id:
                raise BusinessError("BINDING_MISMATCH", "对象设备归属不一致", 409)
            if obj.object_key not in names and not any(
                n.startswith(obj.object_key + "_") for n in names
            ):
                raise BusinessError("OBJECT_KEY_MISSING", f"GLB缺少对象键：{obj.object_key}", 409)
    by_id = {obj.id: obj for obj in objects}
    bindings = repository.scene_bindings(session, scene.id)
    if not bindings:
        raise BusinessError("SCENE_UNBOUND", "至少需要一个测点绑定", 409)
    for binding in bindings:
        point = session.get(DevicePoint, binding.point_id)
        obj = by_id[binding.object_id]
        if (
            point is None
            or point.site_id != site.id
            or point.device_id != obj.device_id
            or binding.device_id != obj.device_id
        ):
            raise BusinessError("BINDING_MISMATCH", "场景绑定归属不一致", 409)
    old = repository.current_scene(session, scene.site_id, lock=True)
    if old:
        old.status = "ARCHIVED"
        session.flush()
    scene.status = "PUBLISHED"
    scene.published_at = utc_now()
    audit(
        session,
        principal,
        "twin:publish",
        "scene",
        scene.id,
        scene.site_id,
        {"version": scene.version_no},
    )
    commit(session)
    return result(scene_out(session, scene), settings)
