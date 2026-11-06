"""配置模块：统一从SPT_环境变量或.env.mysql.local读取MySQL配置，不读取前端Token。

正式启动只支持MySQL；配置优先使用环境变量，连接密码使用SecretStr避免打印泄露。"""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置集合。

    data_source固定mysql；mysql_host/port为连接地址，
    mysql_database为库名，mysql_user/password为数据库账户，写入还须mysql_allow_writes开关。"""

    model_config = SettingsConfigDict(
        env_prefix="SPT_",
        env_file=PROJECT_ROOT / ".env.mysql.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    # 不再接受demo配置；缺少连接信息时明确失败，不生成内存账号。
    data_source: Literal["mysql"] = "mysql"
    # MySQL主机和TCP端口；与后端HTTP端口8000不是同一用途。
    mysql_host: str = "127.0.0.1"
    mysql_port: int = Field(default=3306, ge=1, le=65535)
    # 已创建的数据库名称；应用不会自动创建这个数据库。
    mysql_database: str = "smart_power_twin"
    # 台账查询可用只读账户；账号维护须对账号/授权/审计表具备相应最小写权限。
    mysql_user: str = "smart_power_reader"
    # 数据库连接密码只填写本地配置，不提交或放入前端；不同于sys_user中的网页密码。
    mysql_password: SecretStr = SecretStr("")
    # 默认禁止在已有MySQL写入；必须由用户核对表与权限后显式启用。
    mysql_allow_writes: bool = False
    # 应用启动时要求至少32字符的固定本地密钥；JWT签名仍保留，不使用网页登录密码代替。
    token_secret: SecretStr = SecretStr("")
    token_minutes: int = Field(default=30, ge=1, le=240, description="访问令牌有效分钟")

    @model_validator(mode="after")
    def validate_mysql(self):
        """校验MySQL模式必须提供密码。返回当前配置；缺失时抛出配置校验错误。

        该校验不连接数据库；模式错误不允许静默退回演示库。"""
        if self.data_source == "mysql" and not self.mysql_password.get_secret_value():
            raise ValueError("MySQL模式需要在本地.env中填写SPT_MYSQL_PASSWORD")
        return self
