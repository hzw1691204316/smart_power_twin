"""数据库引擎模块：只连接已有MySQL，默认只读、账号写入须显式开启。

创建引擎不等于MySQL连接已经成功；实际连通由请求或健康检查验证。"""

from sqlalchemy import URL, create_engine, event
from sqlalchemy.engine import Engine

from app.core.config import Settings
from app.modules import register_models


def create_database(settings: Settings) -> Engine:
    """按settings创建SQLAlchemy Engine。

    参数：settings含模式、主机、端口、库名、数据库凭据及写入开关。
    返回：延迟连接的MySQL引擎；不包含内存版分支。
    注意：MySQL分支不建表、不迁移、不导入样例；hide_parameters禁止错误日志回显SQL参数。"""
    register_models()
    if settings.data_source != "mysql":
        raise ValueError("运行后端只支持MySQL，不能启动内存版")

    url = URL.create(
        "mysql+pymysql",
        username=settings.mysql_user,
        password=settings.mysql_password.get_secret_value(),
        host=settings.mysql_host,
        port=settings.mysql_port,
        database=settings.mysql_database,
        query={"charset": "utf8mb4"},
    )
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        hide_parameters=True,
        connect_args={"connect_timeout": 5, "read_timeout": 10, "write_timeout": 10},
    )

    @event.listens_for(engine, "connect")
    def configure_connection(connection, _record):
        """为新MySQL连接connection设置UTC和显式事务读写模式；_record是连接池事件记录。

        这里只设置会话属性，不创建账户或改变已有表。"""
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION time_zone = '+00:00'")
            cursor.execute(
                "SET SESSION TRANSACTION READ WRITE"
                if settings.mysql_allow_writes
                else "SET SESSION TRANSACTION READ ONLY"
            )

    return engine
