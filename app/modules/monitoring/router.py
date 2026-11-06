"""监测接口：获授权设备／测点查询、带时区历史和受限采样批次。"""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.api.dependencies import get_session, require_permission
from app.common.access import PathId, require_device, result
from app.common.pagination import Result
from app.modules.monitoring import repository, service
from app.modules.monitoring.schemas import (
    BatchIn,
    HistoryOut,
    IngestOut,
    LatestOut,
    PointConfigIn,
    PointCreate,
    PointOut,
)

router = APIRouter(tags=["测点与监测"])


@router.get(
    "/devices/{device_id}/points",
    response_model=Result[list[PointOut]],
    summary="设备测点定义（单位、周期、阈值）",
)
def points(
    device_id: PathId,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("monitor:read")),
):
    """device_id为设备主键；先按站点范围授权，再返回定义，不是最新读数。"""
    device = require_device(session, principal, device_id)
    return result(
        [service.point_out(p) for p in repository.device_points(session, device.id)],
        request.app.state.settings,
    )


@router.get(
    "/devices/{device_id}/latest",
    response_model=Result[list[LatestOut]],
    summary="设备最新值、来源、质量和是否过期",
)
def latest(
    device_id: PathId,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("monitor:read")),
):
    """无采样时返回null；isStale独立于quality，不能用ACTIVE台账状态判断在线。"""
    device = require_device(session, principal, device_id)
    definitions = repository.device_points(session, device.id)
    values = repository.latest_values(session, [p.id for p in definitions])
    return result(
        [service.latest_out(p, values.get(p.id), device.is_demo) for p in definitions],
        request.app.state.settings,
    )


@router.get(
    "/points/{point_id}/history",
    response_model=Result[HistoryOut],
    summary="有界原始历史或1m／5m／1h聚合",
)
def history(
    point_id: PathId,
    request: Request,
    start_time: AwareDatetime = Query(alias="startTime", description="带时区开始时间，包含"),
    end_time: AwareDatetime = Query(
        alias="endTime", description="带时区结束时间，不包含；范围最多31天"
    ),
    limit: int = Query(1000, ge=1, le=2000, description="最多返回点数，截断时hasMore=true"),
    grain: Literal["raw", "1m", "5m", "1h"] = Query(
        "raw", description="原始或聚合粒度，累计电量取末值而非求和"
    ),
    session: Session = Depends(get_session),
    principal=Depends(require_permission("monitor:read")),
):
    """UTC转换后查询[startTime,endTime)；缺口不补0，聚合原始记录最多1万条。"""
    return service.history(
        session, request.app.state.settings, principal, point_id, start_time, end_time, limit, grain
    )


@router.post(
    "/telemetry/batches",
    response_model=Result[IngestOut],
    summary="提交采样批次（幂等、来源及类型检查）",
)
def ingest(
    body: BatchIn,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("telemetry:write")),
):
    """需采集动作及站点范围；错误整批回滚。有效新鲜最新数值按配置阈值触发/恢复告警。"""
    return service.ingest(session, request.app.state.settings, principal, body)


@router.post(
    "/devices/{device_id}/points",
    response_model=Result[PointOut],
    status_code=201,
    summary="新增设备测点定义，不生成假读数",
)
def create_point(
    device_id: PathId,
    body: PointCreate,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("monitor:configure")),
):
    """指定获授权设备及单位／数据类型／周期，创建后可在草稿场景中建立绑定。"""
    device = require_device(session, principal, device_id)
    return service.create_point(session, request.app.state.settings, principal, device, body)


@router.put(
    "/points/{point_id}/config",
    response_model=Result[PointOut],
    summary="修改测点周期、启用及简单阈值",
)
def configure(
    point_id: PathId,
    body: PointConfigIn,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("monitor:configure")),
):
    """完整提交配置；关闭采样不等于故障恢复，阈值变更不改写历史事件解释。"""
    return service.configure_point(session, request.app.state.settings, principal, point_id, body)
