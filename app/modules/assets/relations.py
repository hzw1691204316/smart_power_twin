"""站内区域和路线关联维护：站点锁+锁定当前读保护父链与主关联；审计与业务同事务。"""

from sqlalchemy import select

from app.common.access import commit, find, require_writable, result
from app.core.exceptions import BusinessError
from app.modules.assets import maintenance_repository as repo
from app.modules.assets.maintenance import locked_scope
from app.modules.assets.models import HighwayRoute, SiteArea, SiteRouteLink
from app.modules.assets.schemas import AreaOut
from app.modules.assets.service import AssetService, numeric_id
from app.modules.system.service import audit


def locked_areas(session, site_id):
    """调用前持有本站行锁；返回最新区域字典，避免MySQL RR旧快照漏掉并发父链修改。"""
    return {
        area.id: area
        for area in session.scalars(
            select(SiteArea)
            .where(SiteArea.site_id == site_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }


def area_out(area):
    """将区域ORM转换为统一响应，ID字符串化；无父区域用null。"""
    return AreaOut(
        id=str(area.id),
        site_id=str(area.site_id),
        parent_id=str(area.parent_id) if area.parent_id else None,
        code=area.code,
        name=area.name,
        area_type=area.area_type,
    )


def save_area(session, settings, principal, site_id, body, area_id=None):
    """area_id为空新增，否则保存既有区域；父链仅同站，不能自指/成环，不改设备归属。"""
    require_writable(settings)
    site = locked_scope(session, principal, site_id)
    areas = locked_areas(session, site.id)
    creating = area_id is None
    if creating:
        if site.status != "ACTIVE":
            raise BusinessError("SITE_INACTIVE", "停用站点不能新增区域", 409)
        if any(area.code == body.code for area in areas.values()):
            raise BusinessError("AREA_CODE_EXISTS", "本站区域编码已存在", 409)
        area = SiteArea(site_id=site.id, code=body.code)
    else:
        area = areas.get(numeric_id(area_id))
        if area is None:
            raise BusinessError("AREA_NOT_FOUND", "区域不存在或不属于本站", 404)
    parent_id = numeric_id(body.parent_id) if body.parent_id else None
    current, seen = parent_id, {area.id} if not creating else set()
    while current:
        if current in seen:
            raise BusinessError("AREA_PARENT_CYCLE", "父区域不能指向自身或形成循环", 409)
        seen.add(current)
        parent = areas.get(current)
        if parent is None:
            raise BusinessError("AREA_NOT_FOUND", "父区域不存在或不属于本站", 404)
        current = parent.parent_id
    before = area_out(area).model_dump(mode="json", by_alias=True) if not creating else None
    area.name, area.area_type, area.parent_id = body.name, body.area_type, parent_id
    session.add(area)
    repo.flush(session)
    audit(
        session,
        principal,
        "asset:area_create" if creating else "asset:area_update",
        "area",
        area.id,
        site.id,
        {"before": before, "after": body.model_dump(mode="json", by_alias=True)},
    )
    output = area_out(area)
    commit(session)
    return result(output, settings)


def save_route_link(session, settings, principal, site_id, body, link_id=None):
    """新建/编辑本站方向关联；已存在的停用路线允许保留资料，但不可新增或晋升为主关联。"""
    require_writable(settings)
    site = locked_scope(session, principal, site_id)
    links = repo.route_links(session, site.id)
    creating = link_id is None
    if creating:
        if site.status != "ACTIVE":
            raise BusinessError("SITE_INACTIVE", "停用站点不能新增路线关联", 409)
        if any(link.link_code == body.link_code for link in links):
            raise BusinessError("ROUTE_LINK_CODE_EXISTS", "本站关联编码已存在", 409)
        link = SiteRouteLink(site_id=site.id, link_code=body.link_code)
    else:
        link = next((row for row in links if row.id == numeric_id(link_id)), None)
        if link is None:
            raise BusinessError("ROUTE_LINK_NOT_FOUND", "路线关联不存在或不属于本站", 404)
    route = find(session, HighwayRoute, body.route_id)
    if route is None:
        raise BusinessError("ROUTE_NOT_FOUND", "路线不存在", 404)
    if route.status != "ACTIVE" and (
        creating or link.route_id != route.id or (body.is_primary and not link.is_primary)
    ):
        raise BusinessError("ROUTE_INACTIVE", "停用路线不能新增关联或设为主关联", 409)
    areas = locked_areas(session, site.id)
    area_id = numeric_id(body.area_id) if body.area_id else None
    if area_id and area_id not in areas:
        raise BusinessError("AREA_NOT_FOUND", "区域不存在或不属于本站", 404)
    before = (
        {
            "routeId": str(link.route_id),
            "isPrimary": bool(link.is_primary),
            "directionCode": link.direction_code,
            "areaId": str(link.area_id) if link.area_id else None,
            "chainageM": str(link.chainage_m) if link.chainage_m is not None else None,
            "directionLabel": link.direction_label,
            "accessType": link.access_type,
        }
        if not creating
        else None
    )
    if not body.is_primary and sum(bool(row.is_primary) for row in links if row is not link) > 1:
        raise BusinessError(
            "MULTIPLE_PRIMARY_LINKS", "原资料有多个主关联，请先明确选择一条主关联修复", 409
        )
    if body.is_primary:
        for row in links:
            row.is_primary = 0
    link.route_id, link.area_id = route.id, area_id
    link.direction_code, link.direction_label = body.direction_code, body.direction_label or None
    link.chainage_m, link.access_type, link.is_primary = (
        body.chainage_m,
        body.access_type,
        int(body.is_primary),
    )
    session.add(link)
    repo.flush(session)
    audit(
        session,
        principal,
        "asset:route_link_create" if creating else "asset:route_link_update",
        "site_route_link",
        link.id,
        site.id,
        {"before": before, "after": body.model_dump(mode="json", by_alias=True)},
    )
    output = AssetService.route_out(link, route)
    commit(session)
    return result(output, settings)
