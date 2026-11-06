"""测试公共准备：每个用例使用全新的内存demo库，不读取用户.env或触碰MySQL。"""

import pytest
from fastapi.testclient import TestClient

from tests.support.database import create_test_app


@pytest.fixture
def client():
    # 显式模式、不读取用户.env、不连接真实MySQL；每个用例使用全新内存库。
    """pytest客户端fixture，yield提供本机IP的TestClient；用例结束自动关闭应用和数据库引擎。"""
    application = create_test_app()
    with TestClient(application, client=("127.0.0.1", 50000)) as test_client:
        response = test_client.post(
            "/api/v1/auth/login",
            json={"username": "fixture_admin", "password": "FixtureAdmin!2026"},
        )
        assert response.status_code == 200, response.text
        test_client.headers["Authorization"] = "Bearer " + response.json()["data"]["accessToken"]
        yield test_client
