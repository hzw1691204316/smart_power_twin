"""账号模块验收：真实ASGI请求、权限越界、账号状态与事务审计；不连接MySQL。"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy.orm import Session

from app.core.security import password_matches
from app.modules.system.models import Permission, Role, RolePermission, User, UserSiteScope


def login_as(client, username="fixture_viewer", password="FixtureViewer!2026"):
    """使用JSON登录并返回Bearer头，避免测试伪造已认证身份。"""
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["data"]["accessToken"]}


def new_user(**changes):
    """构造独立账号请求；调用者可覆盖角色、站点等边界参数。"""
    return dict(
        username="test_viewer",
        displayName="测试观察员",
        password="Testing!2026",
        roleId="2",
        siteIds=["1"],
        **changes,
    )


def test_login_required_and_no_public_registration(client):
    for path in ["/api/v1/auth/me", "/api/v1/sites", "/api/v1/users"]:
        assert client.get(path, headers={"Authorization": ""}).status_code == 401
        assert client.get(path, headers={"Authorization": "Bearer bad-token"}).status_code == 401
    assert client.post("/api/v1/auth/register", json={}).status_code == 404
    # 已完成模块须进入统一接口，保留无公开注册入口。
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/alarms" in paths
    assert "/api/v1/dashboard/summary" in paths


def test_plaintext_password_and_sanitized_login(client):
    assert password_matches("中文Testing!2026", "中文Testing!2026")
    assert not password_matches("wrong", "Testing!2026")
    assert not password_matches("$argon2old", "$argon2old")
    result = client.get("/api/v1/auth/me").json()["data"]
    assert result["username"] == "fixture_admin"
    assert "password" not in str(result).lower()


@pytest.mark.parametrize("kind", ["expired", "missing-claim", "wrong-signature", "bad-subject"])
def test_token_validation(client, kind):
    now = datetime.now(timezone.utc)
    payload = dict(
        sub="1",
        iat=now,
        exp=now + timedelta(minutes=1),
        iss="smart-power-twin",
        aud="smart-power-api",
        jti="test",
    )
    if kind == "expired":
        payload["exp"] = now - timedelta(seconds=1)
    if kind == "missing-claim":
        payload.pop("jti")
    if kind == "bad-subject":
        payload["sub"] = "18446744073709551616"
    secret = "wrong-secret-" * 4 if kind == "wrong-signature" else client.app.state.token_secret
    token = jwt.encode(payload, secret, algorithm="HS256")
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_failed_login_limit(client):
    for _ in range(10):
        response = client.post(
            "/api/v1/auth/login", json={"username": "absent", "password": "wrong"}
        )
        assert response.status_code == 401
        assert "absent" not in response.text
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "absent", "password": "wrong"}
        ).status_code
        == 429
    )


def test_viewer_site_scope_and_actions(client):
    viewer = login_as(client)
    assert [s["id"] for s in client.get("/api/v1/sites", headers=viewer).json()["data"]] == ["1"]
    assert client.get("/api/v1/sites/2", headers=viewer).status_code == 404
    assert client.get("/api/v1/sites/2/devices", headers=viewer).status_code == 404
    for path in ["/api/v1/users", "/api/v1/roles", "/api/v1/audit-logs"]:
        assert client.get(path, headers=viewer).status_code == 403
    assert client.post("/api/v1/users", json=new_user(), headers=viewer).status_code == 403


def test_create_scope_revoke_lock_and_audit(client):
    response = client.post("/api/v1/users", json=new_user())
    assert response.status_code == 201, response.text
    user_id = response.json()["data"]["id"]
    assert "Testing!2026" not in response.text
    assert "passwordHash" not in response.text
    with Session(client.app.state.engine) as session:
        assert session.get(User, int(user_id)).password == "Testing!2026"
    headers = login_as(client, "test_viewer", "Testing!2026")
    assert client.put(f"/api/v1/users/{user_id}/sites", json={"siteIds": ["2"]}).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).json()["data"]["siteIds"] == ["2"]
    assert client.get("/api/v1/sites/1", headers=headers).status_code == 404
    assert client.get("/api/v1/sites/2", headers=headers).status_code == 200
    client.put(f"/api/v1/users/{user_id}/sites", json={"siteIds": []})
    assert client.get("/api/v1/sites", headers=headers).json()["data"] == []
    assert (
        client.put(f"/api/v1/users/{user_id}/status", json={"status": "LOCKED"}).status_code == 200
    )
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "test_viewer", "password": "Testing!2026"}
        ).status_code
        == 401
    )
    assert client.put("/api/v1/users/1/status", json={"status": "LOCKED"}).status_code == 409
    audit = client.get("/api/v1/audit-logs").json()["data"]
    assert {r["action"] for r in audit} >= {"user:create", "user:scope", "user:status"}
    assert "Testing!2026" not in str(audit)
    assert "accessToken" not in str(audit)


@pytest.mark.parametrize(
    "change,status",
    [
        ({"roleId": "999"}, 404),
        ({"siteIds": ["999"]}, 403),
        ({"username": "fixture_admin"}, 409),
        ({"password": "short"}, 422),
        ({"unknown": True}, 422),
        ({"siteIds": ["0"]}, 422),
    ],
)
def test_creation_boundaries(client, change, status):
    body = new_user()
    body.update(change)
    response = client.post("/api/v1/users", json=body)
    assert response.status_code == status, response.text
    assert body["password"] not in response.text


def test_mysql_read_only_guard_without_mysql_connection(client):
    # 仅替换请求配置，实际引擎仍是内存SQLite，绝不连接或修改用户数据库。
    client.app.state.settings.data_source = "mysql"
    client.app.state.settings.mysql_allow_writes = False
    assert client.post("/api/v1/users", json=new_user()).status_code == 409


def test_cors_bearer_header(client):
    response = client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_delegated_manager_cannot_escalate_or_cross_scope(client):
    """具有开户动作但不具有全部权限的账号，不能借角色选择或修改范围提权。"""
    with Session(client.app.state.engine) as session, session.begin():
        session.add(Role(id=3, code="LIMITED", name="受限管理员"))
        session.flush()
        codes = {
            "site:read",
            "device:read",
            "system:read",
            "user:manage",
            "monitor:read",
            "twin:read",
            "alarm:read",
            "dashboard:read",
        }
        permissions = session.query(Permission).filter(Permission.code.in_(codes)).all()
        session.add_all(RolePermission(role_id=3, permission_id=p.id) for p in permissions)
        session.add(
            User(
                id=3,
                username="limited_manager",
                display_name="受限管理员",
                role_id=3,
                password="Limited!2026",
                status="ACTIVE",
            )
        )
        session.flush()
        session.add(UserSiteScope(user_id=3, site_id=1))
    headers = login_as(client, "limited_manager", "Limited!2026")
    body = new_user()
    body["roleId"] = "1"  # ADMIN还含audit:read，本人没有。
    assert client.post("/api/v1/users", json=body, headers=headers).status_code == 403
    body["roleId"] = "2"
    body["siteIds"] = ["2"]
    assert client.post("/api/v1/users", json=body, headers=headers).status_code == 403
    body["siteIds"] = ["1"]
    assert client.post("/api/v1/users", json=body, headers=headers).status_code == 201
    assert (
        client.put("/api/v1/users/1/sites", json={"siteIds": ["1"]}, headers=headers).status_code
        == 403
    )
    assert (
        client.put("/api/v1/users/1/status", json={"status": "LOCKED"}, headers=headers).status_code
        == 403
    )


def test_auth_cache_and_header_contract(client):
    response = client.get("/api/v1/auth/me")
    assert response.headers["Cache-Control"] == "no-store"
    response = client.get("/api/v1/auth/me", headers={"Authorization": ""})
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_parallel_authenticated_requests_do_not_exhaust_threadpool(client):
    """超过默认线程池容量的并发请求仍可完成；验证演示库排队不持有阻塞线程锁。"""
    import asyncio

    import httpx

    async def check():
        transport = httpx.ASGITransport(app=client.app, client=("127.0.0.1", 51000))
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={
                "Authorization": client.headers["Authorization"],
            },
        ) as requests:
            responses = await asyncio.wait_for(
                asyncio.gather(*[requests.get("/api/v1/auth/me") for _ in range(48)]), timeout=15
            )
            assert all(response.status_code == 200 for response in responses)

    asyncio.run(check())
