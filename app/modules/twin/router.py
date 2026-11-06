"""三维场景接口：读当前场景、复制草稿、替换绑定和发布，按站点及动作分别鉴权。"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_session, require_permission
from app.common.access import PathId, paged, require_site, result
from app.common.pagination import Page, Result
from app.core.exceptions import BusinessError
from app.modules.twin import configuration, repository, service
from app.modules.twin.schemas import (
    BindingsIn,
    CloneIn,
    FromTemplateIn,
    ObjectsIn,
    SceneOut,
    SceneSummary,
    TemplateObjectsOut,
    TemplateOut,
)

router = APIRouter(tags=["三维场景与绑定"])


@router.get(
    "/scene-templates", response_model=Result[list[TemplateOut]], summary="六类模板与资源制作状态"
)
def templates(
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("twin:read")),
):
    """返回模板制作状态；中型及已手动注册的大型服务区可用，未制作资源保持DRAFT。"""
    return result(
        [
            {
                "id": str(t.id),
                "code": t.template_code,
                "siteType": t.site_type,
                "scaleLevel": t.scale_level,
                "version": t.version_no,
                "status": t.status,
                "modelUrl": t.model_uri,
            }
            for t in repository.templates(session)
        ],
        request.app.state.settings,
    )


@router.get(
    "/scene-templates/{template_id}/objects",
    response_model=Result[TemplateObjectsOut],
    summary="读取模板GLB可选对象键",
)
def template_objects(
    template_id: PathId,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("twin:read")),
):
    """只读实际GLB命名节点；模板清单不等于设备台账，尚未发布模板返回409。"""
    return configuration.template_objects(session, request.app.state.settings, template_id)


@router.post(
    "/sites/{site_id}/scenes/from-template",
    response_model=Result[SceneOut],
    status_code=201,
    summary="从模板创建本站全新草稿",
)
def from_template(
    site_id: PathId,
    body: FromTemplateIn,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("twin:publish")),
):
    """可用于没有历史场景的新站；类型/规模一致，设备限本站，不自动发布或生成读数。"""
    return configuration.from_template(
        session, request.app.state.settings, principal, site_id, body
    )


@router.put(
    "/scenes/{scene_id}/objects",
    response_model=Result[SceneOut],
    summary="完整保存草稿对象与设备关系",
)
def objects(
    scene_id: PathId,
    body: ObjectsIn,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("twin:publish")),
):
    """相同键保留对象ID；删除/换设备影响绑定时返回409，请先清理相关绑定。"""
    return configuration.replace_objects(
        session, request.app.state.settings, principal, scene_id, body
    )


@router.get(
    "/sites/{site_id}/scene",
    response_model=Result[SceneOut],
    summary="本站当前发布场景、对象及测点绑定",
)
def current(
    site_id: PathId,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("twin:read")),
):
    """site_id为获授权站点；未发布场景返回404，不自动套其他站点的设备。"""
    site = require_site(session, principal, site_id)
    scene = repository.current_scene(session, site.id)
    if scene is None:
        raise BusinessError("SCENE_NOT_FOUND", "本站尚无发布场景")
    return result(service.scene_out(session, scene), request.app.state.settings)


@router.get(
    "/sites/{site_id}/scenes", response_model=Page[SceneSummary], summary="分页查看本站场景版本"
)
def versions(
    site_id: PathId,
    request: Request,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(50, alias="pageSize", ge=1, le=100),
    session: Session = Depends(get_session),
    principal=Depends(require_permission("twin:read")),
):
    """普通用户仅见当前发布；有twin:publish时可管理本站草稿和历史，返回分页摘要。"""
    site = require_site(session, principal, site_id)
    rows, total = repository.scene_versions(
        session, site.id, "twin:publish" in principal.permissions, page, page_size
    )
    return paged(
        [service.scene_summary(session, row) for row in rows],
        total,
        page,
        page_size,
        request.app.state.settings,
    )


@router.get(
    "/scenes/{scene_id}",
    response_model=Result[SceneOut],
    summary="读取场景版本；草稿/历史需管理权限",
)
def detail(
    scene_id: PathId,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("twin:read")),
):
    """返回指定版本，不改变当前发布版本，范围之外场景统一404。"""
    return result(
        service.scene_out(session, service.require_scene(session, principal, scene_id)),
        request.app.state.settings,
    )


@router.post(
    "/sites/{site_id}/scenes",
    response_model=Result[SceneOut],
    status_code=201,
    summary="复制当前场景为新草稿",
)
def clone(
    site_id: PathId,
    body: CloneIn,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("twin:publish")),
):
    """body可含modelUrl覆盖；对象与绑定复制为新ID，旧发布版本继续服务。"""
    return service.clone(session, request.app.state.settings, principal, site_id, body)


@router.put(
    "/scenes/{scene_id}/bindings",
    response_model=Result[SceneOut],
    summary="完整替换草稿绑定，校验同设备归属",
)
def bindings(
    scene_id: PathId,
    body: BindingsIn,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("twin:publish")),
):
    """先验证全部记录再替换；空bindings清空，发布版本禁止直接修改。"""
    return service.replace_bindings(session, request.app.state.settings, principal, scene_id, body)


@router.post(
    "/scenes/{scene_id}/publish",
    response_model=Result[SceneOut],
    summary="校验GLB和绑定后原子切换当前版本",
)
def publish(
    scene_id: PathId,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("twin:publish")),
):
    """仅DRAFT可发布；校验实际模型键，旧版本归档，失败整个事务回滚。"""
    return service.publish(session, request.app.state.settings, principal, scene_id)
