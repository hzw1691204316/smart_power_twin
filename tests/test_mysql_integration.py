"""可选的真实MySQL集成验收：仅连接明确指定的隔离实例，不读.env、不访问用户3306库。

设置SPT_TEST_MYSQL_PORT为隔离端口后运行；否则整组跳过。测试会导入脚本和维护测试账号。
"""

import os
from pathlib import Path

import pymysql
import pytest
from fastapi.testclient import TestClient

from app.application import create_app
from app.core.config import Settings
from scripts.generate_auth_mysql_seed import CHECK_FILE, SCHEMA_FILE, build_seed_sql

ROOT = Path(__file__).resolve().parents[1]
TEST_PASSWORD = "IsolatedMySQL!2026"
pytestmark = pytest.mark.skipif(
    not os.environ.get("SPT_TEST_MYSQL_PORT"), reason="未启用隔离MySQL实例测试"
)


def execute_script(connection, script):
    """执行本项目逐行DELIMITER脚本；只用于固定测试素材，不是通用SQL解析器。"""
    delimiter, buffer = ";", []
    with connection.cursor() as cursor:
        for line in script.splitlines():
            if line.strip().upper().startswith("DELIMITER "):
                delimiter = line.strip().split(maxsplit=1)[1]
                continue
            buffer.append(line)
            if line.rstrip().endswith(delimiter):
                statement = "\n".join(buffer).rstrip()[: -len(delimiter)]
                cursor.execute(statement)
                while cursor.nextset():
                    pass
                buffer = []
        assert not any(line.strip() and not line.strip().startswith("--") for line in buffer)


@pytest.fixture(scope="module")
def isolated_mysql():
    """严格检查端口与@@datadir后，才在专用测试实例建测试库；拒绝用户默认实例。"""
    port = int(os.environ["SPT_TEST_MYSQL_PORT"])
    if port == 3306:
        pytest.fail("禁止将真实MySQL集成测试指向3306")
    connection = pymysql.connect(
        host="127.0.0.1", port=port, user="root", password="", autocommit=True, charset="utf8mb4"
    )
    with connection.cursor() as cursor:
        cursor.execute("SELECT @@datadir")
        data_path = str(cursor.fetchone()[0]).replace("\\", "/").lower().rstrip("/")
        if not data_path.endswith("/.runtime/mysql-auth-integration"):
            connection.close()
            pytest.fail("数据目录不是专用隔离实例，禁止执行测试写入")
        # 上方已验证专用datadir且禁止3306，只重建这个可丢弃实例中的测试库，保证用例可重跑。
        cursor.execute("DROP DATABASE IF EXISTS smart_power_twin")
        cursor.execute(
            "CREATE DATABASE smart_power_twin CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs"
        )
    execute_script(connection, (ROOT / "sql" / SCHEMA_FILE).read_text(encoding="utf-8"))
    execute_script(
        connection, (ROOT / "sql/C00监测模块_仅缺表时使用.sql").read_text(encoding="utf-8")
    )
    execute_script(
        connection, (ROOT / "sql/C00三维模块_仅缺表时使用.sql").read_text(encoding="utf-8")
    )
    execute_script(
        connection, (ROOT / "sql/C00告警模块_仅缺表时使用.sql").read_text(encoding="utf-8")
    )
    with connection.cursor() as cursor:
        # 验证脚本和接口不依赖demo的1/2等固定ID。
        cursor.execute("SELECT COUNT(*) FROM sys_user")
        if cursor.fetchone()[0] == 0:
            for table, start in [
                ("sys_role", 11),
                ("sys_permission", 21),
                ("site", 101),
                ("sys_user", 201),
            ]:
                cursor.execute(f"ALTER TABLE `{table}` AUTO_INCREMENT={start}")
        cursor.execute(
            "CREATE USER IF NOT EXISTS 'spt_integration'@'127.0.0.1' IDENTIFIED BY %s",
            (TEST_PASSWORD,),
        )
        for table in [
            "site",
            "site_area",
            "device",
            "site_route_link",
            "highway_route",
            "sys_role",
            "sys_permission",
            "role_permission",
            "sys_user",
            "user_site_scope",
            "audit_log",
            "device_point",
            "point_latest",
            "point_history",
            "scene_template",
            "twin_scene",
            "twin_object",
            "twin_binding",
            "alarm_event",
        ]:
            cursor.execute(
                f"GRANT SELECT ON smart_power_twin.`{table}` TO 'spt_integration'@'127.0.0.1'"
            )
        cursor.execute(
            "GRANT INSERT,UPDATE ON smart_power_twin.sys_user TO 'spt_integration'@'127.0.0.1'"
        )
        cursor.execute(
            "GRANT INSERT,DELETE ON smart_power_twin.user_site_scope TO 'spt_integration'@'127.0.0.1'"
        )
        cursor.execute(
            "GRANT INSERT ON smart_power_twin.audit_log TO 'spt_integration'@'127.0.0.1'"
        )
    # 使用受控测试密码生成内容相同的独立种子，不读取用户桌面的随机初始密码。
    seed = build_seed_sql("TestAdmin!2026", "TestViewer!2026")
    execute_script(connection, seed)
    yield connection, port, seed
    connection.close()


