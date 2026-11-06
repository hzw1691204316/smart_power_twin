"""生成供用户手动导入的MySQL脚本；本程序只使用临时SQLite素材，不连接MySQL。

密码按用户要求以明文进入SQL和账号表；输出为本地敏感文件，不提交仓库。
已有同名输出文件时拒绝覆盖，防止重新生成的密码与已导入账号不一致。
"""

import argparse
import json
import re
from decimal import Decimal
from pathlib import Path
from secrets import token_urlsafe

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.validation import AUTH_ASSET_TABLES as ACTIVE_TABLES
from app.modules.assets.models import Device, HighwayRoute, Site, SiteArea, SiteRouteLink
from scripts.sample_assets import create_sample_database

SEED_FILE = "C01账号模块_MySQL初始化数据.sql"
SCHEMA_FILE = "C00账号模块_MySQL所需表_仅缺表时使用.sql"
CHECK_FILE = "C02账号模块_MySQL导入核验.sql"
PASSWORD_FILE = "C账号模块_MySQL初始账号.md"
ADMIN_USERNAME = "mysql_admin"
VIEWER_USERNAME = "mysql_viewer"
PERMISSIONS = {
    "site:read": "查询授权站点与区域",
    "device:read": "查询授权站点设备",
    "system:read": "查询账号与角色目录",
    "user:manage": "开户、授权及账号状态维护",
    "audit:read": "查询范围内审计",
}


def literal(value):
    """将固定种子素材转为SQL常量；脚本明确使用NO_BACKSLASH_ESCAPES，单引号双写。"""
    if value is None:
        return "NULL"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (dict, list)):
        return "CAST(" + literal(json.dumps(value, ensure_ascii=False)) + " AS JSON)"
    return "'" + str(value).replace("'", "''") + "'"


def lookup(table, column, value):
    """按唯一业务编码查实际数据库ID，不预设自增主键；参数来自固定表/列白名单素材。"""
    return f"(SELECT id FROM `{table}` WHERE `{column}` = {literal(value)})"


def insert_missing(table, values, condition):
    """参数values为列→SQL表达式；按condition缺失时插入，已有记录不更新、不删除。"""
    columns = ", ".join(f"`{name}`" for name in values)
    expressions = ", ".join(values.values())
    return (
        f"  INSERT INTO `{table}` ({columns})\n    SELECT {expressions} FROM DUAL\n"
        f"    WHERE NOT EXISTS (SELECT 1 FROM `{table}` WHERE {condition});\n"
    )


def row_values(row):
    """复制原演示台账字段，但不复制主键和时间；归属列由调用者替换成业务编码查找。"""
    return {
        column.name: literal(getattr(row, column.name))
        for column in row.__table__.columns
        if column.name not in {"id", "created_at", "updated_at"}
    }


