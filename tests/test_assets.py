"""台账模块回归测试：搜索、分页、归属、空值、数字边界、只读、错误脱敏及CORS。

client参数由conftest创建独立demo应用；monkeypatch只在当前用例临时替换对象，
parametrize的params/total/origin等由用例数据注入。MySQL用例只检查引擎构造或SQL编译，不连接真实库。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import create_database
from app.modules.assets.models import HighwayRoute, Site, SiteRouteLink
from app.modules.assets.repository import AssetRepository
from app.modules.system.models import UserSiteScope
from tests.support.database import create_test_app


def test_legacy_and_health(client):
    assert client.get("/").json() == {"message": "Hello World"}
    assert client.get("/hello/User").json() == {"message": "Hello User"}
    health = client.get("/api/v1/health").json()
    assert health["dataSource"] == "test"
    assert health["database"] == "isolated-test"
    assert health["authenticationImplemented"] is True


def test_fixture_sites_and_metadata(client):
    result = client.get("/api/v1/sites").json()
    assert result["meta"]["total"] == 2
    assert result["meta"]["dataSource"] == "test"
    assert "测试" in result["meta"]["notice"]
    assert {s["name"] for s in result["data"]} == {"朝歌服务区", "朝歌收费站"}
    assert all(s["isDemo"] and isinstance(s["id"], str) for s in result["data"])
    assert all(s["assetStatus"] == "ACTIVE" and "powerKw" not in s for s in result["data"])
    assert client.get("/api/v1/sites/1").json()["data"]["routes"][0]["directionCode"] == "UNKNOWN"


@pytest.mark.parametrize(
    "params,total",
    [
        (
            {
                "q": "鹤壁 朝歌 s26",
                "siteType": "SERVICE",
                "scale": "M",
                "provinceCode": "41",
                "cityName": "鹤壁",
                "highway": "s26",
            },
            1,
        ),
        ({"siteType": "TOLL", "provinceCode": "410000", "cityName": "鹤壁市"}, 1),
        ({"provinceCode": "370000"}, 0),
        ({"cityName": "郑州"}, 0),
        ({"status": "RETIRED"}, 0),
        ({"q": "朝歌 不存在"}, 0),
        ({"q": "%"}, 0),
        ({"q": "_"}, 2),  # 业务code中的真实下划线，不是任意单字符。
        ({"q": "' OR 1=1 --"}, 0),
    ],
)
def test_combined_filters_and_literal_search(client, params, total):
    response = client.get("/api/v1/sites", params=params)
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == total


def test_exact_highway_and_no_duplicate_site_from_direction_links(client):
    with Session(client.app.state.engine) as session, session.begin():
        session.add(HighwayRoute(id=2, route_code="G40", name="G40测试路线"))
        session.flush()
        session.add_all(
            [
                SiteRouteLink(site_id=1, route_id=2, link_code="G40_TEST"),
                SiteRouteLink(site_id=1, route_id=1, link_code="S26_SECOND", direction_code="DOWN"),
            ]
        )
    assert client.get("/api/v1/sites?highway=G4").json()["meta"]["total"] == 0
    assert client.get("/api/v1/sites?highway=G40").json()["meta"]["total"] == 1
    assert client.get("/api/v1/sites?highway=S26").json()["meta"]["total"] == 2


def test_stable_pagination_and_empty_page(client):
    first = client.get("/api/v1/sites?pageSize=1&page=1").json()
    second = client.get("/api/v1/sites?pageSize=1&page=2").json()
    assert first["meta"]["hasNext"] is True
    assert second["meta"]["hasNext"] is False
    assert first["data"][0]["id"] != second["data"][0]["id"]
    empty = client.get("/api/v1/sites?page=3&pageSize=1").json()
    assert empty["data"] == [] and empty["meta"]["total"] == 2


def test_devices_filters_ratings_and_ownership(client):
    all_devices = client.get("/api/v1/sites/1/devices").json()
    assert all_devices["meta"]["total"] == 4
    assert all(d["siteId"] == "1" and d["isDemo"] for d in all_devices["data"])
    storage = client.get("/api/v1/sites/1/devices?systemType=ESS").json()["data"][0]
    assert storage["ratedEnergyKwh"] == 215
    assert "powerKw" not in storage and "runtimeStatus" not in storage
    assert client.get("/api/v1/sites/1/devices?status=MAINTENANCE").json()["data"] == []
    assert client.get("/api/v1/sites/1/devices?q=直流").json()["meta"]["total"] == 1
    assert client.get("/api/v1/sites/1/devices/101").status_code == 200
    denied = client.get("/api/v1/sites/2/devices/101")
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "DEVICE_NOT_FOUND"


def test_areas_and_highways(client):
    areas = client.get("/api/v1/sites/1/areas").json()["data"]
    assert len(areas) == 3 and all(a["siteId"] == "1" for a in areas)
    routes = client.get("/api/v1/highways?q=s26").json()
    assert routes["meta"]["total"] == 1
    assert routes["data"][0]["geometryUri"] is None


@pytest.mark.parametrize("path", ["/sites/999", "/sites/999/devices", "/sites/999/areas"])
def test_missing_site_is_not_empty_success(client, path):
    response = client.get("/api/v1" + path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SITE_NOT_FOUND"


@pytest.mark.parametrize(
    "path",
    [
        "/sites?page=0",
        "/sites?pageSize=101",
        "/sites?siteType=WRONG",
        "/sites?provinceCode=410600",
        "/sites?highway=G4;G40",
        "/sites/0",
        "/sites/henan-service-01",
        "/sites/18446744073709551616",
        "/sites/-1",
        "/sites/1/devices?systemType=INVALID",
    ],
)
def test_invalid_inputs_are_rejected(client, path):
    response = client.get("/api/v1" + path)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_ARGUMENT"


def test_large_ids_and_nullable_coordinates(client):
    large_id = 9007199254740993
    with Session(client.app.state.engine) as session, session.begin():
        session.add(
            Site(
                id=large_id,
                code="BIG_ID",
                name="大整数测试",
                site_type="TOLL",
                scale_level="S",
                province_code="41",
                is_demo=1,
            )
        )
        session.flush()
        session.add(UserSiteScope(user_id=1, site_id=large_id))
    site = client.get(f"/api/v1/sites/{large_id}").json()["data"]
    assert site["id"] == str(large_id)
    assert site["provinceCode"] == "410000"
    assert site["longitude"] is None and site["latitude"] is None and site["routes"] == []


def test_existing_site_without_devices_returns_empty(client):
    with Session(client.app.state.engine) as session, session.begin():
        session.add(
            Site(
                id=3,
                code="EMPTY",
                name="无设备演示站",
                site_type="TOLL",
                scale_level="S",
                province_code="41",
                is_demo=1,
            )
        )
        session.flush()
        session.add(UserSiteScope(user_id=1, site_id=3))
    result = client.get("/api/v1/sites/3/devices").json()
    assert result["data"] == [] and result["meta"]["total"] == 0


def test_get_routes_issue_no_writes(client):
    statements = []

    def record(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(client.app.state.engine, "before_cursor_execute", record)
    try:
        for path in [
            "/sites",
            "/sites/1",
            "/sites/1/devices",
            "/sites/1/devices/101",
            "/sites/1/areas",
            "/highways",
        ]:
            assert client.get("/api/v1" + path).status_code == 200
        assert statements and all(word == "SELECT" for word in statements)
        for method in ["PUT", "DELETE"]:
            assert client.request(method, "/api/v1/sites").status_code == 405
    finally:
        event.remove(client.app.state.engine, "before_cursor_execute", record)


def test_database_failure_is_explicit_and_sanitized(client, monkeypatch):
    def fail(_self, *_args, **_kwargs):
        raise OperationalError(
            "SELECT password FROM secret", {"password": "DO_NOT_LEAK"}, Exception("DO_NOT_LEAK")
        )

    monkeypatch.setattr(AssetRepository, "sites", fail)
    response = client.get("/api/v1/sites")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "DO_NOT_LEAK" not in response.text and "data" not in response.json()


def test_nonlocal_access_blocked():
    with TestClient(create_test_app(), client=("192.0.2.1", 50000)) as remote:
        assert remote.get("/api/v1/sites").status_code == 403


def test_openapi_and_readonly_contract(client):
    schema = client.get("/openapi.json").json()
    assert client.get("/docs").status_code == 200
    assert "/api/v1/sites/{site_id}/devices/{device_id}" in schema["paths"]
    assert schema["components"]["schemas"]["SiteOut"]["properties"]["id"]["type"] == "string"
    assert schema["components"]["schemas"]["DeviceOut"]["properties"]["assetStatus"]


def test_mysql_mode_creates_engine_without_touching_schema(monkeypatch):
    from app.db.base import Base

    def forbid_ddl(*_args, **_kwargs):
        raise AssertionError("MySQL must not create or replace tables")

    monkeypatch.setattr(Base.metadata, "create_all", forbid_ddl)
    settings = Settings(data_source="mysql", mysql_password="a@b:/test-only", _env_file=None)
    engine = create_database(settings)
    try:
        assert engine.url.drivername == "mysql+pymysql"
        assert engine.url.database == "smart_power_twin"
        assert engine.url.password == "a@b:/test-only"
        assert "a@b:/test-only" not in str(engine.url)
        assert "a@b:/test-only" not in repr(settings)
    finally:
        engine.dispose()


def test_mysql_missing_password_fails_instead_of_fallback():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(data_source="mysql", mysql_password="", _env_file=None)


def test_mysql_uint64_boundary_is_safe_in_demo(client):
    for path in ["/sites/18446744073709551615", "/sites/1/devices/18446744073709551615"]:
        assert client.get("/api/v1" + path).status_code == 404


def test_underscore_is_literal_and_alias_search(client):
    with Session(client.app.state.engine) as session, session.begin():
        session.add(
            Site(
                id=3,
                code="PLAIN",
                name="无下划线站点",
                site_type="TOLL",
                scale_level="S",
                province_code="41",
                is_demo=1,
            )
        )
        site = session.get(Site, 1)
        site.aliases_json = ["仅别名命中测试"]
        session.flush()
        session.add(UserSiteScope(user_id=1, site_id=3))
    assert client.get("/api/v1/sites", params={"q": "_"}).json()["meta"]["total"] == 2
    alias = client.get("/api/v1/sites", params={"q": "仅别名命中测试"}).json()
    assert alias["meta"]["total"] == 1 and alias["data"][0]["id"] == "1"


def test_mysql_search_compiles_with_parameters_without_connection(monkeypatch):
    from sqlalchemy.dialects import mysql

    from app.modules.assets import repository

    engine = create_database(
        Settings(data_source="mysql", mysql_password="test-only", _env_file=None)
    )
    statements = []

    def capture(_session, statement, _page, _page_size):
        statements.append(statement.compile(dialect=mysql.dialect()))
        return [], 0

    monkeypatch.setattr(repository, "page_rows", capture)
    try:
        with Session(engine) as session:
            AssetRepository(session).sites(
                1, 20, "朝歌 %_", "SERVICE", "M", "410000", "鹤壁市", "S26", None
            )
        sql = str(statements[0])
        assert "json_search" in sql and "朝歌" not in sql
        assert "%/%/_%" in statements[0].params.values()
    finally:
        engine.dispose()


@pytest.mark.parametrize("origin", ["http://127.0.0.1:5173", "http://localhost:5173"])
def test_frontend_cors_get_and_preflight(client, origin):
    response = client.get("/api/v1/sites", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    preflight = client.options(
        "/api/v1/sites",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin
    assert "GET" in preflight.headers["access-control-allow-methods"]


def test_unconfigured_origin_and_write_method_not_allowed(client):
    untrusted = client.get("/api/v1/sites", headers={"Origin": "http://example.invalid"})
    assert "access-control-allow-origin" not in untrusted.headers
    write = client.options(
        "/api/v1/sites",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert write.status_code == 200  # 新模块已有POST业务；具体资产写入仍返回405。


def test_database_error_preserves_frontend_cors_headers(client, monkeypatch):
    def fail(_self, *_args, **_kwargs):
        raise OperationalError("SELECT 1", {}, Exception("test"))

    monkeypatch.setattr(AssetRepository, "sites", fail)
    response = client.get("/api/v1/sites", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 503
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
