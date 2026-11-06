"""使用MySQL配置启动后端：与main.py使用相同配置，不自动执行SQL或创建内存账号。

使用python -m scripts.run_backend_mysql；--config指定本地文件，--check-only只做只读预检。
"""

import argparse
from pathlib import Path

import uvicorn
from pydantic import ValidationError

from app.application import create_app
from app.core.config import PROJECT_ROOT, Settings
from app.db.session import create_database
from app.db.validation import validate_mysql_schema


def load_mysql_settings(config: Path) -> Settings:
    """读取config中的本地口令和签名密钥；强制MySQL，拒绝空密码/示例密钥，错误不回显值。"""
    if not config.is_file():
        raise ValueError("缺少本地MySQL配置文件，请按接入文档准备.env.mysql.local")
    try:
        settings = Settings(data_source="mysql", _env_file=config)
    except ValidationError:
        raise ValueError("MySQL配置不完整或格式错误，请在本地填写密码并核对端口等字段") from None
    secret = settings.token_secret.get_secret_value()
    if len(secret) < 32:
        raise ValueError("请在本地配置至少32字符的SPT_TOKEN_SECRET")
    return settings


def main():
    """命令行入口；不打印密码/URL。默认8000，check-only不监听HTTP端口也不写入数据库。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / ".env.mysql.local")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    try:
        if not 1 <= args.port <= 65535:
            raise ValueError("后端端口必须在1—65535之间")
        settings = load_mysql_settings(args.config.resolve())
        if args.check_only:
            engine = create_database(settings)
            try:
                validate_mysql_schema(engine)
            finally:
                engine.dispose()
            print("MySQL只读预检通过：11张活动表可用；未导入或修改任何业务数据。")
        else:
            uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port, proxy_headers=False)
    except (ValueError, RuntimeError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