def build_seed_sql(admin_password, viewer_password):
    """生成一个带异常回滚的MySQL8存储过程脚本；返回文本，不执行任何MySQL语句。

    账号仅缺失时创建，初始站点授权仅给本次新建账号；重跑不重置旧密码、不恢复撤销的授权。
    """
    statements = []
    for code, name in [("ADMIN", "管理员"), ("VIEWER", "只读观察员")]:
        statements.append(
            insert_missing(
                "sys_role", {"code": literal(code), "name": literal(name)}, f"code={literal(code)}"
            )
        )
    for code, name in PERMISSIONS.items():
        statements.append(
            insert_missing(
                "sys_permission",
                {"code": literal(code), "name": literal(name)},
                f"code={literal(code)}",
            )
        )
    for role, codes in [("ADMIN", PERMISSIONS), ("VIEWER", ["site:read", "device:read"])]:
        for code in codes:
            role_id = lookup("sys_role", "code", role)
            permission_id = lookup("sys_permission", "code", code)
            statements.append(
                insert_missing(
                    "role_permission",
                    {"role_id": role_id, "permission_id": permission_id},
                    f"role_id={role_id} AND permission_id={permission_id}",
                )
            )

    engine = create_sample_database()
    try:
        with Session(engine) as session:
            sites = session.scalars(select(Site).order_by(Site.id)).all()
            site_codes = {site.id: site.code for site in sites}
            routes = session.scalars(select(HighwayRoute)).all()
            route_codes = {route.id: route.route_code for route in routes}
            areas = session.scalars(select(SiteArea)).all()
            area_codes = {area.id: (area.site_id, area.code) for area in areas}
            for route in routes:
                statements.append(
                    insert_missing(
                        "highway_route",
                        row_values(route),
                        f"route_code={literal(route.route_code)}",
                    )
                )
            for site in sites:
                statements.append(
                    insert_missing("site", row_values(site), f"code={literal(site.code)}")
                )
            for area in areas:
                values = row_values(area)
                values["site_id"] = lookup("site", "code", site_codes[area.site_id])
                statements.append(
                    insert_missing(
                        "site_area",
                        values,
                        f"site_id={values['site_id']} AND code={literal(area.code)}",
                    )
                )
            for link in session.scalars(select(SiteRouteLink)):
                values = row_values(link)
                values["site_id"] = lookup("site", "code", site_codes[link.site_id])
                values["route_id"] = lookup(
                    "highway_route", "route_code", route_codes[link.route_id]
                )
                statements.append(
                    insert_missing(
                        "site_route_link",
                        values,
                        f"site_id={values['site_id']} AND link_code={literal(link.link_code)}",
                    )
                )
            for device in session.scalars(select(Device)):
                values = row_values(device)
                values["site_id"] = lookup("site", "code", site_codes[device.site_id])
                area_site, area_code = area_codes[device.area_id]
                values["area_id"] = (
                    "(SELECT id FROM site_area WHERE site_id="
                    + lookup("site", "code", site_codes[area_site])
                    + f" AND code={literal(area_code)})"
                )
                statements.append(
                    insert_missing(
                        "device",
                        values,
                        f"site_id={values['site_id']} AND code={literal(device.code)}",
                    )
                )
    finally:
        engine.dispose()

    for username, password, role, label, flag, codes in [
        (
            ADMIN_USERNAME,
            admin_password,
            "ADMIN",
            "MySQL初始管理员",
            "v_new_admin",
            list(site_codes.values()),
        ),
        (
            VIEWER_USERNAME,
            viewer_password,
            "VIEWER",
            "MySQL只读观察员",
            "v_new_viewer",
            [site_codes[1]],
        ),
    ]:
        username_sql = literal(username)
        statements.append(
            f"  SET {flag} = NOT EXISTS (SELECT 1 FROM sys_user WHERE username={username_sql});\n"
        )
        statements.append(
            insert_missing(
                "sys_user",
                {
                    "username": username_sql,
                    "password": literal(password),
                    "display_name": literal(label),
                    "role_id": lookup("sys_role", "code", role),
                    "status": "'ACTIVE'",
                },
                f"username={username_sql}",
            )
        )
        user_id = lookup("sys_user", "username", username)
        statements.append(f"  IF {flag} THEN\n")
        for code in codes:
            site_id = lookup("site", "code", code)
            statements.append(
                insert_missing(
                    "user_site_scope",
                    {"user_id": user_id, "site_id": site_id},
                    f"user_id={user_id} AND site_id={site_id}",
                )
            )
        statements.append(
            f"  INSERT INTO audit_log (actor_id,action,target_type,target_id,request_id,occurred_at,after_json)\n"
            f"    VALUES ({lookup('sys_user', 'username', ADMIN_USERNAME)},'user:bootstrap','user',CAST({user_id} AS CHAR),UUID(),UTC_TIMESTAMP(3),JSON_OBJECT('username',{username_sql},'source','manual_mysql_seed'));\n  END IF;\n"
        )

    names = ",".join(literal(name) for name in ACTIVE_TABLES)
    return f"""-- C01账号模块MySQL初始化数据；生成日期2026-10-15；兼容MySQL8.0.16+/8.4。
-- 用户手动执行，应用不自动导入。固定目标：smart_power_twin。
-- 数据：两角色、五权限、两账号、朝歌两站、S26、六区域、八设备；台账均明确演示。
-- 先确认11张所需表已有且为InnoDB；缺表才运行C00，已有19表勿重建。
-- 密码为随机初始值，见同目录C账号模块_MySQL初始账号.md；按用户要求在password列明文保存。
-- 不用REPLACE/INSERT IGNORE，不删除或更新已有业务记录，不重置旧密码/状态/授权。
-- 会补齐ADMIN/VIEWER角色的本模块权限；同编码角色若有额外动作则停止，请人工核对。
-- 含DELIMITER：用支持完整脚本的客户端执行；不要用--force忽略错误。
-- 仅创建/清理本脚本的辅助存储过程；需要CREATE ROUTINE/ALTER ROUTINE/EXECUTE及数据权限。
-- 请在独立SQL会话执行，避免存储过程DDL隐式提交该会话中其他未提交工作。
USE `smart_power_twin`;
SET @c_spt_old_zone = @@session.time_zone;
SET @c_spt_old_mode = @@session.sql_mode;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;
SET SESSION time_zone='+00:00';
SET SESSION sql_mode='STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION,NO_BACKSLASH_ESCAPES';
DROP PROCEDURE IF EXISTS `c_spt_auth_seed_20261015`;
DELIMITER $$
CREATE PROCEDURE `c_spt_auth_seed_20261015`() SQL SECURITY INVOKER
BEGIN
  DECLARE v_new_admin BOOLEAN DEFAULT FALSE;
  DECLARE v_new_viewer BOOLEAN DEFAULT FALSE;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;
  START TRANSACTION;
  IF DATABASE() <> 'smart_power_twin' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='WRONG_DATABASE';
  END IF;
  IF (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()
        AND table_name IN ({names}) AND engine='InnoDB') <> 11 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='REQUIRED_11_INNODB_TABLES_MISSING';
  END IF;
  IF EXISTS (SELECT 1 FROM sys_role r JOIN role_permission rp ON rp.role_id=r.id
      JOIN sys_permission p ON p.id=rp.permission_id WHERE
      (r.code='ADMIN' AND p.code NOT IN ('site:read','device:read','system:read','user:manage','audit:read'))
      OR (r.code='VIEWER' AND p.code NOT IN ('site:read','device:read'))) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='EXISTING_ROLE_HAS_EXTRA_PERMISSIONS';
  END IF;
  IF EXISTS (SELECT 1 FROM site WHERE
      (code='HEBI_CHAOGE_SERVICE_DEMO' AND (site_type<>'SERVICE' OR is_demo<>1)) OR
      (code='HEBI_CHAOGE_TOLL_DEMO' AND (site_type<>'TOLL' OR is_demo<>1))) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='EXISTING_SITE_CODE_CONFLICT';
  END IF;
{"".join(statements)}
  COMMIT;
  SELECT username,display_name,status,
    CASE WHEN (username='{ADMIN_USERNAME}' AND v_new_admin) OR (username='{VIEWER_USERNAME}' AND v_new_viewer)
      THEN 'CREATED' ELSE 'EXISTS_NOT_CHANGED' END AS import_result
    FROM sys_user WHERE username IN ('{ADMIN_USERNAME}','{VIEWER_USERNAME}');
END$$
DELIMITER ;
CALL `c_spt_auth_seed_20261015`();
DROP PROCEDURE `c_spt_auth_seed_20261015`;
SET SESSION time_zone=@c_spt_old_zone;
SET SESSION sql_mode=@c_spt_old_mode;
"""


