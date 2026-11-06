"""场景查询仓储：读取当前发布版本、对象与绑定；权限及发布校验交给service。"""

from sqlalchemy import func, select

from app.modules.twin.models import SceneTemplate, TwinBinding, TwinObject, TwinScene


def current_scene(session, site_id, lock=False):
    """返回本站唯一发布场景；写入时lock=True使用当前读，避免MySQL快照读到已归档版本。"""
    query = select(TwinScene).where(TwinScene.site_id == site_id, TwinScene.status == "PUBLISHED")
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return session.scalar(query)


def scene_objects(session, scene_id, lock=False):
    """返回scene_id内所有对象，按ID稳定排序；装饰对象device_id可以为空。"""
    query = select(TwinObject).where(TwinObject.scene_id == scene_id).order_by(TwinObject.id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return session.scalars(query).all()


def scene_bindings(session, scene_id, lock=False):
    """经对象连接读取指定场景绑定，不能仅按站点混入其他版本的绑定。"""
    query = (
        select(TwinBinding)
        .join(TwinObject, TwinBinding.object_id == TwinObject.id)
        .where(TwinObject.scene_id == scene_id)
        .order_by(TwinBinding.id)
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return session.scalars(query).all()


def scene_versions(session, site_id, include_drafts, page, page_size):
    """分页列本站版本；普通读取者仅见当前发布，管理者可见草稿/归档。返回行及总数。"""
    clauses = [TwinScene.site_id == site_id]
    if not include_drafts:
        clauses.append(TwinScene.status == "PUBLISHED")
    total = session.scalar(select(func.count()).select_from(TwinScene).where(*clauses))
    rows = session.scalars(
        select(TwinScene)
        .where(*clauses)
        .order_by(TwinScene.version_no.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return rows, total


def templates(session):
    """返回六类模板和版本目录；DRAFT且model_uri为空的条目代表未制作，不伪造文件。"""
    return session.scalars(
        select(SceneTemplate).order_by(SceneTemplate.template_code, SceneTemplate.version_no.desc())
    ).all()
