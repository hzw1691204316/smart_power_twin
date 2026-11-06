"""账号业务：登录、账号维护、站点授权和追加审计。当前首期每用户一个角色。"""

from uuid import uuid4

from sqlalchemy import delete, select

from app.common.access import commit, find, require_writable, result
from app.common.time import utc_now
from app.core.exceptions import BusinessError
from app.core.security import issue_token, password_matches
from app.modules.system.models import AuditLog, Role, User, UserSiteScope
from app.modules.system.repository import principal_for, user_by_name


def audit(session, principal, action, target_type, target_id, site_id=None, after=None):
    """在当前事务追加审计；after只传白名单业务摘要，禁止密码、令牌或整份请求。"""
    session.add(
        AuditLog(
            actor_id=principal.user_id,
            site_id=site_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            request_id=uuid4().hex,
            occurred_at=utc_now(),
            after_json=after,
        )
    )


def user_out(session, user):
    """把user转换为不含密码的账号详情；主键字符串化，附当前动作和站点范围。"""
    principal = principal_for(session, user)
    return {
        "id": str(user.id),
        "username": user.username,
        "displayName": user.display_name,
        "status": user.status,
        "roleId": str(user.role_id),
        "roleCode": principal.role_code,
        "permissions": sorted(principal.permissions),
        "siteIds": [str(i) for i in sorted(principal.site_ids)],
    }


def login(session, application, body, client_key):
    """校验LoginIn并签发短期令牌；同IP+账号5分钟最多10次失败，成功清除计数。"""
    from time import monotonic

    now = monotonic()
    key = (client_key, body.username)
    attempts = application.state.login_attempts
    with application.state.login_lock:
        expired = [k for k, v in attempts.items() if now - v[1] > 300]
        for k in expired:
            attempts.pop(k, None)
        count, first = attempts.get(key, (0, now))
        if count >= 10:
            raise BusinessError("LOGIN_THROTTLED", "登录失败过多，请5分钟后重试", 429)
    user = user_by_name(session, body.username)
    valid = password_matches(
        body.password.get_secret_value(),
        user.password if user else application.state.dummy_password,
    )
    if user is None or not valid or user.status != "ACTIVE":
        with application.state.login_lock:
            if len(attempts) >= 1024:
                attempts.pop(next(iter(attempts)))
            attempts[key] = (count + 1, first)
        raise BusinessError("UNAUTHENTICATED", "账号或密码错误，或账号不可用", 401)
    with application.state.login_lock:
        attempts.pop(key, None)
    settings = application.state.settings
    token = issue_token(user.id, application.state.token_secret, settings.token_minutes)
    return result(
        {
            "accessToken": token,
            "tokenType": "bearer",
            "expiresIn": settings.token_minutes * 60,
            "user": user_out(session, user),
        },
        settings,
    )


def create_user(session, settings, principal, body):
    """创建账号、初始角色及授权范围；只能授予本人已有权限与站点，成功提交并审计。"""
    require_writable(settings)
    role = find(session, Role, body.role_id)
    if role is None:
        raise BusinessError("ROLE_NOT_FOUND", "角色不存在")
    # 当前角色权限直接复用系统查询，不能让用户管理动作成为提权通道。
    from app.modules.system.models import Permission, RolePermission

    target_permissions = set(
        session.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
        )
    )
    if not target_permissions <= principal.permissions:
        raise BusinessError("FORBIDDEN", "不能授予自身不具备的动作权限", 403)
    ids = {int(i) for i in body.site_ids}
    if not ids <= principal.site_ids:
        raise BusinessError("FORBIDDEN", "不能授予自身范围之外的站点", 403)
    if user_by_name(session, body.username):
        raise BusinessError("CONFLICT", "账号已经存在", 409)
    user = User(
        username=body.username,
        display_name=body.display_name,
        password=body.password.get_secret_value(),
        role_id=role.id,
        status="ACTIVE",
    )
    session.add(user)
    session.flush()
    session.add_all(UserSiteScope(user_id=user.id, site_id=i) for i in ids)
    audit(
        session,
        principal,
        "user:create",
        "user",
        user.id,
        after={"username": user.username, "siteIds": sorted(ids)},
    )
    commit(session)
    return result(user_out(session, user), settings)


def replace_scope(session, settings, principal, user_id, body):
    """用body.site_ids完整替换用户范围；保留动作权限，不允许扩大到操作者范围之外。"""
    require_writable(settings)
    user = find(session, User, user_id)
    if user is None:
        raise BusinessError("USER_NOT_FOUND", "账号不存在")
    current = principal_for(session, user)
    if not current.permissions <= principal.permissions:
        raise BusinessError("FORBIDDEN", "不能维护权限高于自身的账号", 403)
    ids = {int(i) for i in body.site_ids}
    if not (ids | set(current.site_ids)) <= principal.site_ids:
        raise BusinessError("FORBIDDEN", "不能维护自身范围之外的授权", 403)
    session.execute(delete(UserSiteScope).where(UserSiteScope.user_id == user.id))
    session.add_all(UserSiteScope(user_id=user.id, site_id=i) for i in ids)
    audit(session, principal, "user:scope", "user", user.id, after={"siteIds": sorted(ids)})
    commit(session)
    return result(user_out(session, user), settings)


def update_status(session, settings, principal, user_id, body):
    """设置账号ACTIVE/LOCKED/INACTIVE；不允许修改本人，已有JWT仍须每次重查状态。"""
    require_writable(settings)
    user = find(session, User, user_id)
    if user is None:
        raise BusinessError("USER_NOT_FOUND", "账号不存在")
    if user.id == principal.user_id:
        raise BusinessError("CONFLICT", "不能修改当前登录账号状态", 409)
    target = principal_for(session, user)
    if not target.permissions <= principal.permissions or not target.site_ids <= principal.site_ids:
        raise BusinessError("FORBIDDEN", "目标账号含未授权站点", 403)
    user.status = body.status
    audit(session, principal, "user:status", "user", user.id, after={"status": body.status})
    commit(session)
    return result(user_out(session, user), settings)
