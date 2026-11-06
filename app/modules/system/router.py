"""登录、当前身份、角色、账号与授权、审计接口；JSON密码输入不会进入响应。"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import current_principal, get_session, require_permission
from app.common.access import PathId, result
from app.common.time import as_utc
from app.modules.system import service
from app.modules.system.models import AuditLog, Permission, Role, RolePermission, User
from app.modules.system.schemas import LoginIn, ScopeIn, UserCreate, UserStatusIn

router = APIRouter(tags=["账号与权限"])


@router.post("/auth/login", summary="JSON登录，获得短期Bearer令牌")
def login(body: LoginIn, request: Request, session: Session = Depends(get_session)):
    """body含username/password；返回accessToken、有效秒数和脱敏用户详情；错误401或限流429。"""
    return service.login(session, request.app, body, request.client.host)


@router.get("/auth/me", summary="当前用户、动作权限和站点范围")
def me(
    request: Request, session: Session = Depends(get_session), principal=Depends(current_principal)
):
    """无需填写身份参数；从Bearer令牌及数据库返回当前权限，不信任前端传入站点范围。"""
    return result(
        service.user_out(session, session.get(User, principal.user_id)), request.app.state.settings
    )


@router.get("/roles", summary="角色及动作权限目录")
def roles(
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("system:read")),
):
    """管理员读取角色；返回数字字符串ID、编码及该角色拥有的动作码，不含密码。"""
    data = []
    for role in session.scalars(select(Role).order_by(Role.id)):
        permissions = session.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
        ).all()
        data.append(
            {
                "id": str(role.id),
                "code": role.code,
                "name": role.name,
                "permissions": sorted(permissions),
            }
        )
    return result(data, request.app.state.settings)


@router.get("/users", summary="分页读取账号（管理员）")
def users(
    request: Request,
    page: int = Query(1, ge=1, le=10000, description="页码"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize", description="每页容量"),
    session: Session = Depends(get_session),
    principal=Depends(require_permission("system:read")),
):
    """只列出全部授权范围位于操作者范围内的用户；明文密码和令牌均不返回。"""
    visible = [
        user
        for user in session.scalars(select(User).order_by(User.id))
        if service.principal_for(session, user).site_ids <= principal.site_ids
    ]
    return result(
        {
            "items": [
                service.user_out(session, u)
                for u in visible[(page - 1) * page_size : page * page_size]
            ],
            "total": len(visible),
            "page": page,
            "pageSize": page_size,
        },
        request.app.state.settings,
    )


@router.post("/users", status_code=201, summary="创建账号、初始角色及站点授权")
def create_user(
    body: UserCreate,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("user:manage")),
):
    """body指定账号、密码、roleId、siteIds；成功201，重复账号409，越权授权403。"""
    return service.create_user(session, request.app.state.settings, principal, body)


@router.put("/users/{user_id}/sites", summary="完整替换用户站点授权")
def scope(
    user_id: PathId,
    body: ScopeIn,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("user:manage")),
):
    """user_id为目标账号主键；siteIds空数组撤销所有站点权限，下一次请求立即生效。"""
    return service.replace_scope(session, request.app.state.settings, principal, user_id, body)


@router.put("/users/{user_id}/status", summary="启用、锁定或停用账号")
def status(
    user_id: PathId,
    body: UserStatusIn,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("user:manage")),
):
    """status为ACTIVE/LOCKED/INACTIVE；不能锁定自己，修改记录进入审计。"""
    return service.update_status(session, request.app.state.settings, principal, user_id, body)


@router.get("/audit-logs", summary="分页审计记录")
def audits(
    request: Request,
    page: int = Query(1, ge=1, le=10000, description="页码"),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100, description="每页容量"),
    session: Session = Depends(get_session),
    principal=Depends(require_permission("audit:read")),
):
    """返回范围内的站点操作；全局账号操作仅原操作者可读，避免通过审计泄露其他站点。"""
    from sqlalchemy import and_, or_

    statement = (
        select(AuditLog)
        .where(
            or_(
                AuditLog.site_id.in_(principal.site_ids),
                and_(AuditLog.site_id.is_(None), AuditLog.actor_id == principal.user_id),
            )
        )
        .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
    )
    rows = session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    return result(
        [
            {
                "id": str(r.id),
                "actorId": str(r.actor_id) if r.actor_id else None,
                "siteId": str(r.site_id) if r.site_id else None,
                "action": r.action,
                "targetType": r.target_type,
                "targetId": r.target_id,
                "occurredAt": as_utc(r.occurred_at),
                "after": r.after_json,
            }
            for r in rows
        ],
        request.app.state.settings,
    )