def build_schema_sql(schema_text):
    """只摘取原19表方案中11张活动表；保留原外键顺序，IF NOT EXISTS不会修复旧结构。"""
    tables = re.findall(r"CREATE TABLE `([^`]+)` \(.*?\) ENGINE=InnoDB.*?;", schema_text, re.S)
    statements = re.findall(r"CREATE TABLE `[^`]+` \(.*?\) ENGINE=InnoDB.*?;", schema_text, re.S)
    selected = [
        statement.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
        for name, statement in zip(tables, statements)
        if name in ACTIVE_TABLES
    ]
    if len(selected) != 11:
        raise ValueError("原SQL未能提取完整11张活动表，停止生成")
    selected = [
        statement.replace("`password_hash`", "`password`").replace(
            "密码哈希，禁止明文", "网页登录密码，本机学习模式明文保存"
        )
        for statement in selected
    ]
    return (
        "-- C00可选：仅在活动表缺失时使用；已有19张表无需执行。\n"
        "-- IF NOT EXISTS不会改造已有旧表，结构不符需人工核对，不删库/表。\n"
        "-- DDL隐式提交，不能保证整份建表原子回滚。目标MySQL8.0.16+/8.4，非MariaDB。\n"
        "USE `smart_power_twin`;\nSET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;\n\n"
        + "\n\n".join(selected)
        + "\n"
    )


