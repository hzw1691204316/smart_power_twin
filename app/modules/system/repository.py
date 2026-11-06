"""账号仓储：查询用户、角色、动作权限和站点授权；不解码令牌或返回密码。"""

from sqlalchemy import select

from app.modules.system.models import Permission, Role, RolePermission, User, UserSiteScope
from app.modules.system.schemas import Principal


def principal_for(session, user):
    """参数user为ORM账号；返回当前角色、权限与站点范围组成的不可变Principal。"""
    role = session.get(Role, user.role_id)
    permissions = session.scalars(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == user.role_id)
    ).all()
    sites = session.scalars(
        select(UserSiteScope.site_id).where(UserSiteScope.user_id == user.id)
    ).all()
    return Principal(user.id, user.username, role.code, frozenset(permissions), frozenset(sites))


def user_by_name(session, username):
    """按唯一username读取账号，未知返回None；密码校验在service中进行。"""
    return session.scalar(select(User).where(User.username == username))
