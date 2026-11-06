"""台账HTTP接口：接收并校验参数、注入服务、声明响应模型。

公开JSON为camelCase，Python参数为snake_case；业务规则在service，数据库访问在repository。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_assets, get_session, require_permission
from app.common.enums import DeviceStatus, EnergySystem, ScaleLevel, SiteStatus, SiteType
from app.common.pagination import Page, Result
from app.modules.assets import maintenance, relations
from app.modules.assets.maintenance_schemas import DeviceCreate, DeviceEdit, SiteCreate, SiteEdit
from app.modules.assets.relation_schemas import AreaCreate, AreaEdit, RouteLinkCreate, RouteLinkEdit
from app.modules.assets.schemas import AreaOut, DeviceOut, HighwayOut, RouteOut, SiteOut
from app.modules.assets.service import AssetService

router = APIRouter(tags=["站点与设备台账"])
AssetDep = Annotated[AssetService, Depends(get_assets)]
AssetId = Annotated[
    str,
    Path(pattern=r"^[1-9][0-9]{0,19}$", description="数据库数字ID，以字符串传输；从列表响应中复制"),
]


@router.get("/sites", response_model=Page[SiteOut], summary="分页查询站点（支持组合筛选）")
def list_sites(
    service: AssetDep,
    page: int = Query(1, ge=1, le=10000, description="页码，从1开始；超过末页返回空数组"),
    page_size: int = Query(
        20, alias="pageSize", ge=1, le=100, description="每页条数，1—100；默认20"
    ),
    q: str = Query("", max_length=120, description="空格分词，例如：鹤壁 朝歌 S26"),
    site_type: SiteType | None = Query(
        None, alias="siteType", description="SERVICE服务区、TOLL收费站；省略为全部"
    ),
    scale: ScaleLevel | None = None,
    province_code: str | None = Query(
        None,
        alias="provinceCode",
        pattern=r"^[1-9][0-9](?:0000)?$",
        description="省代码41或410000；不能传城市代码410600",
    ),
    city_name: str | None = Query(
        None,
        alias="cityName",
        min_length=1,
        max_length=100,
        description="城市名称，例如鹤壁或鹤壁市；当前库无city_code字段",
    ),
    highway: str | None = Query(
        None,
        pattern=r"^[GgSs][0-9]{1,6}$",
        description="完整路线编号，如S26、G4；大小写兼容，G4不匹配G40",
    ),
    status: SiteStatus | None = None,
):
    """组合筛选与分页查询站点。

    service为框架注入，无需在页面填写；page从1开始，pageSize为1—100；q按空格分词且所有词同时满足。
    siteType区分服务区／收费站，scale为规模，provinceCode为两位或六位省码，cityName为城市名称，
    highway为完整路线号，status为资产生命周期。省略筛选项表示不限。
    返回当前页站点和来源／分页meta；无匹配返回空数组，参数不合法返回422。"""
    return service.list_sites(
        page,
        page_size,
        q=q,
        site_type=site_type,
        scale=scale,
        province_code=province_code,
        city_name=city_name,
        highway=highway,
        status=status,
    )


@router.get("/sites/{site_id}", response_model=Result[SiteOut], summary="站点详情与路线关联")
def site_detail(site_id: AssetId, service: AssetDep):
    """参数site_id为站点数字ID的字符串形式，service由框架注入。

    返回站点台账及路线关联；不存在404，主键格式或范围错误422；没有实时电力或场景信息。"""
    return service.site_detail(site_id)


@router.get(
    "/sites/{site_id}/devices",
    response_model=Page[DeviceOut],
    summary="本站设备台账（非实时读数）",
    dependencies=[Depends(require_permission("device:read"))],
)
def list_devices(
    site_id: AssetId,
    service: AssetDep,
    page: int = Query(1, ge=1, le=10000, description="页码，从1开始"),
    page_size: int = Query(
        20, alias="pageSize", ge=1, le=100, description="每页条数，1—100；默认20"
    ),
    system_type: EnergySystem | None = Query(
        None,
        alias="systemType",
        description="PV光伏、ESS储能、CHARGING充电、GRID配电、LOAD负荷、AUX辅助",
    ),
    status: DeviceStatus | None = None,
    q: str = Query(
        "", max_length=120, description="按设备名称、编码空格分词搜索；所有关键词同时满足"
    ),
):
    """查询site_id所属设备台账。

    page/pageSize控制分页，systemType为PV/ESS/CHARGING/GRID/LOAD/AUX，status为资产状态，
    q按名称或编码分词；service无需填写。返回当前页设备，只有额定参数，不能当现场实时读数。
    站点不存在返回404；存在但无匹配设备返回200空列表。"""
    return service.list_devices(
        site_id, page, page_size, system_type=system_type, status=status, q=q
    )


@router.get(
    "/sites/{site_id}/devices/{device_id}",
    response_model=Result[DeviceOut],
    summary="查询本站指定设备，校验设备归属",
    dependencies=[Depends(require_permission("device:read"))],
)
def device_detail(site_id: AssetId, device_id: AssetId, service: AssetDep):
    """参数site_id为站点ID，device_id为设备ID，均从列表复制；service无需填写。

    返回本站指定设备；跨站设备与不存在设备统一404，避免错误关联。"""
    return service.device_detail(site_id, device_id)


@router.get("/sites/{site_id}/areas", response_model=Result[list[AreaOut]], summary="站内区域列表")
def list_areas(site_id: AssetId, service: AssetDep):
    """参数site_id为站点ID字符串，service为注入服务。

    返回区域数组，以parentId表达父子关系；站点不存在404，本站无区域返回空数组。"""
    return service.list_areas(site_id)


@router.get(
    "/highways", response_model=Page[HighwayOut], summary="业务路线目录（不是全部公开高速路网）"
)
def list_highways(
    service: AssetDep,
    page: int = Query(1, ge=1, le=10000, description="页码，从1开始"),
    page_size: int = Query(
        20, alias="pageSize", ge=1, le=100, description="每页条数，1—100；默认20"
    ),
    q: str = Query(
        "", max_length=120, description="路线名称或编号关键词；查询业务台账，不是全省地图几何"
    ),
):
    """参数page/pageSize为分页，q为路线名称或编号关键词，service无需填写。

    返回业务路线台账，不是全省公开高速数据；默认demo仅有S26演示关联。"""
    return service.list_highways(page, page_size, q)


# 维护入口与只读查询分开组织，写操作同时检查动作、站点范围及MySQL写入开关。


@router.post(
    "/sites/{site_id}/areas",
    response_model=Result[AreaOut],
    status_code=201,
    summary="新增本站区域",
    dependencies=[Depends(require_permission("site:read"))],
)
def create_area(
    site_id: AssetId,
    body: AreaCreate,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("asset:manage")),
):
    """仅授权有效站点可新建；父区域同站且无环，不自动分配设备或生成模型。"""
    return relations.save_area(session, request.app.state.settings, principal, site_id, body)


@router.put(
    "/sites/{site_id}/areas/{area_id}",
    response_model=Result[AreaOut],
    summary="保存本站区域及父关系",
    dependencies=[Depends(require_permission("site:read"))],
)
def update_area(
    site_id: AssetId,
    area_id: AssetId,
    body: AreaEdit,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("asset:manage")),
):
    """区域ID/code固定；跨站或不存在404，父链循环409，不删除子区域/设备/历史。"""
    return relations.save_area(
        session, request.app.state.settings, principal, site_id, body, area_id
    )


@router.post(
    "/sites/{site_id}/routes",
    response_model=Result[RouteOut],
    status_code=201,
    summary="新增本站高速方向关联",
    dependencies=[Depends(require_permission("site:read"))],
)
def create_route_link(
    site_id: AssetId,
    body: RouteLinkCreate,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("asset:manage")),
):
    """同一路线可有多条上下行关系；设为主关联时取消其他主标记，旧关联资料保留。"""
    return relations.save_route_link(session, request.app.state.settings, principal, site_id, body)


@router.put(
    "/sites/{site_id}/routes/{link_id}",
    response_model=Result[RouteOut],
    summary="保存本站路线方向与里程资料",
    dependencies=[Depends(require_permission("site:read"))],
)
def update_route_link(
    site_id: AssetId,
    link_id: AssetId,
    body: RouteLinkEdit,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("asset:manage")),
):
    """link_id是关联ID，不是路线ID；米制桩号未知null，不编辑公共字典或GeoJSON。"""
    return relations.save_route_link(
        session, request.app.state.settings, principal, site_id, body, link_id
    )


@router.post(
    "/sites",
    response_model=Result[SiteOut],
    status_code=201,
    summary="新增站点并仅授权创建者",
    dependencies=[Depends(require_permission("site:read"))],
)
def create_site(
    body: SiteCreate,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("site:create")),
):
    """新增台账和创建者新站范围同事务；编码/站型/模拟身份创建后固定，不自动生成设备或场景。"""
    return maintenance.save_site(session, request.app.state.settings, principal, body)


@router.put(
    "/sites/{site_id}",
    response_model=Result[SiteOut],
    summary="保存本站台账资料与生命周期",
    dependencies=[Depends(require_permission("site:read"))],
)
def update_site(
    site_id: AssetId,
    body: SiteEdit,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("asset:manage")),
):
    """site_id须已授权，已有三维场景冻结规模；停用不删除子记录，不自动停用设备或关闭事件。"""
    return maintenance.save_site(session, request.app.state.settings, principal, body, site_id)


@router.post(
    "/sites/{site_id}/devices",
    response_model=Result[DeviceOut],
    status_code=201,
    summary="在本站新增设备台账",
    dependencies=[
        Depends(require_permission("site:read")),
        Depends(require_permission("device:read")),
    ],
)
def create_device(
    site_id: AssetId,
    body: DeviceCreate,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("asset:manage")),
):
    """只能在授权ACTIVE站点创建；区域/父设备必须同站，不自动生成测点或电力读数。"""
    return maintenance.save_device(session, request.app.state.settings, principal, site_id, body)


@router.put(
    "/sites/{site_id}/devices/{device_id}",
    response_model=Result[DeviceOut],
    summary="保存本站设备资料与生命周期",
    dependencies=[
        Depends(require_permission("site:read")),
        Depends(require_permission("device:read")),
    ],
)
def update_device(
    site_id: AssetId,
    device_id: AssetId,
    body: DeviceEdit,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_permission("asset:manage")),
):
    """设备归属及身份固定；父链不能成环；停用/维护后采集接口按已有设备状态拒绝新入库。"""
    return maintenance.save_device(
        session, request.app.state.settings, principal, site_id, body, device_id
    )