CHECK_SQL = """-- C02只读核验：不读取password，不修改任何数据。
USE `smart_power_twin`;
SELECT VERSION() AS mysql_version, DATABASE() AS current_database;
SELECT r.code AS role_code,p.code AS permission_code FROM sys_role r
 JOIN role_permission rp ON rp.role_id=r.id JOIN sys_permission p ON p.id=rp.permission_id
 WHERE r.code IN ('ADMIN','VIEWER') ORDER BY r.code,p.code;
SELECT u.id,u.username,u.display_name,u.status,r.code AS role_code,s.code AS site_code,s.name
 FROM sys_user u JOIN sys_role r ON r.id=u.role_id
 LEFT JOIN user_site_scope uss ON uss.user_id=u.id LEFT JOIN site s ON s.id=uss.site_id
 WHERE u.username IN ('mysql_admin','mysql_viewer') ORDER BY u.username,s.code;
SELECT s.code,s.name,s.is_demo,COUNT(DISTINCT a.id) AS area_count,COUNT(DISTINCT d.id) AS device_count
 FROM site s LEFT JOIN site_area a ON a.site_id=s.id LEFT JOIN device d ON d.site_id=s.id
 WHERE s.code IN ('HEBI_CHAOGE_SERVICE_DEMO','HEBI_CHAOGE_TOLL_DEMO') GROUP BY s.id,s.code,s.name,s.is_demo;
-- 每站3区域/4设备；管理员两站，观察员仅服务区；ADMIN五权限/VIEWER两权限。
SELECT u.username,COUNT(*) AS bootstrap_audits FROM audit_log a JOIN sys_user u ON u.id=a.actor_id
 WHERE a.action='user:bootstrap' GROUP BY u.username;
"""


def generate_bundle(output: Path, schema: Path):
    """向output独占写入四文件，返回路径列表；已存在任何同名文件则停止，不重置密码。"""
    output.mkdir(parents=True, exist_ok=True)
    paths = [output / name for name in [SCHEMA_FILE, SEED_FILE, CHECK_FILE, PASSWORD_FILE]]
    if any(path.exists() for path in paths):
        raise ValueError(
            "输出中已有本模块脚本/账号说明，请保留原密码；需要新一套时指定新的输出目录"
        )
    admin_password, viewer_password = token_urlsafe(18), token_urlsafe(18)
    schema_sql = build_schema_sql(schema.read_text(encoding="utf-8-sig"))
    seed_sql = build_seed_sql(admin_password, viewer_password)
    passwords = f"""# MySQL初始登录账号（仅本地保存）

生成日期：2026-10-15。对应同目录`{SEED_FILE}`，不是MySQL数据库连接账号。

| Web登录账号 | 随机初始密码 | 初始范围 |
|---|---|---|
| `{ADMIN_USERNAME}` | `{admin_password}` | 朝歌服务区和收费站，账号管理 |
| `{VIEWER_USERNAME}` | `{viewer_password}` | 仅朝歌服务区，只读 |

首次导入创建账号才使用以上密码。若导入结果为EXISTS_NOT_CHANGED，沿用数据库中已有账号密码、状态和授权；本脚本不会重置它们。
不要重新生成同名脚本来重置密码，不要把本说明提交仓库或公开分享。当前尚无网页改密入口。
"""
    for path, content in zip(paths, [schema_sql, seed_sql, CHECK_SQL, passwords]):
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    return paths


def main():
    """CLI仅打印生成文件名，不输出随机密码或哈希；可指定原SQL及输出目录。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path.home() / "Desktop/智慧电力文档")
    parser.add_argument(
        "--schema", type=Path, default=Path.home() / "Desktop/C智慧电力系统_MySQL建表.sql"
    )
    args = parser.parse_args()
    try:
        for path in generate_bundle(args.output, args.schema):
            print("已生成：" + path.name)
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
