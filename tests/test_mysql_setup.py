"""MySQL接入的离线检查：配置脱敏、结构拒绝、脚本与生成器一致性，不访问用户数据库。"""

import re
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

from app.db import validation
from app.db.base import Base
from app.modules import register_models
from scripts.generate_auth_mysql_seed import (
    SCHEMA_FILE,
    SEED_FILE,
    build_seed_sql,
    generate_bundle,
)
from scripts.run_backend_mysql import load_mysql_settings

ROOT = Path(__file__).resolve().parents[1]


def test_mysql_local_config_and_secret_redaction(tmp_path):
    config = tmp_path / ".env.mysql.local"
    with pytest.raises(ValueError, match="缺少"):
        load_mysql_settings(config)
    config.write_text("SPT_MYSQL_PASSWORD=\n", encoding="utf-8")
    with pytest.raises(ValueError, match="配置不完整") as error:
        load_mysql_settings(config)
    assert "input_value" not in str(error.value)
    config.write_text(
        "SPT_MYSQL_PASSWORD=local-test-secret\nSPT_TOKEN_SECRET=short\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="至少32"):
        load_mysql_settings(config)
    config.write_text(
        "SPT_DATA_SOURCE=demo\nSPT_MYSQL_PASSWORD=local-test-secret\nSPT_TOKEN_SECRET=" + "x" * 40,
        encoding="utf-8",
    )
    settings = load_mysql_settings(config)
    assert settings.data_source == "mysql"  # 启动器不能意外退回demo。
    assert "local-test-secret" not in repr(settings)


def test_normal_startup_rejects_demo_and_uses_mysql_config():
    from pydantic import ValidationError

    from app.core.config import PROJECT_ROOT, Settings

    assert Settings.model_config["env_file"] == PROJECT_ROOT / ".env.mysql.local"
    with pytest.raises(ValidationError):
        Settings(data_source="demo", mysql_password="offline-test", _env_file=None)
    with pytest.raises(ValidationError):
        Settings(data_source="test", mysql_password="offline-test", _env_file=None)


@pytest.mark.parametrize("problem", ["table", "column", "primary", "engine", "connection"])
def test_mysql_schema_rejects_incompatible_database(monkeypatch, problem):
    register_models()

    class Inspector:
        """模拟MySQL元数据读取，不用SQLite冒充MySQL方言。"""

        def get_table_names(self):
            if problem == "connection":
                raise OperationalError("SQL CONTAINING_SECRET", {}, Exception("PRIVATE_PASSWORD"))
            return validation.ACTIVE_TABLES[1:] if problem == "table" else validation.ACTIVE_TABLES

        def get_columns(self, name):
            return (
                []
                if problem == "column"
                else [{"name": column.name} for column in Base.metadata.tables[name].columns]
            )

        def get_pk_constraint(self, name):
            return {
                "constrained_columns": []
                if problem == "primary"
                else [column.name for column in Base.metadata.tables[name].primary_key]
            }

        def get_table_options(self, name):
            return {"mysql_engine": "MyISAM" if problem == "engine" else "InnoDB"}

    monkeypatch.setattr(validation, "inspect", lambda _engine: Inspector())
    with pytest.raises(RuntimeError) as error:
        validation.validate_mysql_schema(object())
    assert "PRIVATE_PASSWORD" not in str(error.value)
    assert "SQL CONTAINING_SECRET" not in str(error.value)


def test_delivered_seed_matches_generator_without_revealing_passwords():
    delivered = (ROOT / "sql" / SEED_FILE).read_text(encoding="utf-8")
    generated = build_seed_sql("OfflineAdmin!2026", "OfflineViewer!2026")

    def normalize(script):
        return re.sub(r"(SELECT 'mysql_(?:admin|viewer)', )'[^']*'", r"\1'<PASSWORD>'", script)

    assert normalize(delivered) == normalize(generated)
    assert "OfflineAdmin!2026" in generated
    assert "OfflineViewer!2026" in generated
    assert "$argon2id$" not in generated
    assert "`password_hash`" not in generated
    statements = "\n".join(
        line for line in generated.splitlines() if not line.lstrip().startswith("--")
    )
    assert "REPLACE INTO" not in statements and "INSERT IGNORE" not in statements


def test_bundle_preserves_existing_output_and_password(tmp_path):
    schema = tmp_path / "schema.sql"
    schema.write_text(
        (ROOT / "sql" / SCHEMA_FILE)
        .read_text(encoding="utf-8")
        .replace("CREATE TABLE IF NOT EXISTS ", "CREATE TABLE "),
        encoding="utf-8",
    )
    output = tmp_path / "bundle"
    files = generate_bundle(output, schema)
    original = {path.name: path.read_bytes() for path in files}
    with pytest.raises(ValueError, match="已有"):
        generate_bundle(output, schema)
    assert {path.name: path.read_bytes() for path in files} == original
