"""MySQL启动预检：只读取元数据，发现缺表、缺字段、主键或引擎不符即停止；不自动修库。"""

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import Base

# 固定已启用的十九表，dashboard从业务表汇总，不额外创建统计实体表。
AUTH_ASSET_TABLES = (
    "sys_role",
    "sys_permission",
    "role_permission",
    "sys_user",
    "user_site_scope",
    "audit_log",
    "site",
    "site_area",
    "device",
    "highway_route",
    "site_route_link",
)
MONITORING_TABLES = ("device_point", "point_latest", "point_history")
TWIN_TABLES = ("scene_template", "twin_scene", "twin_object", "twin_binding")
ALARM_TABLES = ("alarm_event",)
ACTIVE_TABLES = AUTH_ASSET_TABLES + MONITORING_TABLES + TWIN_TABLES + ALARM_TABLES


def validate_mysql_schema(engine):
    """检查engine的当前库是否支持账号、台账、监测、三维绑定和告警模块。

    返回None代表所需表、字段、主键和事务引擎预检通过，不代表初始账号已导入。
    连接/权限错误只给出脱敏说明；不会建表、写入、补列或回退演示数据。
    """
    try:
        inspector = inspect(engine)
        missing = set(ACTIVE_TABLES) - set(inspector.get_table_names())
        if missing:
            raise RuntimeError(
                "MySQL缺少模块所需表：" + ", ".join(sorted(missing)) + "；请先手动导入表结构"
            )
        for name in ACTIVE_TABLES:
            expected = Base.metadata.tables[name]
            columns = {column["name"] for column in inspector.get_columns(name)}
            absent = set(expected.columns.keys()) - columns
            if absent:
                raise RuntimeError(
                    f"MySQL表{name}缺少字段：{', '.join(sorted(absent))}；不会自动修改已有表"
                )
            primary = set(inspector.get_pk_constraint(name)["constrained_columns"])
            if primary != {column.name for column in expected.primary_key}:
                raise RuntimeError(f"MySQL表{name}主键与模块约定不符，请核对已有SQL版本")
            engine_name = inspector.get_table_options(name).get("mysql_engine", "")
            if str(engine_name).upper() != "INNODB":
                raise RuntimeError(f"MySQL表{name}必须使用InnoDB，以保证账号、授权和审计事务")
    except SQLAlchemyError:
        raise RuntimeError(
            "MySQL连接或表结构读取失败；请检查本地配置、服务、端口和数据库账号权限"
        ) from None
