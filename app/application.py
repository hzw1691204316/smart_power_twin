"""应用装配模块：注册接口、异常处理、CORS、本机访问限制和数据库生命周期。

只负责装配基础能力，站点查询规则交给assets；不在启动时循环采集或修改MySQL结构。"""

from asyncio import Lock as AsyncLock
from collections.abc import Callable
from contextlib import asynccontextmanager
from ipaddress import ip_address
from secrets import token_urlsafe
from threading import Lock

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.router import router
from app.core.config import Settings
from app.core.exceptions import register_exception_handlers
from app.db.session import create_database
from app.db.validation import validate_mysql_schema


def create_app(
    settings: Settings | None = None,
    *,
    database_factory: Callable[[Settings], Engine] | None = None,
) -> FastAPI:
    """创建可独立启动或测试的FastAPI应用。

    参数：settings默认读取.env.mysql.local；database_factory仅供自动化测试注入独立引擎。
    返回：FastAPI应用，数据库引擎在lifespan启动时建立。
    注意：已启用认证和站点范围，仍限定本机演示；测试可传入配置隔离用户环境。"""
    settings = settings if settings is not None else Settings()
    if settings.data_source != "mysql" and database_factory is None:
        raise ValueError("后端只支持MySQL；测试数据必须通过测试工厂显式注入")
    secret = settings.token_secret.get_secret_value()
    if (secret and len(secret) < 32) or (settings.data_source == "mysql" and not secret):
        raise ValueError("请在后端本地配置至少32字符的SPT_TOKEN_SECRET")

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        """管理应用启动与关闭。application是当前应用实例。

        启动时仅连接并检查MySQL，关闭时释放连接池；测试引擎只由测试工厂注入。"""
        engine = database_factory(settings) if database_factory else create_database(settings)
        application.state.engine = engine
        try:
            if settings.data_source == "mysql":
                # MySQL只做连接和结构预检；初始化数据必须由用户手动导入。
                validate_mysql_schema(engine)
            yield
        finally:
            engine.dispose()

    application = FastAPI(
        title="智慧电力数字孪生 · 后端业务接口",
        version="0.9.0",
        description="MySQL账号、台账查询与维护、电力监测、三维绑定、告警与大屏汇总接口。先POST /api/v1/auth/login，再将accessToken填入Authorize。网页登录密码沿用当前明文约定，仅本机访问。",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.is_test_database = (
        database_factory is not None and settings.data_source == "test"
    )
    application.state.token_secret = secret or token_urlsafe(48)
    application.state.db_lock = AsyncLock()
    application.state.login_lock = Lock()
    application.state.login_attempts = {}
    application.state.dummy_password = token_urlsafe(32)
    register_exception_handlers(application)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Accept", "Content-Type", "Authorization"],
    )

    @application.middleware("http")
    async def local_preview_only(request: Request, call_next):
        # 已有认证，仍保持本机演示边界，不自动开放到局域网。
        """限制演示后端只在本机测试。

        参数：request含客户端IP；call_next代表后续请求处理链。
        返回：本机请求继续处理；其他客户端返回403 LOCAL_ONLY。此处不是账号或站点权限校验。"""
        try:
            local = request.client is not None and ip_address(request.client.host).is_loopback
        except ValueError:
            local = False
        if not local:
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "LOCAL_ONLY", "message": "当前仅允许本机测试"}},
            )
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @application.get("/", tags=["基础"], summary="保留原示例入口")
    def root():
        """保留原根路径示例，返回固定问候消息，方便确认旧入口未丢失。"""
        return {"message": "Hello World"}

    @application.get("/hello/{name}", tags=["基础"])
    def say_hello(name: str):
        """保留原问候接口。name是路径中的显示名称；返回包含该名称的消息。"""
        return {"message": f"Hello {name}"}

    @application.get("/api/v1/health", tags=["基础"], summary="检查数据连接和当前测试模式")
    def health(session: Session = Depends(get_session)):
        """检查当前数据连接及运行模式。

        执行SELECT 1后返回数据来源、数据库标识和访问模式；失败由统一异常处理返回503。
        这里只证明连接可查询，不证明19张业务表均存在，也不代表设备在线。"""
        session.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "module": "assets-system-monitoring-twin-alarms-dashboard",
            "dataSource": settings.data_source,
            "database": "isolated-test"
            if application.state.is_test_database
            else settings.mysql_database,
            "accessMode": "local-only",
            "authenticationImplemented": True,
            "mysqlWritesEnabled": settings.data_source == "mysql" and settings.mysql_allow_writes,
        }

    application.include_router(router)
    return application
