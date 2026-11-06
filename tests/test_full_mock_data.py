"""全模块模拟素材验收：默认离线；显式隔离端口才执行真实MySQL，绝不读取用户配置。"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pymysql
import pytest
from fastapi.testclient import TestClient

from app.application import create_app
from app.core.config import Settings
from scripts.generate_auth_mysql_seed import build_seed_sql
from scripts.generate_full_mock_data import BATCH, TABLES, build_sql, generate_bundle
from tests.test_mysql_integration import execute_script

ROOT = Path(__file__).resolve().parents[1]
MYSQL_ONLY = pytest.mark.skipif(
    not os.environ.get("SPT_TEST_MYSQL_PORT"), reason="未启用隔离MySQL实例测试"
)


@MYSQL_ONLY
def test_mysql_site_relations_cycles_primary_and_rollback(full_mysql, mock_bundle):
    """专用MySQL验证区域并发父环、主关联互斥、真实复合外键与审计失败原子回滚。"""
    from tests.test_site_relations import area_body, edit_body, link_body

    connection = full_mysql
    execute_script(connection, mock_bundle[0])
    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE USER IF NOT EXISTS 'spt_relation_fixture'@'127.0.0.1' IDENTIFIED BY 'RelationFixture!2026'"
        )
        cursor.execute("GRANT SELECT ON smart_power_twin.* TO 'spt_relation_fixture'@'127.0.0.1'")
        cursor.execute(
            "GRANT UPDATE(id) ON smart_power_twin.site TO 'spt_relation_fixture'@'127.0.0.1'"
        )
        for table in ["site_area", "site_route_link"]:
            cursor.execute(
                f"GRANT INSERT,UPDATE ON smart_power_twin.{table} TO 'spt_relation_fixture'@'127.0.0.1'"
            )
        cursor.execute(
            "GRANT INSERT ON smart_power_twin.audit_log TO 'spt_relation_fixture'@'127.0.0.1'"
        )
    settings = Settings(
        mysql_port=int(os.environ["SPT_TEST_MYSQL_PORT"]),
        mysql_user="spt_relation_fixture",
        mysql_password="RelationFixture!2026",
        token_secret="isolated-site-relations-signing-secret-2026",
        mysql_allow_writes=True,
        _env_file=None,
    )
    with TestClient(create_app(settings), client=("127.0.0.1", 50014)) as client:
        login = client.post(
            "/api/v1/auth/login", json={"username": "sim_admin", "password": "SimAdmin!2026"}
        )
        assert login.status_code == 200
        client.headers["Authorization"] = "Bearer " + login.json()["data"]["accessToken"]
        sid = str(scalar(connection, "SELECT id FROM site WHERE code='HEBI_CHAOGE_SERVICE_DEMO'"))
        base = f"/api/v1/sites/{sid}"
        original = client.get(base).json()["data"]
        route_id = original["routes"][0]["routeId"]
        areas = []
        for code in ["RACE_A", "RACE_B"]:
            response = client.post(base + "/areas", json=area_body(code=code))
            assert response.status_code == 201, response.text
            areas.append(response.json()["data"])

        def parent(pair):
            """两个请求相互指定父区域，站点锁与最新锁定读应只允许一个成功。"""
            child, ancestor = pair
            return client.put(
                base + f"/areas/{child['id']}", json=edit_body(area_body(parentId=ancestor["id"]))
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(parent, [(areas[0], areas[1]), (areas[1], areas[0])])) == [
                200,
                409,
            ]

        def primary(index):
            """同时新增两条主方向关联，两者可串行成功，提交后至多一个主关联。"""
            return client.post(
                base + "/routes",
                json=link_body(
                    linkCode=f"RACE_LINK_{index}",
                    routeId=route_id,
                    areaId=areas[index]["id"],
                    chainageM="23456.125",
                ),
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(primary, range(2)))
        assert all(response.status_code == 201 for response in responses)
        before = client.get(base).json()["data"]["routes"]
        assert sum(row["isPrimary"] for row in before) == 1
        count = scalar(connection, "SELECT COUNT(*) FROM site_area WHERE site_id=%s", (sid,))
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TRIGGER isolated_relation_audit_fail BEFORE INSERT ON audit_log FOR EACH ROW BEGIN IF NEW.action IN ('asset:area_create','asset:route_link_create') THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ISOLATED_RELATION_AUDIT_FAILURE'; END IF; END"
            )
        try:
            assert (
                client.post(base + "/areas", json=area_body(code="ROLLBACK_AREA")).status_code
                == 503
            )
            assert (
                client.post(
                    base + "/routes", json=link_body(linkCode="ROLLBACK_ROUTE", routeId=route_id)
                ).status_code
                == 503
            )
        finally:
            with connection.cursor() as cursor:
                cursor.execute("DROP TRIGGER isolated_relation_audit_fail")
        assert (
            scalar(connection, "SELECT COUNT(*) FROM site_area WHERE site_id=%s", (sid,)) == count
        )
        assert client.get(base).json()["data"]["routes"] == before
        # 只读模式也不能写区域/关联；不影响用户账号和数据库连接配置。
        settings.mysql_allow_writes = False
        assert client.post(base + "/areas", json=area_body(code="READ_ONLY")).status_code == 409
        assert (
            client.post(
                base + "/routes", json=link_body(linkCode="READ_ONLY", routeId=route_id)
            ).status_code
            == 409
        )


@MYSQL_ONLY
def test_mysql_scene_creation_and_object_edit_atomicity(full_mysql, mock_bundle):
    """隔离MySQL：并发从模板分配不同版本，对象外键/父关系及审计失败一并回滚。"""
    connection = full_mysql
    execute_script(connection, mock_bundle[0])
    execute_script(
        connection, (ROOT / "sql/C07大型服务区_统一模板注册.sql").read_text(encoding="utf-8")
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE USER IF NOT EXISTS 'spt_config_fixture'@'127.0.0.1' IDENTIFIED BY 'ConfigFixture!2026'"
        )
        cursor.execute("GRANT SELECT ON smart_power_twin.* TO 'spt_config_fixture'@'127.0.0.1'")
        cursor.execute(
            "GRANT UPDATE(id) ON smart_power_twin.site TO 'spt_config_fixture'@'127.0.0.1'"
        )
        for table in ["twin_scene", "twin_object", "twin_binding"]:
            cursor.execute(
                f"GRANT INSERT,UPDATE,DELETE ON smart_power_twin.{table} TO 'spt_config_fixture'@'127.0.0.1'"
            )
        cursor.execute(
            "GRANT INSERT ON smart_power_twin.audit_log TO 'spt_config_fixture'@'127.0.0.1'"
        )
    settings = Settings(
        mysql_port=int(os.environ["SPT_TEST_MYSQL_PORT"]),
        mysql_user="spt_config_fixture",
        mysql_password="ConfigFixture!2026",
        token_secret="isolated-scene-config-signing-secret-2026",
        mysql_allow_writes=True,
        _env_file=None,
    )
    with TestClient(create_app(settings), client=("127.0.0.1", 50013)) as client:
        login = client.post(
            "/api/v1/auth/login", json={"username": "sim_admin", "password": "SimAdmin!2026"}
        )
        assert login.status_code == 200
        client.headers["Authorization"] = "Bearer " + login.json()["data"]["accessToken"]
        site_id = str(
            scalar(connection, "SELECT id FROM site WHERE code='HEBI_CHAOGE_SERVICE_DEMO'")
        )
        current = client.get(f"/api/v1/sites/{site_id}/scene").json()["data"]
        payload = {
            "templateId": current["templateId"],
            "objects": [
                {"objectKey": o["objectKey"], "name": o["name"], "deviceId": o["deviceId"]}
                for o in current["objects"]
            ],
        }

        def create(_index):
            """同站并发创建草稿使用同一站点锁，不改变当前已发布版本。"""
            response = client.post(f"/api/v1/sites/{site_id}/scenes/from-template", json=payload)
            assert response.status_code == 201, response.text
            return response.json()["data"]

        with ThreadPoolExecutor(max_workers=3) as pool:
            drafts = list(pool.map(create, range(3)))
        assert sorted(d["version"] for d in drafts) == list(
            range(current["version"] + 1, current["version"] + 4)
        )
        assert client.get(f"/api/v1/sites/{site_id}/scene").json()["data"]["id"] == current["id"]
        value = drafts[0]
        first, second = value["objects"][:2]
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE twin_object SET parent_id=%s WHERE id=%s", (first["id"], second["id"])
            )
        # 没有绑定的父对象可以移除；子对象ID保留，parent置空，真实复合外键必须成立。
        rows = payload["objects"][1:]
        response = client.put(f"/api/v1/scenes/{value['id']}/objects", json={"objects": rows})
        assert response.status_code == 200, response.text
        assert response.json()["data"]["objects"][0]["parentId"] is None
        before = response.json()["data"]
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TRIGGER isolated_scene_config_fail BEFORE INSERT ON audit_log FOR EACH ROW BEGIN IF NEW.action IN ('twin:objects','twin:create') THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ISOLATED_CONFIG_FAILURE'; END IF; END"
            )
        try:
            changed = [dict(row, name="应回滚") for row in rows]
            assert (
                client.put(
                    f"/api/v1/scenes/{value['id']}/objects", json={"objects": changed}
                ).status_code
                == 503
            )
            assert (
                client.post(
                    f"/api/v1/sites/{site_id}/scenes/from-template", json=payload
                ).status_code
                == 503
            )
        finally:
            with connection.cursor() as cursor:
                cursor.execute("DROP TRIGGER isolated_scene_config_fail")
        assert client.get(f"/api/v1/scenes/{value['id']}").json()["data"] == before
        assert client.get(f"/api/v1/sites/{site_id}/scenes").json()["meta"]["total"] == 4
        large_id = str(
            scalar(
                connection,
                "SELECT id FROM scene_template WHERE template_code='SERVICE_L' AND version_no=20261018",
            )
        )
        catalog = client.get(f"/api/v1/scene-templates/{large_id}/objects")
        assert catalog.status_code == 200 and len(catalog.json()["data"]["objectKeys"]) == 38


@pytest.fixture(scope="module")
def mock_bundle():
    """离线生成一次素材；不依赖真实MySQL或.env。"""
    return build_sql()


def test_export_is_complete_and_preserves_previous_output(tmp_path, mock_bundle):
    """检查19表全覆盖和生成器拒绝覆盖旧文件，防止测试凭据/批次被悄悄重置。"""
    sql, counts = mock_bundle
    assert set(counts) == set(TABLES) and len(TABLES) == 19
    assert counts["point_history"] == counts["device_point"] * 96 == 9216
    assert all(re.search(rf"INSERT INTO `?{table}`?\b", sql) for table in TABLES)
    assert not re.search(r"\b(?:UPDATE|DELETE|TRUNCATE)\s+", sql, re.IGNORECASE)
    assert "DROP TABLE" not in sql and "FOREIGN_KEY_CHECKS" not in sql
    paths = generate_bundle(tmp_path)
    before = [path.read_bytes() for path in paths]
    assert json.loads(paths[1].read_text(encoding="utf-8"))["expectedFixtureRows"] == counts
    with pytest.raises(ValueError, match="未覆盖"):
        generate_bundle(tmp_path)
    assert before == [path.read_bytes() for path in paths]


@pytest.fixture
def full_mysql():
    """仅重建已验证的独立实例中的测试库；禁止3306，datadir必须完全匹配专用路径。"""
    port = int(os.environ["SPT_TEST_MYSQL_PORT"])
    if port == 3306:
        pytest.fail("禁止指向用户MySQL默认端口")
    connection = pymysql.connect(
        host="127.0.0.1", port=port, user="root", password="", autocommit=True, charset="utf8mb4"
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT @@datadir")
            actual = str(cursor.fetchone()[0]).replace("\\", "/").lower().rstrip("/")
            expected = (ROOT / ".runtime/mysql-auth-integration").as_posix().lower()
            if actual != expected:
                pytest.fail("拒绝写入非专用测试数据目录")
            cursor.execute("DROP DATABASE IF EXISTS smart_power_twin")
            cursor.execute(
                "CREATE DATABASE smart_power_twin CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs"
            )
        execute_script(
            connection, (ROOT / "sql/C00全模块_建表_仅缺表时使用.sql").read_text(encoding="utf-8")
        )
        with connection.cursor() as cursor:
            # 故意错开ID起点，验收业务编码查找，不允许素材依赖1/2等固定主键。
            for table, start in [
                ("site", 101),
                ("device", 501),
                ("sys_user", 201),
                ("device_point", 1001),
            ]:
                cursor.execute(f"ALTER TABLE `{table}` AUTO_INCREMENT={start}")
        yield connection
    finally:
        connection.close()


def scalar(connection, sql, parameters=None):
    """执行验收查询并取单值；参数通过驱动绑定，不拼接用户输入。"""
    with connection.cursor() as cursor:
        cursor.execute(sql, parameters)
        return cursor.fetchone()[0]


@MYSQL_ONLY
def test_mysql_full_seed_repeat_and_relationships(full_mysql, mock_bundle):
    """空库首次/重复导入，核实19表数量、测点最新历史一致、绑定归属及告警权限。"""
    connection = full_mysql
    sql, expected = mock_bundle
    execute_script(connection, sql)
    first_time = scalar(
        connection, "SELECT occurred_at FROM audit_log WHERE request_id=%s", (BATCH,)
    )
    for table, count in expected.items():
        assert scalar(connection, f"SELECT COUNT(*) FROM `{table}`") == count, table
    assert (
        scalar(
            connection,
            "SELECT COUNT(*) FROM point_latest l JOIN point_history h ON h.point_id=l.point_id "
            "AND h.sampled_at=l.source_time AND h.source_sequence=l.source_sequence "
            "WHERE l.value_numeric <=> h.value_numeric AND l.value_text <=> h.value_text "
            "AND l.quality=h.quality",
        )
        == 96
    )
    assert (
        scalar(
            connection,
            "SELECT COUNT(*) FROM twin_binding b JOIN twin_object o ON o.id=b.object_id "
            "JOIN device_point p ON p.id=b.point_id WHERE b.site_id<>o.site_id "
            "OR b.site_id<>p.site_id OR b.device_id<>o.device_id OR b.device_id<>p.device_id",
        )
        == 0
    )
    assert (
        scalar(
            connection,
            "SELECT COUNT(*) FROM alarm_event a WHERE a.acknowledged_by IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM user_site_scope s WHERE s.user_id=a.acknowledged_by AND s.site_id=a.site_id)",
        )
        == 0
    )
    assert scalar(connection, "SELECT COUNT(*) FROM point_latest WHERE quality='BAD'") == 1
    assert (
        scalar(
            connection,
            "SELECT COUNT(*) FROM point_latest l JOIN device_point p ON p.id=l.point_id "
            "JOIN site s ON s.id=p.site_id WHERE s.code='DEMO_SERVICE_03' "
            "AND l.source_time=TIMESTAMPADD(HOUR,-2,%s)",
            (first_time,),
        )
        == 16
    )
    execute_script(connection, sql)
    for table, count in expected.items():
        assert scalar(connection, f"SELECT COUNT(*) FROM `{table}`") == count, table
    assert (
        scalar(connection, "SELECT occurred_at FROM audit_log WHERE request_id=%s", (BATCH,))
        == first_time
    )
    execute_script(
        connection, (ROOT / "sql/C02全模块_模拟数据核验.sql").read_text(encoding="utf-8")
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE USER IF NOT EXISTS 'spt_full_fixture'@'127.0.0.1' IDENTIFIED BY 'FullFixture!2026'"
        )
        cursor.execute("GRANT SELECT ON smart_power_twin.* TO 'spt_full_fixture'@'127.0.0.1'")
    settings = Settings(
        mysql_port=int(os.environ["SPT_TEST_MYSQL_PORT"]),
        mysql_user="spt_full_fixture",
        mysql_password="FullFixture!2026",
        token_secret="full-mock-test-only-signing-secret-2026",
        mysql_allow_writes=False,
        _env_file=None,
    )
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as client:
        for username, password, count in [
            ("sim_admin", "SimAdmin!2026", 6),
            ("sim_operator", "SimOperator!2026", 2),
            ("sim_viewer", "SimViewer!2026", 1),
        ]:
            result = client.post(
                "/api/v1/auth/login", json={"username": username, "password": password}
            )
            assert result.status_code == 200, result.text
            data = result.json()["data"]
            assert len(data["user"]["siteIds"]) == count
            client.headers["Authorization"] = "Bearer " + data["accessToken"]
            assert len(client.get("/api/v1/sites").json()["data"]) == count
        locked = client.post(
            "/api/v1/auth/login", json={"username": "sim_locked", "password": "SimLocked!2026"}
        )
        assert locked.status_code == 401


@MYSQL_ONLY
def test_mysql_existing_accounts_readings_and_scene_are_preserved(full_mysql, mock_bundle):
    """模拟已有账号/发布场景与后来人工修改；重跑不能重置密码、授权、最新值或告警处理。"""
    connection = full_mysql
    sql, _ = mock_bundle
    execute_script(connection, build_seed_sql("ExistingAdmin!2026", "ExistingViewer!2026"))
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO scene_template(template_code,name,site_type,scale_level,version_no,status,model_uri) "
            "VALUES('SERVICE_M','已有模板','SERVICE','M',1,'PUBLISHED','/existing.glb')"
        )
        cursor.execute(
            "INSERT INTO twin_scene(site_id,site_type,template_id,version_no,status,published_at) "
            "SELECT s.id,'SERVICE',t.id,1,'PUBLISHED',UTC_TIMESTAMP(3) FROM site s "
            "JOIN scene_template t ON t.template_code='SERVICE_M' AND t.version_no=1 "
            "WHERE s.code='HEBI_CHAOGE_SERVICE_DEMO'"
        )
    execute_script(connection, sql)
    assert (
        scalar(connection, "SELECT password FROM sys_user WHERE username='mysql_admin'")
        == "ExistingAdmin!2026"
    )
    assert (
        scalar(
            connection,
            "SELECT COUNT(*) FROM user_site_scope WHERE user_id=(SELECT id FROM sys_user WHERE username='mysql_admin')",
        )
        == 2
    )
    assert (
        scalar(
            connection,
            "SELECT status FROM twin_scene WHERE site_id=(SELECT id FROM site WHERE code='HEBI_CHAOGE_SERVICE_DEMO') AND version_no=20261016",
        )
        == "DRAFT"
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE sys_user SET password='Edited!2026',status='LOCKED' WHERE username='sim_viewer'"
        )
        cursor.execute(
            "DELETE FROM user_site_scope WHERE user_id=(SELECT id FROM sys_user WHERE username='sim_viewer')"
        )
        cursor.execute(
            "DELETE FROM role_permission WHERE role_id=(SELECT id FROM sys_role WHERE code='SIM_VIEWER')"
        )
        cursor.execute(
            "UPDATE point_latest SET value_numeric=987,quality='MANUAL' WHERE point_id=(SELECT MIN(id) FROM device_point WHERE value_type='NUMERIC')"
        )
        cursor.execute(
            "UPDATE alarm_event SET handling_note='人工已修改' WHERE event_key=%s",
            (BATCH + "-alarm-1",),
        )
    execute_script(connection, sql)
    assert (
        scalar(connection, "SELECT password FROM sys_user WHERE username='sim_viewer'")
        == "Edited!2026"
    )
    assert scalar(connection, "SELECT status FROM sys_user WHERE username='sim_viewer'") == "LOCKED"
    assert (
        scalar(
            connection,
            "SELECT COUNT(*) FROM user_site_scope WHERE user_id=(SELECT id FROM sys_user WHERE username='sim_viewer')",
        )
        == 0
    )
    assert (
        scalar(
            connection,
            "SELECT COUNT(*) FROM role_permission WHERE role_id=(SELECT id FROM sys_role WHERE code='SIM_VIEWER')",
        )
        == 0
    )
    assert (
        scalar(
            connection,
            "SELECT COUNT(*) FROM point_latest WHERE value_numeric=987 AND quality='MANUAL'",
        )
        == 1
    )
    assert (
        scalar(
            connection,
            "SELECT handling_note FROM alarm_event WHERE event_key=%s",
            (BATCH + "-alarm-1",),
        )
        == "人工已修改"
    )
    assert (
        scalar(
            connection,
            "SELECT version_no FROM twin_scene WHERE site_id=(SELECT id FROM site WHERE code='HEBI_CHAOGE_SERVICE_DEMO') AND status='PUBLISHED'",
        )
        == 1
    )


@MYSQL_ONLY
def test_mysql_conflict_stops_without_partial_data(full_mysql, mock_bundle):
    """同编码真实站点与模拟素材冲突时明确停止；已有站点保留，不留下半套新数据。"""
    connection = full_mysql
    execute_script(connection, build_seed_sql("ExistingAdmin!2026", "ExistingViewer!2026"))
    with connection.cursor() as cursor:
        cursor.execute("UPDATE site SET is_demo=0 WHERE code='HEBI_CHAOGE_SERVICE_DEMO'")
    before = {table: scalar(connection, f"SELECT COUNT(*) FROM `{table}`") for table in TABLES}
    with pytest.raises(pymysql.MySQLError, match="SIM_SITE_CODE_CONFLICT"):
        execute_script(connection, mock_bundle[0])
    assert before == {
        table: scalar(connection, f"SELECT COUNT(*) FROM `{table}`") for table in TABLES
    }
    assert scalar(connection, "SELECT IS_FREE_LOCK(%s)", (BATCH,)) == 1
    with connection.cursor() as cursor:
        cursor.execute("DROP PROCEDURE c_spt_mock_all_20261016")
        cursor.execute("UPDATE site SET is_demo=1 WHERE code='HEBI_CHAOGE_SERVICE_DEMO'")
        # 主动制造事务中段失败：此时前面的用户、资产、测点、历史已执行INSERT，应整体回滚。
        cursor.execute(
            "CREATE TRIGGER isolated_mock_fail BEFORE INSERT ON twin_binding FOR EACH ROW "
            "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ISOLATED_MOCK_MID_TRANSACTION_FAILURE'"
        )
    try:
        with pytest.raises(pymysql.MySQLError, match="ISOLATED_MOCK_MID_TRANSACTION_FAILURE"):
            execute_script(connection, mock_bundle[0])
        assert before == {
            table: scalar(connection, f"SELECT COUNT(*) FROM `{table}`") for table in TABLES
        }
        assert scalar(connection, "SELECT IS_FREE_LOCK(%s)", (BATCH,)) == 1
    finally:
        with connection.cursor() as cursor:
            cursor.execute("DROP TRIGGER isolated_mock_fail")
            cursor.execute("DROP PROCEDURE IF EXISTS c_spt_mock_all_20261016")


@MYSQL_ONLY
def test_mysql_monitoring_api_patch_and_concurrent_ingest(full_mysql, mock_bundle):
    """真实MySQL验证权限补丁、毫秒/大序号、并发幂等、迟到、只读和不生成告警。"""
    connection = full_mysql
    execute_script(connection, build_seed_sql("ExistingAdmin!2026", "ExistingViewer!2026"))
    patch = (ROOT / "sql/C03监测模块_权限初始化.sql").read_text(encoding="utf-8")
    execute_script(connection, patch)
    assert (
        scalar(
            connection,
            "SELECT COUNT(*) FROM role_permission rp JOIN sys_role r ON r.id=rp.role_id JOIN sys_permission p ON p.id=rp.permission_id WHERE r.code='ADMIN' AND p.code IN ('monitor:read','telemetry:write','monitor:configure')",
        )
        == 3
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE rp FROM role_permission rp JOIN sys_role r ON r.id=rp.role_id JOIN sys_permission p ON p.id=rp.permission_id WHERE r.code='VIEWER' AND p.code='monitor:read'"
        )
    execute_script(connection, patch)
    assert (
        scalar(
            connection,
            "SELECT COUNT(*) FROM role_permission rp JOIN sys_role r ON r.id=rp.role_id JOIN sys_permission p ON p.id=rp.permission_id WHERE r.code='VIEWER' AND p.code='monitor:read'",
        )
        == 0
    )
    assert (
        scalar(connection, "SELECT password FROM sys_user WHERE username='mysql_admin'")
        == "ExistingAdmin!2026"
    )
    execute_script(connection, mock_bundle[0])
    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE USER IF NOT EXISTS 'spt_monitor_fixture'@'127.0.0.1' IDENTIFIED BY 'MonitorFixture!2026'"
        )
        cursor.execute("GRANT SELECT ON smart_power_twin.* TO 'spt_monitor_fixture'@'127.0.0.1'")
        for table in ["device_point", "point_latest", "point_history"]:
            cursor.execute(
                f"GRANT INSERT,UPDATE ON smart_power_twin.`{table}` TO 'spt_monitor_fixture'@'127.0.0.1'"
            )
        cursor.execute(
            "GRANT INSERT ON smart_power_twin.audit_log TO 'spt_monitor_fixture'@'127.0.0.1'"
        )
    settings = Settings(
        mysql_port=int(os.environ["SPT_TEST_MYSQL_PORT"]),
        mysql_user="spt_monitor_fixture",
        mysql_password="MonitorFixture!2026",
        token_secret="isolated-monitoring-signing-secret-2026",
        mysql_allow_writes=True,
        _env_file=None,
    )
    with TestClient(create_app(settings), client=("127.0.0.1", 50005)) as client:
        login = client.post(
            "/api/v1/auth/login", json={"username": "sim_operator", "password": "SimOperator!2026"}
        )
        assert login.status_code == 200
        client.headers["Authorization"] = "Bearer " + login.json()["data"]["accessToken"]
        site = client.get("/api/v1/sites").json()["data"][0]
        device = client.get(f"/api/v1/sites/{site['id']}/devices").json()["data"][0]
        points = client.get(f"/api/v1/devices/{device['id']}/points").json()["data"]
        pid = next(p["id"] for p in points if p["code"] == "active_power")
        now = datetime.now(timezone(timedelta(hours=8)))
        entry = {
            "pointId": pid,
            "sampledAt": now.isoformat(),
            "sourceSequence": "9007199254740997",
            "valueNumeric": 12.34,
            "quality": "GOOD",
        }
        body = {"source": "SIMULATED", "samples": [entry]}

        def submit(_index):
            """独立HTTP会话并发提交相同批次；MySQL测点锁应只允许一次新历史写入。"""
            response = client.post("/api/v1/telemetry/batches", json=body)
            assert response.status_code == 200, response.text
            return response.json()["data"]

        with ThreadPoolExecutor(max_workers=4) as pool:
            stats = list(pool.map(submit, range(4)))
        assert sum(s["inserted"] for s in stats) == 1 and sum(s["duplicates"] for s in stats) == 3
        latest = client.get(f"/api/v1/devices/{device['id']}/latest").json()["data"]
        value = next(v for v in latest if v["pointId"] == pid)
        assert (
            value["valueNumeric"] == 12.34
            and value["sourceSequence"] == entry["sourceSequence"]
            and not value["isStale"]
        )
        assert (
            datetime.fromisoformat(value["sampledAt"].replace("Z", "+00:00")).microsecond % 1000
            == 0
        )
        late = {
            **entry,
            "sampledAt": (now - timedelta(minutes=2)).isoformat(),
            "sourceSequence": "1",
            "valueNumeric": 1.0,
        }
        assert (
            client.post(
                "/api/v1/telemetry/batches", json={"source": "SIMULATED", "samples": [late]}
            ).json()["data"]["latestUpdated"]
            == 0
        )
        response = client.get(
            f"/api/v1/points/{pid}/history",
            params={
                "startTime": (now - timedelta(minutes=3)).isoformat(),
                "endTime": (now + timedelta(minutes=1)).isoformat(),
            },
        )
        assert response.status_code == 200 and any(
            row["sourceSequence"] == entry["sourceSequence"]
            for row in response.json()["data"]["items"]
        )
        count = scalar(connection, "SELECT COUNT(*) FROM point_history")
        assert (
            client.post(
                "/api/v1/telemetry/batches",
                json={"source": "SIMULATED", "samples": [{**entry, "valueNumeric": 99}]},
            ).status_code
            == 409
        )
        assert scalar(connection, "SELECT COUNT(*) FROM point_history") == count
        assert scalar(connection, "SELECT COUNT(*) FROM alarm_event") == 6
    with TestClient(
        create_app(settings.model_copy(update={"mysql_allow_writes": False})),
        client=("127.0.0.1", 50006),
    ) as client:
        login = client.post(
            "/api/v1/auth/login", json={"username": "sim_operator", "password": "SimOperator!2026"}
        )
        client.headers["Authorization"] = "Bearer " + login.json()["data"]["accessToken"]
        assert client.post("/api/v1/telemetry/batches", json=body).status_code == 409


@MYSQL_ONLY
def test_mysql_alarm_permissions_concurrency_and_atomic_ingest(full_mysql, mock_bundle):
    """真MySQL：原账号补权、并发只触发一次、处置幂等、采样/事件/审计失败整体回滚。"""
    connection = full_mysql
    execute_script(connection, build_seed_sql("ExistingAdmin!2026", "ExistingViewer!2026"))
    execute_script(connection, mock_bundle[0])
    patch = (ROOT / "sql/C06告警模块_权限初始化.sql").read_text(encoding="utf-8")
    execute_script(connection, patch)
    count = scalar(connection, "SELECT COUNT(*) FROM role_permission")
    execute_script(connection, patch)
    assert scalar(connection, "SELECT COUNT(*) FROM role_permission") == count
    assert (
        scalar(connection, "SELECT password FROM sys_user WHERE username='mysql_admin'")
        == "ExistingAdmin!2026"
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE USER IF NOT EXISTS 'spt_alarm_fixture'@'127.0.0.1' IDENTIFIED BY 'AlarmFixture!2026'"
        )
        cursor.execute("GRANT SELECT ON smart_power_twin.* TO 'spt_alarm_fixture'@'127.0.0.1'")
        cursor.execute(
            "GRANT UPDATE(id) ON smart_power_twin.device_point TO 'spt_alarm_fixture'@'127.0.0.1'"
        )
        for table in ["point_history", "point_latest", "alarm_event"]:
            cursor.execute(
                f"GRANT INSERT,UPDATE ON smart_power_twin.{table} TO 'spt_alarm_fixture'@'127.0.0.1'"
            )
        cursor.execute(
            "GRANT INSERT ON smart_power_twin.audit_log TO 'spt_alarm_fixture'@'127.0.0.1'"
        )
    settings = Settings(
        mysql_port=int(os.environ["SPT_TEST_MYSQL_PORT"]),
        mysql_user="spt_alarm_fixture",
        mysql_password="AlarmFixture!2026",
        token_secret="isolated-alarm-signing-secret-2026",
        mysql_allow_writes=True,
        _env_file=None,
    )
    site_id = scalar(connection, "SELECT id FROM site WHERE code='HEBI_CHAOGE_TOLL_DEMO'")
    point_id = scalar(
        connection,
        "SELECT p.id FROM device_point p JOIN device d ON d.id=p.device_id WHERE d.site_id=%s AND d.code='TRANSFORMER_01' AND p.code='temperature'",
        (site_id,),
    )
    with TestClient(create_app(settings), client=("127.0.0.1", 50009)) as client:
        login = client.post(
            "/api/v1/auth/login", json={"username": "sim_admin", "password": "SimAdmin!2026"}
        )
        assert login.status_code == 200
        admin_headers = {"Authorization": "Bearer " + login.json()["data"]["accessToken"]}
        now = datetime.now(timezone.utc)

        def submit(value, sequence):
            """并发独立HTTP事务；源序号递增保护同一采样时刻的最新值顺序。"""
            return client.post(
                "/api/v1/telemetry/batches",
                headers=admin_headers,
                json={
                    "source": "SIMULATED",
                    "samples": [
                        {
                            "pointId": str(point_id),
                            "sampledAt": now.isoformat(),
                            "sourceSequence": sequence,
                            "valueNumeric": value,
                            "quality": "GOOD",
                        }
                    ],
                },
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(lambda i: submit(90, i), range(1, 5)))
        assert all(r.status_code == 200 for r in responses), [r.status_code for r in responses]
        response = client.get(
            "/api/v1/alarms",
            headers=admin_headers,
            params={"pointId": str(point_id), "status": "ACTIVE"},
        )
        assert response.status_code == 200
        managed = [
            e
            for e in response.json()["data"]
            if e["triggerSnapshot"].get("rule") == "numeric_threshold_v1"
        ]
        assert len(managed) == 1
        eid = managed[0]["id"]

        def acknowledge(_index):
            """重复确认应保留首次操作人/时间，只追加一次确认审计。"""
            return client.post(f"/api/v1/alarms/{eid}/acknowledge", headers=admin_headers, json={})

        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(acknowledge, range(4)))
        assert all(r.status_code == 200 for r in responses)
        assert len({r.json()["data"]["acknowledgedAt"] for r in responses}) == 1
        assert (
            scalar(
                connection,
                "SELECT COUNT(*) FROM audit_log WHERE action='alarm:ack' AND target_id=%s",
                (eid,),
            )
            == 1
        )
        assert submit(30, 5).status_code == 200
        assert (
            client.get(f"/api/v1/alarms/{eid}", headers=admin_headers).json()["data"]["status"]
            == "RECOVERED"
        )
        assert (
            client.post(f"/api/v1/alarms/{eid}/close", headers=admin_headers, json={}).json()[
                "data"
            ]["status"]
            == "CLOSED"
        )
        # 发生告警后审计失败，不能留下最新值、历史或事件；随后正常重传可再次成功。
        before_history = scalar(connection, "SELECT COUNT(*) FROM point_history")
        before_alarms = scalar(connection, "SELECT COUNT(*) FROM alarm_event")
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TRIGGER isolated_alarm_audit_fail BEFORE INSERT ON audit_log FOR EACH ROW BEGIN IF NEW.action='alarm:raise' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ISOLATED_ALARM_AUDIT_FAILURE'; END IF; END"
            )
        try:
            assert submit(90, 6).status_code == 503
        finally:
            with connection.cursor() as cursor:
                cursor.execute("DROP TRIGGER isolated_alarm_audit_fail")
        assert scalar(connection, "SELECT COUNT(*) FROM point_history") == before_history
        assert scalar(connection, "SELECT COUNT(*) FROM alarm_event") == before_alarms
        assert (
            scalar(
                connection,
                "SELECT source_sequence FROM point_latest WHERE point_id=%s",
                (point_id,),
            )
            == 5
        )
        assert submit(90, 6).status_code == 200
        for username, password in [
            ("mysql_admin", "ExistingAdmin!2026"),
            ("mysql_viewer", "ExistingViewer!2026"),
        ]:
            login = client.post(
                "/api/v1/auth/login", json={"username": username, "password": password}
            )
            assert login.status_code == 200
            permissions = login.json()["data"]["user"]["permissions"]
            headers = {"Authorization": "Bearer " + login.json()["data"]["accessToken"]}
            assert "alarm:read" in permissions
            assert client.get("/api/v1/alarms", headers=headers).status_code == 200
            if username == "mysql_viewer":
                assert "alarm:ack" not in permissions and "alarm:close" not in permissions
                assert client.get(f"/api/v1/alarms/{eid}", headers=headers).status_code == 404
                assert (
                    client.post(
                        f"/api/v1/alarms/{eid}/acknowledge", headers=headers, json={}
                    ).status_code
                    == 403
                )


@MYSQL_ONLY
def test_mysql_explicit_role_repair_preserves_accounts_and_scope(full_mysql, mock_bundle):
    """模拟旧补丁已执行但权限缺失；显式修复可恢复读取且不扩大viewer站点或写权限。"""
    connection = full_mysql
    execute_script(connection, build_seed_sql("ExistingAdmin!2026", "ExistingViewer!2026"))
    execute_script(connection, mock_bundle[0])
    for name in ["C03监测模块_权限初始化.sql", "C04三维模块_权限初始化.sql"]:
        execute_script(connection, (ROOT / "sql" / name).read_text(encoding="utf-8"))
    with connection.cursor() as cursor:
        cursor.execute("UPDATE sys_user SET username='admin' WHERE username='mysql_admin'")
        cursor.execute("UPDATE sys_user SET username='viewer' WHERE username='mysql_viewer'")
        cursor.execute(
            "DELETE rp FROM role_permission rp JOIN sys_role r ON r.id=rp.role_id "
            "JOIN sys_permission p ON p.id=rp.permission_id "
            "WHERE r.code IN ('ADMIN','VIEWER') AND p.code IN "
            "('monitor:read','monitor:configure','telemetry:write','twin:read','twin:publish')"
        )

    def account_snapshot():
        """只在内存比较账号和站点范围，确保修复不改密码或授权；不输出任何凭据。"""
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM sys_user ORDER BY id")
            accounts = cursor.fetchall()
            cursor.execute("SELECT * FROM user_site_scope ORDER BY user_id,site_id")
            return accounts, cursor.fetchall()

    before = account_snapshot()
    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE USER IF NOT EXISTS 'spt_repair_fixture'@'127.0.0.1' "
            "IDENTIFIED BY 'RepairFixture!2026'"
        )
        cursor.execute("GRANT SELECT ON smart_power_twin.* TO 'spt_repair_fixture'@'127.0.0.1'")
    settings = Settings(
        mysql_port=int(os.environ["SPT_TEST_MYSQL_PORT"]),
        mysql_user="spt_repair_fixture",
        mysql_password="RepairFixture!2026",
        token_secret="isolated-role-repair-signing-secret-2026",
        mysql_allow_writes=False,
        _env_file=None,
    )
    patch = (ROOT / "sql/C05管理员与观察员_模块权限修复.sql").read_text(encoding="utf-8")
    with TestClient(create_app(settings), client=("127.0.0.1", 50008)) as client:
        for username, password in [
            ("admin", "ExistingAdmin!2026"),
            ("viewer", "ExistingViewer!2026"),
        ]:
            login = client.post(
                "/api/v1/auth/login", json={"username": username, "password": password}
            )
            assert login.status_code == 200
            data = login.json()["data"]
            assert "twin:read" not in data["user"]["permissions"]
            client.headers["Authorization"] = "Bearer " + data["accessToken"]
            site_id = data["user"]["siteIds"][0]
            assert client.get(f"/api/v1/sites/{site_id}/scene").status_code == 403
        execute_script(connection, patch)
        count = scalar(connection, "SELECT COUNT(*) FROM role_permission")
        execute_script(connection, patch)
        assert scalar(connection, "SELECT COUNT(*) FROM role_permission") == count
        assert account_snapshot() == before
        for username, password in [
            ("admin", "ExistingAdmin!2026"),
            ("viewer", "ExistingViewer!2026"),
        ]:
            login = client.post(
                "/api/v1/auth/login", json={"username": username, "password": password}
            )
            assert login.status_code == 200
            data = login.json()["data"]
            permissions = set(data["user"]["permissions"])
            assert {"site:read", "device:read", "monitor:read", "twin:read"} <= permissions
            client.headers["Authorization"] = "Bearer " + data["accessToken"]
            for site_id in data["user"]["siteIds"]:
                assert client.get(f"/api/v1/sites/{site_id}/scene").status_code == 200
            if username == "viewer":
                assert permissions == {"site:read", "device:read", "monitor:read", "twin:read"}
                assert len(data["user"]["siteIds"]) == 1
                assert client.post(f"/api/v1/sites/{site_id}/scenes", json={}).status_code == 403
                toll_id = scalar(
                    connection, "SELECT id FROM site WHERE code='HEBI_CHAOGE_TOLL_DEMO'"
                )
                assert client.get(f"/api/v1/sites/{toll_id}/scene").status_code == 404
            else:
                assert {"twin:publish", "monitor:configure", "telemetry:write"} <= permissions


@MYSQL_ONLY
def test_mysql_twin_patch_concurrent_versions_and_failed_publish_rollback(full_mysql, mock_bundle):
    """真MySQL验收权限补丁、并发版本号、唯一当前场景及归档后失败的原子回滚。"""
    connection = full_mysql
    execute_script(connection, build_seed_sql("ExistingAdmin!2026", "ExistingViewer!2026"))
    patch = (ROOT / "sql/C04三维模块_权限初始化.sql").read_text(encoding="utf-8")
    execute_script(connection, patch)
    assert (
        scalar(
            connection,
            "SELECT COUNT(*) FROM role_permission rp JOIN sys_role r ON r.id=rp.role_id JOIN sys_permission p ON p.id=rp.permission_id WHERE r.code='ADMIN' AND p.code IN ('twin:read','twin:publish')",
        )
        == 2
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE rp FROM role_permission rp JOIN sys_role r ON r.id=rp.role_id JOIN sys_permission p ON p.id=rp.permission_id WHERE r.code='VIEWER' AND p.code='twin:read'"
        )
    execute_script(connection, patch)
    assert (
        scalar(
            connection,
            "SELECT COUNT(*) FROM role_permission rp JOIN sys_role r ON r.id=rp.role_id JOIN sys_permission p ON p.id=rp.permission_id WHERE r.code='VIEWER' AND p.code='twin:read'",
        )
        == 0
    )
    assert (
        scalar(connection, "SELECT password FROM sys_user WHERE username='mysql_admin'")
        == "ExistingAdmin!2026"
    )
    execute_script(connection, mock_bundle[0])
    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE USER IF NOT EXISTS 'spt_twin_fixture'@'127.0.0.1' IDENTIFIED BY 'TwinFixture!2026'"
        )
        cursor.execute("GRANT SELECT ON smart_power_twin.* TO 'spt_twin_fixture'@'127.0.0.1'")
        # MySQL行锁需要UPDATE权限；仅给站点id列作互斥锁，不授予整表台账编辑。
        cursor.execute(
            "GRANT UPDATE(id) ON smart_power_twin.site TO 'spt_twin_fixture'@'127.0.0.1'"
        )
        for table in ["twin_scene", "twin_object", "twin_binding"]:
            cursor.execute(
                f"GRANT INSERT,UPDATE,DELETE ON smart_power_twin.`{table}` TO 'spt_twin_fixture'@'127.0.0.1'"
            )
        cursor.execute(
            "GRANT INSERT ON smart_power_twin.audit_log TO 'spt_twin_fixture'@'127.0.0.1'"
        )
    settings = Settings(
        mysql_port=int(os.environ["SPT_TEST_MYSQL_PORT"]),
        mysql_user="spt_twin_fixture",
        mysql_password="TwinFixture!2026",
        token_secret="isolated-twin-signing-secret-2026",
        mysql_allow_writes=True,
        _env_file=None,
    )
    with TestClient(create_app(settings), client=("127.0.0.1", 50007)) as client:
        login = client.post(
            "/api/v1/auth/login", json={"username": "sim_admin", "password": "SimAdmin!2026"}
        )
        assert login.status_code == 200
        client.headers["Authorization"] = "Bearer " + login.json()["data"]["accessToken"]
        site_id = scalar(connection, "SELECT id FROM site WHERE code='HEBI_CHAOGE_SERVICE_DEMO'")
        current = client.get(f"/api/v1/sites/{site_id}/scene").json()["data"]
        assert len(current["objects"]) == 4 and len(current["bindings"]) == 16

        def clone(_index):
            """相同站点并发复制，站点锁和锁定当前读应分配四个不同版本。"""
            response = client.post(f"/api/v1/sites/{site_id}/scenes", json={})
            assert response.status_code == 201, response.text
            return response.json()["data"]

        with ThreadPoolExecutor(max_workers=4) as pool:
            drafts = list(pool.map(clone, range(4)))
        assert sorted(d["version"] for d in drafts) == list(
            range(current["version"] + 1, current["version"] + 5)
        )

        def publish(draft):
            """相同站点并发发布不同草稿，允许串行成功，但数据库最终只能有一个当前版本。"""
            response = client.post(f"/api/v1/scenes/{draft['id']}/publish")
            assert response.status_code == 200, response.text

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(publish, drafts[:2]))
        assert (
            scalar(
                connection,
                "SELECT COUNT(*) FROM twin_scene WHERE site_id=%s AND status='PUBLISHED'",
                (site_id,),
            )
            == 1
        )
        before = client.get(f"/api/v1/sites/{site_id}/scene").json()["data"]["id"]
        bad = drafts[2]
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TRIGGER isolated_twin_publish_fail BEFORE UPDATE ON twin_scene FOR EACH ROW BEGIN IF NEW.status='PUBLISHED' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ISOLATED_TWIN_PUBLISH_FAILURE'; END IF; END"
            )
        try:
            assert client.post(f"/api/v1/scenes/{bad['id']}/publish").status_code == 503
        finally:
            with connection.cursor() as cursor:
                cursor.execute("DROP TRIGGER isolated_twin_publish_fail")
        after = client.get(f"/api/v1/sites/{site_id}/scene").json()["data"]["id"]
        assert after == before
        assert (
            scalar(connection, "SELECT status FROM twin_scene WHERE id=%s", (bad["id"],)) == "DRAFT"
        )
        login = client.post(
            "/api/v1/auth/login", json={"username": "sim_viewer", "password": "SimViewer!2026"}
        )
        client.headers["Authorization"] = "Bearer " + login.json()["data"]["accessToken"]
        assert client.get(f"/api/v1/scenes/{bad['id']}").status_code == 404
        assert client.get(f"/api/v1/sites/{site_id}/scene").status_code == 200
        assert client.post(f"/api/v1/scenes/{bad['id']}/publish").status_code == 403
        assert scalar(connection, "SELECT COUNT(*) FROM point_history") == 9216
        assert scalar(connection, "SELECT COUNT(*) FROM alarm_event") == 6


@MYSQL_ONLY
def test_mysql_dashboard_read_only_scope_source_and_permission_patch(full_mysql, mock_bundle):
    """真实MySQL：只读账号聚合、源隔离、过期数据、权限补丁重跑及范围立即撤销。"""
    connection = full_mysql
    execute_script(connection, build_seed_sql("ExistingAdmin!2026", "ExistingViewer!2026"))
    execute_script(connection, mock_bundle[0])
    with connection.cursor() as cursor:
        cursor.execute("SELECT id,password,role_id,status FROM sys_user ORDER BY id")
        before = cursor.fetchall()
    patch = (ROOT / "sql/C08大屏汇总模块_权限初始化.sql").read_text(encoding="utf-8-sig")
    execute_script(connection, patch)
    execute_script(connection, patch)
    with connection.cursor() as cursor:
        cursor.execute("SELECT id,password,role_id,status FROM sys_user ORDER BY id")
        assert before == cursor.fetchall()
        cursor.execute(
            "CREATE USER IF NOT EXISTS 'spt_dashboard_fixture'@'127.0.0.1' IDENTIFIED BY 'DashboardFixture!2026'"
        )
        cursor.execute("GRANT SELECT ON smart_power_twin.* TO 'spt_dashboard_fixture'@'127.0.0.1'")
        # 固定素材若已过期不能贡献瞬时功率，再将本测试的PV最新值更新为新鲜值进行对照。
        cursor.execute("UPDATE point_latest SET source_time=UTC_TIMESTAMP(3)-INTERVAL 1 DAY")
    settings = Settings(
        mysql_port=int(os.environ["SPT_TEST_MYSQL_PORT"]),
        mysql_user="spt_dashboard_fixture",
        mysql_password="DashboardFixture!2026",
        token_secret="dashboard-read-only-integration-secret-2026",
        mysql_allow_writes=False,
        _env_file=None,
    )
    with TestClient(create_app(settings), client=("127.0.0.1", 50012)) as client:

        def login(username, password):
            response = client.post(
                "/api/v1/auth/login", json={"username": username, "password": password}
            )
            assert response.status_code == 200, response.text
            client.headers["Authorization"] = "Bearer " + response.json()["data"]["accessToken"]

        login("mysql_admin", "ExistingAdmin!2026")
        assert client.get("/api/v1/dashboard/summary").status_code == 200
        login("sim_admin", "SimAdmin!2026")
        stale = client.get("/api/v1/dashboard/summary?source=SIMULATED").json()["data"]
        assert stale["siteCount"] == 6 and stale["deviceCount"] == 24
        assert all(p["valueKw"] is None for p in stale["power"].values())
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE point_latest l JOIN device_point p ON p.id=l.point_id JOIN device d ON d.id=p.device_id SET l.source_time=UTC_TIMESTAMP(3),l.quality='GOOD',l.value_numeric=10 WHERE p.code='active_power' AND d.system_type='PV'"
            )
        fresh = client.get("/api/v1/dashboard/summary?source=SIMULATED").json()["data"]
        assert (
            fresh["power"]["PV"]["valueKw"] == 60 and fresh["power"]["PV"]["contributingSites"] == 6
        )
        assert (
            client.get("/api/v1/dashboard/summary").json()["data"]["power"]["PV"]["valueKw"] is None
        )
        login("sim_viewer", "SimViewer!2026")
        viewer = client.get("/api/v1/dashboard/summary?source=SIMULATED").json()["data"]
        assert viewer["siteCount"] == 1 and viewer["power"]["PV"]["valueKw"] == 10
        forbidden = scalar(connection, "SELECT id FROM site WHERE code='HEBI_CHAOGE_TOLL_DEMO'")
        assert client.get(f"/api/v1/dashboard/summary?siteId={forbidden}").status_code == 404
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM user_site_scope WHERE user_id=(SELECT id FROM sys_user WHERE username='sim_viewer')"
            )
        assert client.get("/api/v1/dashboard/summary").json()["data"]["siteCount"] == 0


@MYSQL_ONLY
def test_mysql_asset_maintenance_scope_atomicity_and_parent_lock(full_mysql, mock_bundle):
    """实际MySQL验证新站范围、可重复补权、最小写权限、重复编码及并发防父环。"""
    from tests.test_asset_maintenance import device_body, device_edit, site_body

    connection = full_mysql
    execute_script(connection, build_seed_sql("ExistingAdmin!2026", "ExistingViewer!2026"))
    execute_script(connection, mock_bundle[0])
    patch = (ROOT / "sql/C09站点设备台账维护_权限初始化.sql").read_text(encoding="utf-8-sig")
    execute_script(connection, patch)
    execute_script(connection, patch)
    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE USER IF NOT EXISTS 'spt_asset_fixture'@'127.0.0.1' IDENTIFIED BY 'AssetFixture!2026'"
        )
        cursor.execute("GRANT SELECT ON smart_power_twin.* TO 'spt_asset_fixture'@'127.0.0.1'")
        for table in ["site", "device", "site_route_link"]:
            cursor.execute(
                f"GRANT INSERT,UPDATE ON smart_power_twin.{table} TO 'spt_asset_fixture'@'127.0.0.1'"
            )
        for table in ["user_site_scope", "audit_log"]:
            cursor.execute(
                f"GRANT INSERT ON smart_power_twin.{table} TO 'spt_asset_fixture'@'127.0.0.1'"
            )
    settings = Settings(
        mysql_port=int(os.environ["SPT_TEST_MYSQL_PORT"]),
        mysql_user="spt_asset_fixture",
        mysql_password="AssetFixture!2026",
        token_secret="asset-maintenance-isolated-secret-2026",
        mysql_allow_writes=True,
        _env_file=None,
    )
    with TestClient(create_app(settings), client=("127.0.0.1", 50013)) as client:
        response = client.post(
            "/api/v1/auth/login", json={"username": "sim_admin", "password": "SimAdmin!2026"}
        )
        assert response.status_code == 200
        client.headers["Authorization"] = "Bearer " + response.json()["data"]["accessToken"]
        result = client.post("/api/v1/sites", json=site_body())
        assert result.status_code == 201, result.text
        sid = result.json()["data"]["id"]
        assert sid in client.get("/api/v1/auth/me").json()["data"]["siteIds"]
        assert client.get("/api/v1/sites/" + sid + "/scene").status_code == 404

        def create_duplicate(_):
            return client.post(f"/api/v1/sites/{sid}/devices", json=device_body()).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(create_duplicate, range(2))) == [201, 409]
        did = client.get(f"/api/v1/sites/{sid}/devices").json()["data"][0]["id"]
        another = client.post(
            f"/api/v1/sites/{sid}/devices", json={**device_body(), "code": "SECOND"}
        )
        assert another.status_code == 201, another.text
        other = another.json()["data"]["id"]

        def set_parent(pair):
            child, parent = pair
            return client.put(
                f"/api/v1/sites/{sid}/devices/{child}", json=device_edit(parentDeviceId=parent)
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(set_parent, [(did, other), (other, did)])) == [200, 409]
        # 人为使审计写入失败，确认之前flush过的新增站点和创建者范围整体回滚。
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TRIGGER isolated_asset_audit_fail BEFORE INSERT ON audit_log FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='isolated asset audit failure'"
            )
        try:
            failed = client.post("/api/v1/sites", json={**site_body(), "code": "ROLLBACK_SITE"})
            assert failed.status_code >= 400
            assert scalar(connection, "SELECT COUNT(*) FROM site WHERE code='ROLLBACK_SITE'") == 0
        finally:
            with connection.cursor() as cursor:
                cursor.execute("DROP TRIGGER isolated_asset_audit_fail")
        # 原观察员权限/站点数保持；不能写新站也不能查新站。
        viewer = client.post(
            "/api/v1/auth/login", json={"username": "sim_viewer", "password": "SimViewer!2026"}
        ).json()["data"]
        headers = {"Authorization": "Bearer " + viewer["accessToken"]}
        assert len(viewer["user"]["siteIds"]) == 1
        assert client.get("/api/v1/sites/" + sid, headers=headers).status_code == 404
        assert client.post("/api/v1/sites", json=site_body(), headers=headers).status_code == 403