def settings(port, writes=True):
    """只用隔离实例凭据；显式传参绕过用户.env和默认3306配置。"""
    return Settings(
        data_source="mysql",
        mysql_host="127.0.0.1",
        mysql_port=port,
        mysql_user="spt_integration",
        mysql_password=TEST_PASSWORD,
        mysql_allow_writes=writes,
        token_secret="isolated-test-signing-secret-2026-10-15",
        _env_file=None,
    )


def test_mysql_seed_and_authorization_persistence(isolated_mysql):
    connection, port, seed = isolated_mysql
    with TestClient(create_app(settings(port)), client=("127.0.0.1", 50000)) as client:

        def login(name, password):
            result = client.post(
                "/api/v1/auth/login", json={"username": name, "password": password}
            )
            assert result.status_code == 200, result.text
            return result.json()["data"]

        admin = login("mysql_admin", "TestAdmin!2026")
        client.headers["Authorization"] = "Bearer " + admin["accessToken"]
        health = client.get("/api/v1/health").json()
        assert health["dataSource"] == "mysql" and health["mysqlWritesEnabled"] is True
        sites = client.get("/api/v1/sites").json()["data"]
        assert len(sites) == 2 and {s["id"] for s in sites} != {"1", "2"}
        assert all(s["isDemo"] for s in sites)
        service_id = next(s["id"] for s in sites if s["siteType"] == "SERVICE")
        toll_id = next(s["id"] for s in sites if s["siteType"] == "TOLL")
        assert len(client.get(f"/api/v1/sites/{service_id}/devices").json()["data"]) == 4
        role = next(r for r in client.get("/api/v1/roles").json()["data"] if r["code"] == "VIEWER")
        created = client.post(
            "/api/v1/users",
            json={
                "username": "persistent_viewer",
                "displayName": "持久化测试",
                "password": "Persistent!2026",
                "roleId": role["id"],
                "siteIds": [service_id],
            },
        )
        assert created.status_code == 201, created.text
        user_id = created.json()["data"]["id"]
        viewer = login("persistent_viewer", "Persistent!2026")
        viewer_headers = {"Authorization": "Bearer " + viewer["accessToken"]}
        assert client.get(f"/api/v1/sites/{toll_id}", headers=viewer_headers).status_code == 404
        assert (
            client.put(f"/api/v1/users/{user_id}/sites", json={"siteIds": [toll_id]}).status_code
            == 200
        )
        assert client.get("/api/v1/auth/me", headers=viewer_headers).json()["data"]["siteIds"] == [
            toll_id
        ]
        assert (
            client.put(f"/api/v1/users/{user_id}/status", json={"status": "LOCKED"}).status_code
            == 200
        )
        assert client.get("/api/v1/auth/me", headers=viewer_headers).status_code == 401
        audit = client.get("/api/v1/audit-logs").json()["data"]
        assert {item["action"] for item in audit} >= {"user:create", "user:scope", "user:status"}
        # 撤销初始观察员站点范围后重跑种子：不能把撤销的权限恢复，也不能重置密码。
        initial_viewer = login("mysql_viewer", "TestViewer!2026")["user"]
        client.put(f"/api/v1/users/{initial_viewer['id']}/sites", json={"siteIds": []})
    execute_script(connection, seed)
    execute_script(connection, (ROOT / "sql" / CHECK_FILE).read_text(encoding="utf-8"))
    # 新应用/新连接模拟后端重启，验证不会重建/覆盖MySQL数据。
    with TestClient(create_app(settings(port)), client=("127.0.0.1", 50001)) as restarted:
        response = restarted.post(
            "/api/v1/auth/login",
            json={"username": "persistent_viewer", "password": "Persistent!2026"},
        )
        assert response.status_code == 401  # LOCKED持久化。
        initial = restarted.post(
            "/api/v1/auth/login", json={"username": "mysql_viewer", "password": "TestViewer!2026"}
        )
        assert initial.status_code == 200 and initial.json()["data"]["user"]["siteIds"] == []
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM sys_user")
        assert cursor.fetchone()[0] == 3
        cursor.execute("SELECT password FROM sys_user WHERE username='persistent_viewer'")
        assert cursor.fetchone()[0] == "Persistent!2026"


