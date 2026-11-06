"""大屏汇总入口：支持全国授权集合、省、市和站点筛选，统一监测有效性口径。"""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_session, require_permission
from app.common.access import require_site, result
from app.common.pagination import Result
from app.core.exceptions import BusinessError
from app.modules.dashboard.schemas import SummaryOut
from app.modules.dashboard.service import summarize

router = APIRouter(tags=["大屏统计"])


@router.get(
    "/dashboard/summary",
    response_model=Result[SummaryOut],
    summary="授权范围内的大屏统计与功率覆盖",
)
def summary(
    request: Request,
    province_code: str | None = Query(
        None, alias="provinceCode", pattern=r"^[1-9][0-9](?:0000)?$", description="两位或六位省代码"
    ),
    city_name: str | None = Query(
        None,
        alias="cityName",
        min_length=1,
        max_length=100,
        description="地市名称，例如鹤壁或鹤壁市",
    ),
    site_id: str | None = Query(
        None, alias="siteId", pattern=r"^[1-9][0-9]{0,19}$", description="可选获授权站点ID"
    ),
    source: Literal["FIELD", "SIMULATED"] = Query(
        "FIELD", description="设备/功率/事件来源：FIELD现场或SIMULATED模拟，默认现场，不混加"
    ),
    session: Session = Depends(get_session),
    principal=Depends(require_permission("dashboard:read")),
):
    """先按站点授权再统计；指定未授权站点404，无数据时功率null，partial明确覆盖。"""
    if city_name is not None and not city_name.strip():
        raise BusinessError("INVALID_CITY", "地市名称不能为空白", 422)
    site = require_site(session, principal, site_id) if site_id else None
    return result(
        summarize(session, principal, province_code, city_name, site.id if site else None, source),
        request.app.state.settings,
    )
