"""测试专用工厂；配置test不能从正式Settings启动，永远不读取用户数据库配置。"""

from typing import Literal

from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.application import create_app
from app.core.config import Settings
from app.modules.system.models import Permission, Role, RolePermission, User, UserSiteScope
from scripts.sample_assets import create_sample_database


class TestSettings(Settings):
    """只在测试中允许test来源；不是公开的环境变量配置选项。"""

    __test__ = False
    data_source: Literal["test", "mysql"] = "test"
    token_secret: SecretStr = SecretStr("isolated-offline-test-signing-secret-2026")


def create_test_database(_settings):
    """创建隔离SQLite测试引擎并填两角色/账号；fixture密码只在测试使用，不进MySQL。"""
    engine = create_sample_database()
    codes = [
        "site:read",
        "device:read",
        "system:read",
        "user:manage",
        "audit:read",
        "monitor:read",
        "telemetry:write",
        "monitor:configure",
        "twin:read",
        "twin:publish",
        "alarm:read",
        "alarm:ack",
        "alarm:close",
        "dashboard:read",
        "site:create",
        "asset:manage",
    ]
    with Session(engine) as session, session.begin():
        session.add_all(
            [
                Role(id=1, code="ADMIN", name="测试管理员"),
                Role(id=2, code="VIEWER", name="测试观察员"),
            ]
        )
        session.add_all(Permission(id=i, code=code, name=code) for i, code in enumerate(codes, 1))
        session.flush()
        for i, username, password in [
            (1, "fixture_admin", "FixtureAdmin!2026"),
            (2, "fixture_viewer", "FixtureViewer!2026"),
        ]:
            session.add(
                User(
                    id=i,
                    username=username,
                    password=password,
                    display_name=username,
                    role_id=i,
                    status="ACTIVE",
                )
            )
            session.add_all(
                RolePermission(role_id=i, permission_id=p)
                for p in (range(1, 17) if i == 1 else [1, 2, 6, 9, 11, 14])
            )
        session.flush()
        session.add_all(
            UserSiteScope(user_id=i, site_id=s)
            for i, sites in [(1, [1, 2]), (2, [1])]
            for s in sites
        )
    return engine


def create_test_app():
    """测试应用通过显式factory注入，不触发正式MySQL配置或数据初始化。"""
    return create_app(TestSettings(_env_file=None), database_factory=create_test_database)