def test_mysql_read_only_mode(isolated_mysql):
    _connection, port, _seed = isolated_mysql
    with TestClient(
        create_app(settings(port, writes=False)), client=("127.0.0.1", 50002)
    ) as client:
        login = client.post(
            "/api/v1/auth/login", json={"username": "mysql_admin", "password": "TestAdmin!2026"}
        )
        assert login.status_code == 200
        client.headers["Authorization"] = "Bearer " + login.json()["data"]["accessToken"]
        assert client.get("/api/v1/health").json()["mysqlWritesEnabled"] is False
        assert client.get("/api/v1/users").status_code == 200
        assert (
            client.put("/api/v1/users/999999/status", json={"status": "ACTIVE"}).status_code == 409
        )


def test_mysql_seed_rollback_and_preserve_accounts(isolated_mysql):
    connection, _port, seed = isolated_mysql
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM site")
        before = cursor.fetchone()[0]
    # 将首次角色INSERT故意改为新编码，然后让第二条写入失败，必须撤销第一条写入。
    broken = seed.replace("SELECT 'ADMIN', '管理员'", "SELECT 'ROLLBACK_PROBE', '管理员'", 1)
    broken = broken.replace("WHERE code='ADMIN')", "WHERE code='ROLLBACK_PROBE')", 1)
    broken = broken.replace("SELECT 'VIEWER', '只读观察员'", "SELECT NULL, '只读观察员'", 1)
    # 现有VIEWER会使WHERE NOT EXISTS为False，因此把该条件改为永不存在的探针编码。
    broken = broken.replace("WHERE code='VIEWER')", "WHERE code='MISSING_ROLLBACK_PROBE')", 1)
    with pytest.raises(pymysql.MySQLError):
        execute_script(connection, broken)
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM sys_role WHERE code='ROLLBACK_PROBE'")
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM site")
        assert cursor.fetchone()[0] == before


def test_mysql_direct_plaintext_password_edit(isolated_mysql):
    """用户可直接修改password列；旧密码失效、新密码登录，不依赖改密工具。"""
    connection, port, _seed = isolated_mysql
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE sys_user SET password=%s WHERE username='mysql_viewer'", ("DirectEdit!2026",)
        )
    with TestClient(create_app(settings(port)), client=("127.0.0.1", 50003)) as client:
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"username": "mysql_viewer", "password": "TestViewer!2026"},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"username": "mysql_viewer", "password": "DirectEdit!2026"},
            ).status_code
            == 200
        )
