"""离线生成19表的全模块模拟数据包，不读取本地凭据，不连接MySQL。

SQL由用户手动导入。新模拟账号独立命名，已有账号/授权/最新值不覆盖；批次时刻固定后可重跑。
"""

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.assets.models import Device, HighwayRoute, Site, SiteArea, SiteRouteLink
from scripts.generate_auth_mysql_seed import insert_missing, literal, lookup, row_values
from scripts.sample_assets import create_sample_database

ROOT = Path(__file__).resolve().parents[1]
BATCH = "sim-full-v1-20261016"
VERSION = 20261016
SEQUENCE = 20261016
TABLES = (
    "sys_role",
    "sys_permission",
    "role_permission",
    "sys_user",
    "highway_route",
    "site",
    "user_site_scope",
    "site_area",
    "site_route_link",
    "device",
    "device_point",
    "point_latest",
    "point_history",
    "scene_template",
    "twin_scene",
    "twin_object",
    "twin_binding",
    "alarm_event",
    "audit_log",
)
PERMISSIONS = {
    "site:read": "查询授权站点",
    "device:read": "查询授权设备",
    "system:read": "查询账号角色",
    "user:manage": "管理账号授权",
    "audit:read": "查询审计",
    "monitor:read": "查询电力监测",
    "telemetry:write": "提交采样数据",
    "monitor:configure": "维护测点配置",
    "twin:read": "查询孪生场景",
    "twin:publish": "发布孪生场景",
    "alarm:read": "查询告警",
    "alarm:ack": "确认告警",
    "alarm:close": "关闭告警",
    "dashboard:read": "查询大屏汇总",
    "site:create": "新增业务站点",
    "asset:manage": "维护站点与设备台账",
}
ROLE_PERMISSIONS = {
    "SIM_ADMIN": list(PERMISSIONS),
    "SIM_OPERATOR": [
        "site:read",
        "device:read",
        "monitor:read",
        "telemetry:write",
        "twin:read",
        "alarm:read",
        "alarm:ack",
        "alarm:close",
        "dashboard:read",
    ],
    "SIM_VIEWER": [
        "site:read",
        "device:read",
        "monitor:read",
        "twin:read",
        "alarm:read",
        "dashboard:read",
    ],
}
ACCOUNTS = [
    ("sim_admin", "SimAdmin!2026", "模拟管理员", "SIM_ADMIN", "ACTIVE", 6),
    ("sim_operator", "SimOperator!2026", "模拟值班员", "SIM_OPERATOR", "ACTIVE", 2),
    ("sim_viewer", "SimViewer!2026", "模拟观察员", "SIM_VIEWER", "ACTIVE", 1),
    ("sim_locked", "SimLocked!2026", "模拟锁定账号", "SIM_VIEWER", "LOCKED", 1),
]
OBJECT_KEYS = {
    "ESS_01": "storage_01",
    "TRANSFORMER_01": "transformer_01",
    "PV_01": "pv_canopy",
    "CHARGER_01": "charger_01",
}
EXTRA_SITES = [
    (3, "DEMO_SERVICE_02", "洛阳服务区 · 演示", "SERVICE", "洛阳市", 112.52, 34.76, "G30"),
    (4, "DEMO_TOLL_02", "开封收费站 · 演示", "TOLL", "开封市", 114.3, 34.84, "G30"),
    (5, "DEMO_SERVICE_03", "许昌服务区 · 演示", "SERVICE", "许昌市", 113.93, 34.04, "G4"),
    (6, "DEMO_TOLL_03", "新乡收费站 · 演示", "TOLL", "新乡市", 113.94, 35.3, "G4"),
]


def model_manifest(kind):
    """核对中型GLB的四个稳定对象键，返回本地模型URI与模拟资源说明，不修改文件。"""
    uri = f"/models/{kind.lower()}_medium.glb" if kind == "SERVICE" else "/models/toll_medium.glb"
    path = ROOT / "smart_power_web/public" / uri.lstrip("/")
    with path.open("rb") as stream:
        magic, version, total = struct.unpack("<III", stream.read(12))
        size, chunk = struct.unpack("<II", stream.read(8))
        if magic != 0x46546C67 or version != 2 or chunk != 0x4E4F534A or size + 20 > total:
            raise ValueError("GLB文件格式异常")
        names = {node.get("name", "") for node in json.loads(stream.read(size)).get("nodes", [])}
    if any(
        key not in names and not any(name.startswith(key + "_") for name in names)
        for key in OBJECT_KEYS.values()
    ):
        raise ValueError("GLB缺少既有设备对象键")
    return uri, {
        "isSimulated": True,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "note": "第四版通用模型，仅作本地模拟；不是站点实景测绘",
        "objectKeys": list(OBJECT_KEYS.values()),
    }


