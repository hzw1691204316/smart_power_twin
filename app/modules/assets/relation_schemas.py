"""站内关系输入：区域树与高速方向关联；只维护授权站点，不编辑共享路线字典或地图几何。"""

from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.common.access import IdValue
from app.modules.assets.maintenance_schemas import AssetInput


class AreaEdit(AssetInput):
    """完整保存区域显示、类型及父关系；区域不删除，设备和场景仍通过ID引用。"""

    name: str = Field(min_length=1, max_length=150, description="区域名称，例如北侧配电房")
    area_type: str = Field(
        pattern=r"^[A-Z][A-Z0-9_]{0,31}$",
        description="区域类型编码，如DIRECTION/BUILDING/PARKING/POWER_ROOM",
    )
    parent_id: IdValue | None = Field(None, description="同站父区域ID；顶层为null，禁止自指或成环")


class AreaCreate(AreaEdit):
    """新增站内区域；code在本站内唯一，创建后固定。"""

    code: str = Field(
        pattern=r"^[A-Za-z0-9_-]{1,64}$", description="本站唯一的区域编码，创建后固定"
    )


class RouteLinkEdit(AssetInput):
    """完整保存一条站点路线方向关系，支持换路线修正，不修改共享路线本身。"""

    route_id: IdValue = Field(description="既有高速路线主键；新增或改关联必须选择有效路线")
    area_id: IdValue | None = Field(
        None, description="本站方向/空间区域ID，可空；不自动改设备所在区域"
    )
    direction_code: Literal["UP", "DOWN", "BOTH", "UNKNOWN"] = Field(
        description="上行/下行/双向/待核验，不根据地名猜测"
    )
    direction_label: str | None = Field(
        None, max_length=100, description="具体方向说明，如往郑州方向；未知null"
    )
    chainage_m: Decimal | None = Field(
        None,
        ge=0,
        max_digits=12,
        decimal_places=3,
        description="米制里程桩号，最多3位小数；0有效，未知null",
    )
    access_type: Literal["DIRECT", "INTERCHANGE", "OTHER"] = Field(
        description="直接接入/互通接入/其他"
    )
    is_primary: bool = Field(description="本站主关联；设true会取消其他关联的主标记，不删除其资料")


class RouteLinkCreate(RouteLinkEdit):
    """新增方向关联；同一路线可按不同编码配置上下行，整个站点最多一个主关联。"""

    link_code: str = Field(
        pattern=r"^[A-Za-z0-9_-]{1,64}$", description="本站唯一关联编码，如G4_UP，创建后固定"
    )
