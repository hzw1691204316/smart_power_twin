"""告警查询/确认/关闭接口；动作权限与站点范围分别校验，不公开自动恢复入口。"""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.api.dependencies import get_session, require_permission
from app.common.access import PathId, paged, require_device, require_site, result
from app.common.pagination import Page, Result
from app.common.time import db_time
from app.core.exceptions import BusinessError
from app.modules.alarms import repository, service
from app.modules.alarms.schemas import ActionIn, AlarmOut, AlarmSeverity, AlarmStatus
from app.modules.monitoring.service import require_point

router = APIRouter(tags=["告警与处置"])


@router.get("/alarms", response_model=Page[AlarmOut], summary="范围内告警分页与筛选")
def alarms(
    request: Request,
    page: int = Query(1, ge=1, le=10000, description="页码，从1开始"),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100, description="每页容量"),
    site_id: str | None = Query(
        None, alias="siteId", pattern=r"^[1-9][0-9]{0,19}$", description="可选站点ID"
    ),
    device_id: str | None = Query(
        None, alias="deviceId", pattern=r"^[1-9][0-9]{0,19}$", description="可选设备ID"
    ),
    point_id: str | None = Query(
        None, alias="pointId", pattern=r"^[1-9][0-9]{0,19}$", description="可选测点ID"
    ),
    status: AlarmStatus | None = Query(None, description="生命周期，独立于确认"),
    severity: AlarmSeverity | None = Query(None, description="事件级别"),
    acknowledged: bool | None = Query(None, description="是否已人工确认；不等同恢复"),
    start_time: AwareDatetime | None = Query(
        None, alias="startTime", description="发生时间起点，包含，须带时区"
    ),
    end_time: AwareDatetime | None = Query(
        None, alias="endTime", description="发生时间终点，不包含，须带时区"
    ),
    session: Session = Depends(get_session),
    principal=Depends(require_permission("alarm:read")),
):
    """可组合过滤；显式传未授权身份返回404，授权内无匹配返回空页；时间半开区间。"""
    site = require_site(session, principal, site_id) if site_id else None
    device = require_device(session, principal, device_id) if device_id else None
    point = require_point(session, principal, point_id) if point_id else None
    start, end = (
        db_time(start_time) if start_time else None,
        db_time(end_time) if end_time else None,
    )
    if start is not None and end is not None and start >= end:
        raise BusinessError("INVALID_TIME_RANGE", "告警时间范围必须递增", 422)
    rows, total = repository.list_events(
        session,
        principal.site_ids,
        page,
        page_size,
        site_id=site.id if site else None,
        device_id=device.id if device else None,
        point_id=point.id if point else None,
        status=status,
        severity=severity,
        acknowledged=acknowledged,
        start=start,
        end=end,
    )
    return paged(
        [service.alarm_out(session, e) for e in rows],
        total,
        page,
        page_size,
        request.app.state.settings,
    )


@router.get("/alarms/{event_id}", response_model=Result[AlarmOut], summary="告警详情与发生快照")
def detail(
    event_id: PathId,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("alarm:read")),
):
    """event_id为事件主键；返回关联设备/测点身份以定位模型与查询趋势。"""
    return result(
        service.alarm_out(session, service.require_event(session, principal, event_id)),
        request.app.state.settings,
    )


@router.post(
    "/alarms/{event_id}/acknowledge", response_model=Result[AlarmOut], summary="首次人工确认"
)
def acknowledge(
    event_id: PathId,
    body: ActionIn,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("alarm:ack")),
):
    """记录首次确认人与时间；重复不覆盖说明；不会将ACTIVE改为RECOVERED。"""
    return service.act(session, request.app.state.settings, principal, event_id, body, "ack")


@router.post(
    "/alarms/{event_id}/close", response_model=Result[AlarmOut], summary="关闭已恢复且已确认的事件"
)
def close(
    event_id: PathId,
    body: ActionIn,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("alarm:close")),
):
    """活动或未确认时409；关闭重试幂等，成功后同事务追加审计。"""
    return service.act(session, request.app.state.settings, principal, event_id, body, "close")
