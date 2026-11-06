"""场景创建与对象维护：复用19表，按站点锁串行分配版本；保存不影响已发布场景。"""

from sqlalchemy import delete, select

from app.common.access import commit, find, require_site, require_writable, result
from app.core.exceptions import BusinessError
from app.modules.assets.models import Device, Site
from app.modules.system.service import audit
from app.modules.twin import repository, service
from app.modules.twin.models import SceneTemplate, TwinObject, TwinScene


def require_template(session, template_id):
    """template_id为字符串主键；只允许已发布、有可解析GLB的模板，不自动注册资源。"""
    template = find(session, SceneTemplate, template_id)
    if template is None:
        raise BusinessError("TEMPLATE_NOT_FOUND", "模板不存在", 404)
    if template.status != "PUBLISHED":
        raise BusinessError("TEMPLATE_UNPUBLISHED", "模板尚未发布", 409)
    return template, service.model_names(template.model_uri)


def matches(key, names):
    """键必须精确命中GLB节点或其完整下划线前缀，与现有发布校验规则一致。"""
    return key in names or any(name.startswith(key + "_") for name in names)


def template_objects(session, settings, template_id):
    """返回经GLB复核的推荐键；清单只是候选，不赋予设备身份，也不返回任意文件内容。"""
    template, names = require_template(session, template_id)
    manifest = template.resource_manifest_json
    keys = manifest.get("objectKeys") if isinstance(manifest, dict) else None
    # 缺少人工清单时只推荐最外层下划线命名，避免把柜体螺丝、门板等数百子网格当成设备。
    candidates = (
        keys
        if isinstance(keys, list) and keys
        else [
            name
            for name in sorted(names)
            if not any(parent and name.startswith(parent + "_") for parent in names)
        ]
    )
    safe = sorted(
        {
            key
            for key in candidates
            if isinstance(key, str) and 0 < len(key) <= 100 and matches(key, names)
        }
    )
    return result({"templateId": str(template.id), "objectKeys": safe}, settings)


def validate_objects(session, site_id, items, names):
    """校验完整对象输入后返回设备映射；跨站设备、重复键和无效GLB键返回422，不写入。"""
    seen = set()
    devices = {}
    for item in items:
        if item.object_key in seen:
            raise BusinessError("OBJECT_DUPLICATE", "对象键不能重复", 422)
        seen.add(item.object_key)
        if not matches(item.object_key, names):
            raise BusinessError("OBJECT_KEY_MISSING", f"GLB缺少对象键：{item.object_key}", 422)
        if item.device_id:
            device = find(session, Device, item.device_id)
            if device is None or device.site_id != site_id:
                raise BusinessError("OBJECT_DEVICE_MISMATCH", "只能关联本站设备", 422)
            devices[item.object_key] = device
    return devices


def from_template(session, settings, principal, site_id, body):
    """新建DRAFT并配置对象；isDemo继承站点/设备，绑定为空，版本及审计在同一事务提交。"""
    require_writable(settings)
    site = require_site(session, principal, site_id)
    session.refresh(site, with_for_update=True)
    if site.status != "ACTIVE":
        raise BusinessError("SITE_INACTIVE", "停用站点不能新建场景", 409)
    template, names = require_template(session, body.template_id)
    if template.site_type != site.site_type or template.scale_level != site.scale_level:
        raise BusinessError("TEMPLATE_MISMATCH", "模板类型及规模必须与本站一致", 409)
    devices = validate_objects(session, site.id, body.objects, names)
    # 锁定当前读，避免MySQL可重复读快照下并发创建得到相同版本号。
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
    scene = TwinScene(
        site_id=site.id,
        site_type=site.site_type,
        template_id=template.id,
        version_no=version,
        status="DRAFT",
        is_demo=site.is_demo,
    )
    session.add(scene)
    session.flush()
    for item in body.objects:
        device = devices.get(item.object_key)
        session.add(
            TwinObject(
                site_id=site.id,
                scene_id=scene.id,
                object_key=item.object_key,
                name=item.name,
                device_id=device.id if device else None,
                is_demo=device.is_demo if device else site.is_demo,
            )
        )
    audit(
        session,
        principal,
        "twin:create",
        "scene",
        scene.id,
        site.id,
        {"templateId": str(template.id), "version": version, "objectCount": len(body.objects)},
    )
    commit(session)
    return result(service.scene_out(session, scene), settings)


def replace_objects(session, settings, principal, scene_id, body):
    """完整保存DRAFT对象；同键保留ID和父关系，绑定受影响时拒绝，避免静默丢失测点关系。"""
    require_writable(settings)
    scene = service.require_scene(session, principal, scene_id)
    site = session.get(Site, scene.site_id)
    session.refresh(site, with_for_update=True)
    session.refresh(scene, with_for_update=True)
    if scene.status != "DRAFT":
        raise BusinessError("SCENE_IMMUTABLE", "只能编辑草稿对象，请先复制或创建草稿", 409)
    names = service.model_names(
        scene.model_uri or session.get(SceneTemplate, scene.template_id).model_uri
    )
    devices = validate_objects(session, site.id, body.objects, names)
    existing = {o.object_key: o for o in repository.scene_objects(session, scene.id, lock=True)}
    incoming = {item.object_key: item for item in body.objects}
    bound_ids = {b.object_id for b in repository.scene_bindings(session, scene.id, lock=True)}
    for key, obj in existing.items():
        item = incoming.get(key)
        device = devices.get(key)
        if obj.id in bound_ids and (
            item is None or obj.device_id != (device.id if device else None)
        ):
            raise BusinessError(
                "OBJECT_HAS_BINDINGS",
                "对象已有测点绑定，请先移除并保存相关绑定，再删除或换设备",
                409,
            )
    removed = {obj.id for key, obj in existing.items() if key not in incoming}
    # 解除被删除父节点的引用；保留对象的ID和其余父关系，不依赖数据库级联删除。
    for obj in existing.values():
        if obj.parent_id in removed or obj.id in removed:
            obj.parent_id = None
    session.flush()
    if removed:
        session.execute(delete(TwinObject).where(TwinObject.id.in_(removed)))
    for item in body.objects:
        device = devices.get(item.object_key)
        obj = existing.get(item.object_key)
        if obj is None:
            obj = TwinObject(site_id=site.id, scene_id=scene.id, object_key=item.object_key)
            session.add(obj)
        obj.name = item.name
        obj.device_id = device.id if device else None
        obj.is_demo = device.is_demo if device else site.is_demo
    audit(
        session,
        principal,
        "twin:objects",
        "scene",
        scene.id,
        site.id,
        {"objectCount": len(body.objects)},
    )
    commit(session)
    return result(service.scene_out(session, scene), settings)