def point_specs(code):
    """返回每台设备四个测点：编码、名称、单位、类型、聚合方式、低/高阈值。"""
    common = ("active_power", "有功功率", "kW", "NUMERIC", "INSTANT", None, None)
    temperature = ("temperature", "设备温度", "°C", "NUMERIC", "INSTANT", None, 55)
    energy = ("total_energy", "累计电量", "kWh", "NUMERIC", "COUNTER", None, None)
    online = ("online", "在线状态", "BOOL", "BOOLEAN", "STATE", None, None)
    if code == "ESS_01":
        return [common, ("soc", "荷电状态", "%", "NUMERIC", "INSTANT", 15, 95), temperature, online]
    if code == "TRANSFORMER_01":
        return [
            common,
            ("voltage", "线电压", "V", "NUMERIC", "INSTANT", 340, 420),
            ("temperature", "变压器温度", "°C", "NUMERIC", "INSTANT", None, 65),
            energy,
        ]
    if code == "PV_01":
        return [
            common,
            energy,
            ("temperature", "组件温度", "°C", "NUMERIC", "INSTANT", None, 75),
            ("operation_state", "并网状态", "TEXT", "TEXT", "STATE", None, None),
        ]
    return [common, energy, temperature, online]


def sample_expression(site_index, device_code, point_code):
    """生成确定性曲线表达式；n为0—95，代表每15分钟一次，共24小时，不使用随机数。"""
    if point_code == "operation_state":
        return "NULL", literal("模拟并网运行"), "'GOOD'"
    if point_code == "online":
        return ("IF(n=95,0,1)" if site_index == 5 else "1"), "NULL", "'GOOD'"
    if point_code == "soc":
        value = "ROUND(60 + 12*SIN(n*PI()/24),2)"
        if site_index == 4:
            value = f"IF(n>=94,12,{value})"
    elif point_code == "voltage":
        value = "ROUND(380+5*SIN(n*PI()/12),2)"
    elif point_code == "total_energy":
        value = f"ROUND({10000 + site_index * 1000}+n*8.5,3)"
    elif point_code == "temperature":
        value = "ROUND(36+6*SIN(n*PI()/24),2)"
        if site_index == 1 and device_code == "CHARGER_01":
            value = f"IF(n>=94,62.1,{value})"
        if site_index == 2 and device_code == "TRANSFORMER_01":
            value = f"IF(n BETWEEN 90 AND 92,72,{value})"
        if site_index == 6 and device_code == "TRANSFORMER_01":
            value = f"IF(n BETWEEN 82 AND 83,74,{value})"
    elif device_code == "PV_01":
        # UTC采样时间加8小时得到本地小时，夜间发电归零；仅表达模拟日变化。
        hour = "(HOUR(TIMESTAMPADD(MINUTE,-15*(95-n),TIMESTAMPADD(HOUR,8,v_seed_time))))"
        value = f"ROUND(100*GREATEST(0,SIN(({hour}-6)*PI()/12)),2)"
    elif device_code == "ESS_01":
        value = "ROUND(45*SIN(n*PI()/24),2)"  # 正放电、负充电。
    else:
        base = 180 if device_code == "TRANSFORMER_01" else 45
        value = f"ROUND({base}+12*SIN(n*PI()/24)+{site_index},2)"
    quality = "'GOOD'"
    if site_index == 3 and device_code == "PV_01" and point_code == "active_power":
        value, quality = f"IF(n=95,NULL,{value})", "IF(n=95,'BAD','GOOD')"
    return value, "NULL", quality


