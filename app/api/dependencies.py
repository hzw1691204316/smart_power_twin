"""请求依赖模块：会话、Bearer认证、动作权限及按站点范围过滤的台账服务。"""

from contextlib import nullcontext

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.common.access import find
from app.core.exceptions import BusinessError
from app.core.security import token_subject
from app.modules.assets.repository import AssetRepository
from app.modules.assets.service import AssetService
from app.modules.system.models import User
from app.modules.system.repository import principal_for

bearer = HTTPBearer(
    auto_error=False,
    description="先调用/auth/login，将accessToken填入Authorize；不要填写用户名密码",
)


async def get_session(request: Request):
    """为request所属应用创建请求级Session。

    yield把会话交给接口依赖，结束时关闭并释放资源；只读查询不主动提交事务。"""
    # SQLite共用一个连接，异步排队避免并发事务相互回滚，同时不占用等待中的线程池。
    # 不用跨yield持有线程锁：高并发会耗尽线程池，使持锁请求无法进入同步业务函数。
    # MySQL使用独立连接池，不串行排队；业务函数仍在线程池执行同步SQLAlchemy查询。
    guard = request.app.state.db_lock if request.app.state.is_test_database else nullcontext()
    async with guard:
        session = Session(request.app.state.engine)
        try:
            yield session
        finally:
            await run_in_threadpool(session.close)


def current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_session),
):
    """校验Bearer令牌并重查有效账号、动作权限和站点范围；未登录／停用返回401。"""
    if credentials is None:
        raise BusinessError("UNAUTHENTICATED", "请先登录并提供Bearer令牌", 401)
    subject = token_subject(credentials.credentials, request.app.state.token_secret)
    user = find(session, User, str(subject))
    if user is None or user.status != "ACTIVE":
        raise BusinessError("UNAUTHENTICATED", "账号不存在、已锁定或已停用", 401)
    return principal_for(session, user)


def require_permission(code: str):
    """返回动作权限依赖；code如alarm:ack。站点范围还必须在业务查询中再次过滤。"""

    def check(principal=Depends(current_principal)):
        """参数principal由身份依赖注入；缺少动作码返回403，成功返回当前身份。"""
        if code not in principal.permissions:
            raise BusinessError("FORBIDDEN", "当前账号没有此操作权限", 403)
        return principal

    return check


def get_assets(
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("site:read")),
):
    """组装台账业务服务。request提供当前数据来源；session由get_session注入。

    返回绑定仓储和来源信息的AssetService；调用者无需自行管理连接。"""
    return AssetService(
        AssetRepository(session, principal.site_ids), request.app.state.settings.data_source
    )
