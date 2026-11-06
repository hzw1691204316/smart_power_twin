"""跨模块公共规则：主键、安全范围、只读模式、事务提交和响应来源，不替代各模块业务。"""

from typing import Annotated

from fastapi import Path
from pydantic import Field
from sqlalchemy.exc import IntegrityError

from app.common.pagination import Page, PageMeta, Result, SourceMeta
from app.core.exceptions import BusinessError
from app.modules.assets.models import Device, Site
from app.modules.assets.service import numeric_id

IdValue = Annotated[
    str,
    Field(pattern=r"^[1-9][0-9]{0,19}$", description="数据库主键的十进制字符串，从查询结果复制"),
]
PathId = Annotated[
    str, Path(pattern=r"^[1-9][0-9]{0,19}$", description="数据库主键，十进制字符串；从列表结果复制")
]


def find(session, model, value):
    """按字符串value查model主键；兼容SQLite演示范围，无记录返回None，大ID不产生驱动溢出。"""
    key = numeric_id(value)
    if session.get_bind().dialect.name == "sqlite" and key > 9223372036854775807:
        return None
    return session.get(model, key)


def require_site(session, principal, site_id):
    """返回获授权站点；不存在与未授权统一404，避免泄露其他站点详情。"""
    site = find(session, Site, site_id)
    if site is None or site.id not in principal.site_ids:
        raise BusinessError("SITE_NOT_FOUND", "站点不存在或未授权", 404)
    return site


def require_device(session, principal, device_id):
    """返回获授权站点内设备；device_id为字符串ID，未授权／不存在统一404。"""
    device = find(session, Device, device_id)
    if device is None or device.site_id not in principal.site_ids:
        raise BusinessError("DEVICE_NOT_FOUND", "设备不存在或未授权", 404)
    return device


def require_writable(settings):
    """MySQL须显式启用写开关，默认409；自动化测试使用独立注入的会话。"""
    if settings.data_source == "mysql" and not settings.mysql_allow_writes:
        raise BusinessError("MYSQL_READ_ONLY", "当前MySQL只读模式，业务写入尚未启用", 409)


def commit(session):
    """提交一个完整业务事务；唯一键／归属约束冲突时回滚并返回409，不暴露原始SQL。"""
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise BusinessError("CONFLICT", "记录已存在、并发冲突或归属约束不满足", 409) from None


def result(data, settings):
    """给data附数据来源说明；mysql也可能含演示台账，样本来源由设备isDemo隔离。"""
    return Result(
        data=data,
        meta=SourceMeta(
            data_source=settings.data_source,
            notice="自动化测试样例，不连接用户数据库。"
            if settings.data_source == "test"
            else "来自已配置MySQL；请结合isDemo、采样质量和新鲜度判断，不默认视为现场数据。",
        ),
    )


def paged(data, total, page, page_size, settings):
    """统一分页响应，参数为当前页、筛选总数、页码、容量和来源配置。"""
    return Page(
        data=data,
        meta=PageMeta(
            **result(None, settings).meta.model_dump(),
            total=total,
            page=page,
            page_size=page_size,
            has_next=page * page_size < total,
        ),
    )
