"""异常响应模块：区分业务不存在、参数错误和数据库不可用，不向客户端泄露SQL或密码。"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

logger = logging.getLogger(__name__)


class BusinessError(Exception):
    """可展示给调用者的业务异常，区别于数据库等内部异常。"""

    def __init__(self, code: str, message: str, status_code: int = 404):
        """参数：code为稳定错误编码；message为用户可读说明；status_code为HTTP状态，默认404。"""
        self.code, self.message, self.status_code = code, message, status_code


def register_exception_handlers(app: FastAPI):
    """为app注册统一异常处理。参数app为FastAPI实例；注册本身不执行数据库查询。"""

    @app.exception_handler(BusinessError)
    async def business_error(_request: Request, exc: BusinessError):
        """把exc业务异常转换为error.code/message及对应HTTP状态；_request为框架注入的请求。"""
        return JSONResponse(
            status_code=exc.status_code,
            headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, exc: RequestValidationError):
        # 不回显原始输入，避免未来敏感请求泄露字段。
        """把参数校验异常exc转为422，保留出错位置和说明，不回显原始输入。"""
        details = [{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_ARGUMENT",
                    "message": "请求参数不符合要求",
                    "details": details,
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request: Request, exc: SQLAlchemyError):
        # 不输出连接URL、参数及原始错误，也不回退到演示数据。
        """把SQLAlchemy异常exc转为503并只记录异常类型；不给出SQL参数，不回退到demo。"""
        logger.error("Database request failed (%s)", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "数据库查询失败，请检查连接、权限和表结构",
                }
            },
        )

    @app.exception_handler(IntegrityError)
    async def conflict(_request: Request, exc: IntegrityError):
        """flush阶段的唯一键／归属约束冲突统一409；请求会话关闭时回滚，不返回内部SQL。"""
        return JSONResponse(
            status_code=409,
            content={
                "error": {"code": "CONFLICT", "message": "记录重复、并发冲突或归属约束不满足"}
            },
        )
