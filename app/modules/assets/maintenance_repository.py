"""维护仓储：本站写入按站点行锁串行，减少父设备成环、主路线竞争；事务由业务层提交。"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import BusinessError
from app.modules.assets.models import Device, Site, SiteRouteLink


def lock_site(session, site_id):
    """读取站点最新锁定行；所有本站维护操作先锁site，再改子记录，统一锁顺序。"""
    return session.scalar(
        select(Site)
        .where(Site.id == site_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def site_devices(session, site_id):
    """返回本站设备身份字典，用于归属和完整父链环校验；调用前必须持有站点锁。"""
    return {
        d.id: d
        for d in session.scalars(
            select(Device)
            .where(Device.site_id == site_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }


def route_links(session, site_id):
    """返回本站路线关系，不删除旧路线或方向资料。"""
    return list(
        session.scalars(
            select(SiteRouteLink)
            .where(SiteRouteLink.site_id == site_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )


def flush(session):
    """在需要自增ID时刷新，唯一/归属冲突返回409并回滚整个事务，不泄露驱动SQL。"""
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise BusinessError("ASSET_CONFLICT", "编码或归属约束冲突，请刷新后重试", 409) from None
