"""台账维护业务：动作权限在路由校验，范围/只读/同站关系在此再次检查；每次写入和审计同事务。"""

from sqlalchemy import select

from app.common.access import commit, find, require_site, require_writable, result
from app.core.exceptions import BusinessError
from app.modules.assets import maintenance_repository as repo
from app.modules.assets.models import Device, HighwayRoute, Site, SiteArea, SiteRouteLink
from app.modules.assets.repository import AssetRepository
from app.modules.assets.service import AssetService, numeric_id
from app.modules.system.models import UserSiteScope
from app.modules.system.service import audit
from app.modules.twin.models import TwinScene


def locked_scope(session, principal, site_id):
    """未授权/不存在均404；授权后重读锁定站点，保证本站写操作统一锁顺序。"""
    site = require_site(session, principal, site_id)
    return repo.lock_site(session, site.id)


def apply_primary(session, site, route_id):
    """设置一个主路线；空值只清主标记，不删除原方向、里程或其他路线关系。"""
    route = find(session, HighwayRoute, route_id) if route_id else None
    if route_id and (route is None or route.status != "ACTIVE"):
        raise BusinessError("ROUTE_NOT_FOUND", "主路线不存在或已停用", 404)
    links = repo.route_links(session, site.id)
    # 同一路线可能有上下行两条关联；保存普通站点资料时优先保留当前主方向，不能悄悄切到首条。
    preferred = next(
        (item for item in links if route and item.route_id == route.id and item.is_primary), None
    )
    for link in links:
        link.is_primary = 0
    if route:
        link = preferred or next((item for item in links if item.route_id == route.id), None)
        if link is None:
            link_code = f"ASSET_PRIMARY_{route.id}"
            if any(item.link_code == link_code for item in links):
                raise BusinessError(
                    "ROUTE_LINK_CONFLICT", "主路线关联编码冲突，请先核验原关系", 409
                )
            link = SiteRouteLink(
                site_id=site.id,
                route_id=route.id,
                link_code=link_code,
                direction_code="UNKNOWN",
                access_type="DIRECT",
            )
            session.add(link)
        link.is_primary = 1


def save_site(session, settings, principal, body, site_id=None):
    """site_id为空为新增，否则完整保存白名单资料；返回带路线的SiteOut。

    新站只为创建者添加该新站范围；已有场景冻结规模，身份列不在编辑协议中。
    停用不删除历史/场景，不自动级联停用设备；后续可恢复台账。
    """
    require_writable(settings)
    creating = site_id is None
    if creating:
        if session.scalar(select(Site.id).where(Site.code == body.code)):
            raise BusinessError("SITE_CODE_EXISTS", "站点编码已存在", 409)
        site = Site(
            code=body.code,
            name=body.name,
            site_type=body.site_type.value,
            scale_level=body.scale_level.value,
            is_demo=int(body.is_demo),
            province_code=body.province_code,
            coordinate_system="WGS84",
        )
        session.add(site)
    else:
        site = locked_scope(session, principal, site_id)
        if site.scale_level != body.scale_level.value and session.scalar(
            select(TwinScene.id).where(TwinScene.site_id == site.id).limit(1).with_for_update()
        ):
            raise BusinessError(
                "SCENE_SCALE_LOCKED", "已有三维场景，不能直接修改站点规模；请先完成场景迁移", 409
            )
        if site.coordinate_system != "WGS84" and (
            body.longitude is not None or body.latitude is not None
        ):
            raise BusinessError(
                "COORDINATE_MISMATCH", "原坐标不是WGS84，请先核验并转换，不可直接覆盖", 409
            )
    old_position = (site.longitude, site.latitude, site.location_source)
    fields = body.model_dump(exclude={"code", "site_type", "is_demo", "primary_route_id"})
    for key, value in fields.items():
        if key == "asset_status":
            site.status = value.value
        elif key == "scale_level":
            site.scale_level = value.value
        elif key == "province_code":
            site.province_code = value[:2] + "0000"
        else:
            setattr(site, key, value if value != "" else None)
    if old_position != (site.longitude, site.latitude, site.location_source):
        # 修改坐标或来源后必须重新核验，不能沿用原来的核验日期。
        site.location_verified_at = None
    # 唯一冲突由commit兜底；提前flush同样通过统一冲突处理，不能泄露驱动SQL。
    repo.flush(session)
    if creating:
        session.add(UserSiteScope(user_id=principal.user_id, site_id=site.id))
    if "primary_route_id" in body.model_fields_set:
        apply_primary(session, site, body.primary_route_id)
    audit(
        session,
        principal,
        "asset:site_create" if creating else "asset:site_update",
        "site",
        site.id,
        site.id,
        body.model_dump(mode="json", by_alias=True),
    )
    # 读取响应须在提交前构造，创建者授权在同事务中已添加；避免用请求旧范围漏掉刚建站点。
    service = AssetService(AssetRepository(session), settings.data_source)
    output = service.site_out(site, service.repository.routes_for_sites([site.id]).get(site.id, []))
    commit(session)
    return result(output, settings)


def save_device(session, settings, principal, site_id, body, device_id=None):
    """新增/编辑本站设备，校验区域与父链；设备身份固定、没有硬删除，返回DeviceOut。"""
    require_writable(settings)
    site = locked_scope(session, principal, site_id)
    creating = device_id is None
    if creating and site.status != "ACTIVE":
        raise BusinessError("SITE_INACTIVE", "停用或退役站点不能新增设备", 409)
    devices = repo.site_devices(session, site.id)
    if creating:
        if any(d.code == body.code for d in devices.values()):
            raise BusinessError("DEVICE_CODE_EXISTS", "站内设备编码已存在", 409)
        device = Device(
            site_id=site.id,
            code=body.code,
            name=body.name,
            device_type=body.device_type,
            system_type=body.system_type.value,
            is_demo=int(body.is_demo),
        )
        session.add(device)
    else:
        device = devices.get(numeric_id(device_id))
        if device is None:
            raise BusinessError("DEVICE_NOT_FOUND", "设备不存在或不属于本站", 404)
    area = find(session, SiteArea, body.area_id) if body.area_id else None
    if body.area_id and (area is None or area.site_id != site.id):
        raise BusinessError("AREA_NOT_FOUND", "区域不存在或不属于本站", 404)
    parent_id = numeric_id(body.parent_device_id) if body.parent_device_id else None
    if parent_id:
        seen = {device.id} if device.id else set()
        current = parent_id
        while current:
            if current in seen:
                raise BusinessError("DEVICE_PARENT_CYCLE", "父设备不能指向自身或形成循环", 409)
            seen.add(current)
            parent = devices.get(current)
            if parent is None:
                raise BusinessError("PARENT_NOT_FOUND", "父设备不存在或不属于本站", 404)
            current = parent.parent_device_id
    for key, value in body.model_dump(
        exclude={"code", "device_type", "system_type", "is_demo", "area_id", "parent_device_id"}
    ).items():
        if key == "asset_status":
            device.status = value.value
        else:
            setattr(device, key, value if value != "" else None)
    device.area_id = area.id if area else None
    device.parent_device_id = parent_id
    repo.flush(session)
    audit(
        session,
        principal,
        "asset:device_create" if creating else "asset:device_update",
        "device",
        device.id,
        site.id,
        body.model_dump(mode="json", by_alias=True),
    )
    output = AssetService(AssetRepository(session), settings.data_source).device_out(device)
    commit(session)
    return result(output, settings)