def build_sql():
    """返回SQL与行数清单。所有数字主键通过业务编码查找，现有数据只查询、不覆盖。"""
    statements, guards = [], []
    manifest = {table: 0 for table in TABLES}

    def add(table, values, condition, count=1):
        statements.append(insert_missing(table, values, condition))
        manifest[table] += count

    def encoded(values):
        return {key: literal(value) for key, value in values.items()}

    def guard(condition, message):
        guards.append(
            f"  IF EXISTS ({condition}) THEN\n    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='{message}';\n  END IF;\n"
        )

    for role in ROLE_PERMISSIONS:
        flag = "v_role_new_" + role.lower()
        statements.append(
            f"  SET {flag}=NOT EXISTS(SELECT 1 FROM sys_role WHERE code={literal(role)});\n"
        )
        guard(
            f"SELECT 1 FROM sys_role WHERE code={literal(role)} AND COALESCE(description,'')<>{literal(BATCH)}",
            "SIM_ROLE_CODE_CONFLICT",
        )
        add(
            "sys_role",
            encoded(
                {"code": role, "name": "模拟" + role.removeprefix("SIM_"), "description": BATCH}
            ),
            f"code={literal(role)}",
        )
    for code, name in PERMISSIONS.items():
        add("sys_permission", encoded({"code": code, "name": name}), f"code={literal(code)}")
    for role, codes in ROLE_PERMISSIONS.items():
        statements.append(f"  IF v_role_new_{role.lower()} THEN\n")
        for code in codes:
            values = {
                "role_id": lookup("sys_role", "code", role),
                "permission_id": lookup("sys_permission", "code", code),
            }
            add(
                "role_permission",
                values,
                f"role_id={values['role_id']} AND permission_id={values['permission_id']}",
            )
        statements.append("  END IF;\n")

    engine = create_sample_database()
    try:
        with Session(engine, expire_on_commit=False) as session, session.begin():
            for rid, code in [(2, "G30"), (3, "G4")]:
                session.add(
                    HighwayRoute(id=rid, route_code=code, name=f"{code}模拟路线关联（待核验）")
                )
            session.flush()
            for sid, code, name, kind, city, lon, lat, route in EXTRA_SITES:
                session.add(
                    Site(
                        id=sid,
                        code=code,
                        name=name,
                        site_type=kind,
                        scale_level="M",
                        longitude=lon,
                        latitude=lat,
                        province_code="410000",
                        city_name=city,
                        is_demo=1,
                        location_source="完全虚构测试台账与近似位置，非真实服务区或收费站入口",
                        aliases_json=["模拟", city],
                    )
                )
            session.flush()
            for sid, *_ in EXTRA_SITES:
                for offset, code, name, kind in [
                    (1, "POWER", "配电储能区（模拟）", "POWER_ROOM"),
                    (2, "PV", "光伏区（模拟）", "BUILDING"),
                    (3, "PARK", "充电区（模拟）", "PARKING"),
                ]:
                    session.add(
                        SiteArea(
                            id=sid * 100 + offset, site_id=sid, code=code, name=name, area_type=kind
                        )
                    )
            session.flush()
            original_devices = session.scalars(select(Device).where(Device.site_id == 1)).all()
            for sid, *rest in EXTRA_SITES:
                route = rest[-1]
                session.add(
                    SiteRouteLink(
                        site_id=sid,
                        route_id=2 if route == "G30" else 3,
                        link_code=route + "_DEMO",
                        direction_code="UNKNOWN",
                        direction_label="模拟方向，待核验",
                        is_primary=1,
                    )
                )
                for offset, original in enumerate(original_devices, 1):
                    values = {
                        column.name: getattr(original, column.name)
                        for column in Device.__table__.columns
                        if column.name
                        not in {"id", "site_id", "area_id", "created_at", "updated_at"}
                    }
                    session.add(
                        Device(
                            id=sid * 100 + offset,
                            site_id=sid,
                            area_id=sid * 100 + (original.area_id % 100),
                            **values,
                        )
                    )
            session.flush()
            sites = session.scalars(select(Site).order_by(Site.id)).all()
            site_codes = {site.id: site.code for site in sites}
            routes = session.scalars(select(HighwayRoute)).all()
            route_codes = {route.id: route.route_code for route in routes}
            areas = session.scalars(select(SiteArea)).all()
            area_codes = {area.id: (area.site_id, area.code) for area in areas}
            devices = session.scalars(select(Device).order_by(Device.site_id, Device.code)).all()
            for route in routes:
                add("highway_route", row_values(route), f"route_code={literal(route.route_code)}")
            for site in sites:
                guard(
                    f"SELECT 1 FROM site WHERE code={literal(site.code)} AND (is_demo<>1 OR site_type<>{literal(site.site_type)} OR scale_level<>'M')",
                    "SIM_SITE_CODE_CONFLICT",
                )
                add("site", row_values(site), f"code={literal(site.code)}")
            for area in areas:
                values = row_values(area)
                values["site_id"] = lookup("site", "code", site_codes[area.site_id])
                add(
                    "site_area",
                    values,
                    f"site_id={values['site_id']} AND code={literal(area.code)}",
                )
            for link in session.scalars(select(SiteRouteLink)):
                values = row_values(link)
                values["site_id"] = lookup("site", "code", site_codes[link.site_id])
                values["route_id"] = lookup(
                    "highway_route", "route_code", route_codes[link.route_id]
                )
                add(
                    "site_route_link",
                    values,
                    f"site_id={values['site_id']} AND link_code={literal(link.link_code)}",
                )
            for device in devices:
                values = row_values(device)
                values["site_id"] = lookup("site", "code", site_codes[device.site_id])
                _, area_code = area_codes[device.area_id]
                values["area_id"] = (
                    f"(SELECT id FROM site_area WHERE site_id={values['site_id']} AND code={literal(area_code)})"
                )
                guard(
                    f"SELECT 1 FROM device WHERE site_id={values['site_id']} AND code={literal(device.code)} AND (is_demo<>1 OR system_type<>{literal(device.system_type)})",
                    "SIM_DEVICE_CODE_CONFLICT",
                )
                add(
                    "device", values, f"site_id={values['site_id']} AND code={literal(device.code)}"
                )
    finally:
        engine.dispose()

    def sid(code):
        return lookup("site", "code", code)

    def did(site_code, device_code):
        return f"(SELECT id FROM device WHERE site_id={sid(site_code)} AND code={literal(device_code)})"

    def pid(site_code, device_code, point_code):
        return f"(SELECT id FROM device_point WHERE device_id={did(site_code, device_code)} AND code={literal(point_code)})"

    for username, password, label, role, status, count in ACCOUNTS:
        flag = "v_user_new_" + username
        guard(
            f"SELECT 1 FROM sys_user u JOIN sys_role r ON r.id=u.role_id WHERE u.username={literal(username)} AND r.code<>{literal(role)}",
            "SIM_USERNAME_CONFLICT",
        )
        statements.append(
            f"  SET {flag}=NOT EXISTS(SELECT 1 FROM sys_user WHERE username={literal(username)});\n"
        )
        add(
            "sys_user",
            {
                **encoded(
                    {
                        "username": username,
                        "password": password,
                        "display_name": label,
                        "status": status,
                    }
                ),
                "role_id": lookup("sys_role", "code", role),
            },
            f"username={literal(username)}",
        )
        statements.append(f"  IF {flag} THEN\n")
        for site in sites[:count]:
            values = {
                "user_id": lookup("sys_user", "username", username),
                "site_id": sid(site.code),
            }
            add(
                "user_site_scope",
                values,
                f"user_id={values['user_id']} AND site_id={values['site_id']}",
            )
        statements.append("  END IF;\n")

    # 一个固定审计键保存首次导入时刻，重跑不会生成新的时间批次。
    add(
        "audit_log",
        {
            "actor_id": lookup("sys_user", "username", "sim_admin"),
            "site_id": "NULL",
            "action": literal("mock:seed"),
            "target_type": literal("mock_batch"),
            "target_id": literal(BATCH),
            "request_id": literal(BATCH),
            "occurred_at": "v_seed_time",
            "after_json": literal(
                {"source": "SIMULATED", "batch": BATCH, "note": "全表固定模拟批次，不含凭据"}
            ),
        },
        f"request_id={literal(BATCH)}",
    )
    for username, *_ in ACCOUNTS:
        request_id = BATCH + "-user-" + username
        add(
            "audit_log",
            {
                "actor_id": lookup("sys_user", "username", "sim_admin"),
                "site_id": "NULL",
                "action": literal("mock:account_fixture"),
                "target_type": literal("user"),
                "target_id": f"CAST({lookup('sys_user', 'username', username)} AS CHAR)",
                "request_id": literal(request_id),
                "occurred_at": "v_seed_time",
                "after_json": literal({"username": username, "source": "SIMULATED"}),
            },
            f"request_id={literal(request_id)}",
        )

    for kind in ["TOLL", "SERVICE"]:
        uri, resource = model_manifest(kind)
        for scale in ["S", "M", "L"]:
            code = kind + "_" + scale
            values = encoded(
                {
                    "template_code": code,
                    "version_no": VERSION,
                    "name": code + "全表模拟模板",
                    "site_type": kind,
                    "scale_level": scale,
                    "status": "PUBLISHED" if scale == "M" else "DRAFT",
                    "model_uri": uri if scale == "M" else None,
                    "layout_json": {"source": "SIMULATED", "batch": BATCH},
                    "resource_manifest_json": resource
                    if scale == "M"
                    else {"isSimulated": True, "note": "仅模板草稿，资源未制作"},
                }
            )
            add("scene_template", values, f"template_code={literal(code)} AND version_no={VERSION}")

    grid = literal(list(range(96)))
    for site in sites:
        site_code = site.code
        scene = (
            f"(SELECT id FROM twin_scene WHERE site_id={sid(site_code)} AND version_no={VERSION})"
        )
        published = f"EXISTS(SELECT 1 FROM twin_scene WHERE site_id={sid(site_code)} AND status='PUBLISHED')"
        template = f"(SELECT id FROM scene_template WHERE template_code={literal(site.site_type + '_M')} AND version_no={VERSION})"
        add(
            "twin_scene",
            {
                "site_id": sid(site_code),
                "site_type": literal(site.site_type),
                "template_id": template,
                "version_no": str(VERSION),
                "status": f"IF({published},'DRAFT','PUBLISHED')",
                "is_demo": "1",
                "published_at": f"IF({published},NULL,v_seed_time)",
                "model_uri": "NULL",
            },
            f"site_id={sid(site_code)} AND version_no={VERSION}",
        )
        site_time = "TIMESTAMPADD(HOUR,-2,v_seed_time)" if site.id == 5 else "v_seed_time"
        for device in [item for item in devices if item.site_id == site.id]:
            device_id = did(site_code, device.code)
            object_key = OBJECT_KEYS[device.code]
            obj_id = f"(SELECT id FROM twin_object WHERE scene_id={scene} AND object_key={literal(object_key)})"
            _, area_code = area_codes[device.area_id]
            area_id = f"(SELECT id FROM site_area WHERE site_id={sid(site_code)} AND code={literal(area_code)})"
            add(
                "twin_object",
                {
                    "site_id": sid(site_code),
                    "scene_id": scene,
                    "object_key": literal(object_key),
                    "name": literal(device.name),
                    "device_id": device_id,
                    "area_id": area_id,
                    "is_demo": "1",
                    "transform_json": literal({"source": "SIMULATED", "useModelTransform": True}),
                    "model_uri": "NULL",
                },
                f"scene_id={scene} AND object_key={literal(object_key)}",
            )
            for code, name, unit, value_type, aggregation, low, high in point_specs(device.code):
                point_id = pid(site_code, device.code, code)
                guard(
                    f"SELECT 1 FROM device_point WHERE device_id={device_id} AND code={literal(code)} AND (unit<>{literal(unit)} OR value_type<>{literal(value_type)} OR aggregation_type<>{literal(aggregation)})",
                    "SIM_POINT_DEFINITION_CONFLICT",
                )
                add(
                    "device_point",
                    {
                        "site_id": sid(site_code),
                        "device_id": device_id,
                        **encoded(
                            {
                                "code": code,
                                "name": name + "（模拟）",
                                "unit": unit,
                                "value_type": value_type,
                                "aggregation_type": aggregation,
                                "alarm_low": low,
                                "alarm_high": high,
                                "sample_interval_ms": 900000,
                                "stale_after_ms": 1800000,
                                "enabled": 1,
                                "direction_convention": "正放电/负充电"
                                if device.code == "ESS_01" and code == "active_power"
                                else "模拟读数，非现场采集",
                            }
                        ),
                    },
                    f"device_id={device_id} AND code={literal(code)}",
                )
                numeric, text_value, quality = sample_expression(site.id, device.code, code)
                # 固定批次时间、测点ID和源序号构成幂等键；已有最新值不覆盖。
                sampled = f"TIMESTAMPADD(MINUTE,-15*(95-n),{site_time})"
                statements.append(
                    f"  INSERT INTO point_history (point_id,sampled_at,source_sequence,received_at,value_numeric,value_text,quality)\n"
                    f"    SELECT {point_id},{sampled},{SEQUENCE},TIMESTAMPADD(SECOND,1,{sampled}),{numeric},{text_value},{quality}\n"
                    f"    FROM JSON_TABLE({grid},'$[*]' COLUMNS(n INT PATH '$')) AS steps\n"
                    f"    WHERE NOT EXISTS (SELECT 1 FROM point_history WHERE point_id={point_id} AND sampled_at={sampled} AND source_sequence={SEQUENCE});\n"
                )
                manifest["point_history"] += 96
                values = {
                    "point_id": point_id,
                    "source_time": site_time,
                    "source_sequence": str(SEQUENCE),
                    "received_time": f"TIMESTAMPADD(SECOND,1,{site_time})",
                    "value_numeric": re.sub(r"\bn\b", "95", numeric),
                    "value_text": text_value,
                    "quality": re.sub(r"\bn\b", "95", quality),
                }
                add("point_latest", values, f"point_id={point_id}")
                add(
                    "twin_binding",
                    {
                        "site_id": sid(site_code),
                        "device_id": device_id,
                        "object_id": obj_id,
                        "point_id": point_id,
                        "property_code": literal(code),
                        "mapping_config_json": literal(
                            {"unit": unit, "precision": 2, "source": "SIMULATED", "batch": BATCH}
                        ),
                    },
                    f"object_id={obj_id} AND property_code={literal(code)}",
                )
        request_id = BATCH + "-site-" + str(site.id)
        add(
            "audit_log",
            {
                "actor_id": lookup("sys_user", "username", "sim_admin"),
                "site_id": sid(site_code),
                "action": literal("mock:site_fixture"),
                "target_type": literal("site"),
                "target_id": f"CAST({sid(site_code)} AS CHAR)",
                "request_id": literal(request_id),
                "occurred_at": "v_seed_time",
                "after_json": literal(
                    {"source": "SIMULATED", "batch": BATCH, "devices": 4, "points": 16}
                ),
            },
            f"request_id={literal(request_id)}",
        )

    # 独立准备六种告警样例；时刻与上方最新/历史异常相对应。
    alarms = [
        (
            1,
            "CHARGER_01",
            "temperature",
            "ACTIVE",
            "MAJOR",
            -15,
            None,
            None,
            62.1,
            "充电桩温度偏高",
            55,
        ),
        (
            2,
            "TRANSFORMER_01",
            "temperature",
            "RECOVERED",
            "MINOR",
            -75,
            -30,
            None,
            72,
            "变压器温度已恢复，待确认",
            65,
        ),
        (
            3,
            "PV_01",
            "active_power",
            "ACTIVE",
            "MINOR",
            0,
            None,
            None,
            None,
            "光伏功率测点质量BAD",
            None,
        ),
        (4, "ESS_01", "soc", "ACTIVE", "MAJOR", -15, None, -10, 12, "储能SOC偏低，已确认", 15),
        (
            5,
            "ESS_01",
            "online",
            "ACTIVE",
            "MAJOR",
            -120,
            None,
            None,
            0,
            "模拟采集断流，离线两小时",
            None,
        ),
        (
            6,
            "TRANSFORMER_01",
            "temperature",
            "CLOSED",
            "MINOR",
            -195,
            -165,
            -180,
            74,
            "温度告警已恢复并关闭",
            65,
        ),
    ]
    for index, (
        site_index,
        device_code,
        point_code,
        status,
        severity,
        raised,
        recovered,
        ack,
        value,
        message,
        threshold,
    ) in enumerate(alarms, 1):
        site_code = site_codes[site_index]
        event_key = f"{BATCH}-alarm-{index}"

        def time_expr(minutes):
            """分钟偏移转换为UTC快照时间表达式；None表示尚未确认/恢复。"""
            return "NULL" if minutes is None else f"TIMESTAMPADD(MINUTE,{minutes},v_seed_time)"

        add(
            "alarm_event",
            {
                "site_id": sid(site_code),
                "device_id": did(site_code, device_code),
                "point_id": pid(site_code, device_code, point_code),
                "event_key": literal(event_key),
                "raised_at": time_expr(raised),
                "recovered_at": time_expr(recovered),
                "acknowledged_at": time_expr(ack),
                "acknowledged_by": "NULL"
                if ack is None
                # 开封/新乡不在模拟值班员的朝歌授权范围内，由拥有六站范围的管理员确认。
                else lookup("sys_user", "username", "sim_admin"),
                **encoded(
                    {
                        "status": status,
                        "severity": severity,
                        "message": "【模拟】" + message,
                        "handling_note": "模拟确认/关闭记录" if ack is not None else None,
                        "trigger_snapshot_json": {
                            "source": "SIMULATED",
                            "batch": BATCH,
                            "value": value,
                            "threshold": threshold,
                            "pointCode": point_code,
                        },
                    }
                ),
            },
            f"site_id={sid(site_code)} AND event_key={literal(event_key)}",
        )

    # 所有冲突守卫必须在插入前执行；未知表结构明确失败而不是自动修库。
    required = ",".join(literal(table) for table in TABLES)
    flags = ["v_role_new_" + role.lower() for role in ROLE_PERMISSIONS] + [
        "v_user_new_" + item[0] for item in ACCOUNTS
    ]
    declarations = "".join(f"  DECLARE {flag} BOOLEAN DEFAULT FALSE;\n" for flag in flags)
    sql = f"""-- 全模块19表模拟数据；批次{BATCH}；用户手动导入，绝不在应用启动时执行。
-- 6站、24设备、96测点、9216历史记录；全部虚构/模拟，不能当现场数据或实测成果。
-- 只补缺失记录；不覆盖已有账号密码、角色权限、站点授权、最新值或当前发布场景。
-- 四个sim_账号为本机测试账号，密码在本文件/说明中；不要用于对外部署。
-- 重跑复用首次批次时间，不刷新旧数据的时效性。先有19表，再执行本脚本。
-- 单独连接执行；辅助过程DDL存在隐式提交，请不要与其他未提交业务事务混用。
USE `smart_power_twin`;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;
SET @c_mock_old_mode=@@SESSION.sql_mode;
SET @c_mock_old_zone=@@SESSION.time_zone;
SET SESSION sql_mode=CONCAT_WS(',',NULLIF(@c_mock_old_mode,''),'NO_BACKSLASH_ESCAPES');
SET SESSION time_zone='+00:00';
DELIMITER $$
CREATE PROCEDURE `c_spt_mock_all_20261016`()
BEGIN
  DECLARE v_seed_time DATETIME(3);
  DECLARE v_lock INT DEFAULT 0;
{declarations}  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    IF v_lock=1 THEN DO RELEASE_LOCK('{BATCH}'); END IF;
    RESIGNAL;
  END;
  IF (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()
      AND table_name IN ({required}) AND engine='InnoDB')<>19 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='REQUIRE_19_INNODB_TABLES';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE()
      AND table_name='sys_user' AND column_name='password') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='REQUIRE_CURRENT_PASSWORD_COLUMN';
  END IF;
  SELECT GET_LOCK('{BATCH}',10) INTO v_lock;
  IF COALESCE(v_lock,0)<>1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='MOCK_IMPORT_BUSY'; END IF;
  START TRANSACTION;
  SELECT COALESCE(MIN(occurred_at),UTC_TIMESTAMP(3)) INTO v_seed_time FROM audit_log WHERE request_id='{BATCH}';
{"".join(guards)}
{"".join(statements)}
  COMMIT;
  DO RELEASE_LOCK('{BATCH}');
  SET v_lock=0;
  SELECT '{BATCH}' AS batch,v_seed_time AS snapshot_time_utc,'SIMULATED' AS source;
END$$
DELIMITER ;
CALL `c_spt_mock_all_20261016`();
DROP PROCEDURE `c_spt_mock_all_20261016`;
SET SESSION sql_mode=@c_mock_old_mode;
SET SESSION time_zone=@c_mock_old_zone;
"""
    return sql, manifest


def generate_bundle(output):
    """output为导出目录，已存在同名输出时拒绝覆盖；返回SQL和清单路径。"""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    targets = [output / "C01全模块_模拟数据.sql", output / "C全模块_模拟数据清单.json"]
    if any(path.exists() for path in targets):
        raise ValueError("已有同名输出，未覆盖；需更换目录或人工核对旧版本")
    sql, counts = build_sql()
    targets[0].write_text(sql, encoding="utf-8")
    targets[1].write_text(
        json.dumps(
            {
                "batch": BATCH,
                "source": "SIMULATED",
                "expectedFixtureRows": counts,
                "notice": "为模拟集行数；已有记录保留、现有原模板/账号仍存在时总数可更多",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return targets


def main():
    """命令行入口，只输出文件路径，不打印SQL中的测试密码，更不读取实际数据库凭据。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "sql")
    args = parser.parse_args()
    for path in generate_bundle(args.output):
        print(path.name)


if __name__ == "__main__":
    main()
