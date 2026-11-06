"""台账API响应模型：说明返回字段、单位和空值，不承担数据库查询。

ID统一字符串；额定参数与实时监测分开；Field说明会显示在/docs的响应Schemas中。"""

from pydantic import Field

from app.common.enums import DeviceStatus, EnergySystem, ScaleLevel, SiteStatus, SiteType
from app.common.pagination import ApiModel


class RouteOut(ApiModel):
    """一个站点与路线的关联；id为关联记录ID，route_id才是路线ID。"""

    id: str = Field(description="站点路线关联记录ID，十进制字符串；不是路线ID")
    site_id: str = Field(description="唯一所属站点ID")
    link_code: str = Field(description="本站关联编码；创建后固定")
    area_id: str | None = Field(description="本站方向/空间区域ID，可空")
    route_id: str = Field(description="高速路线主键，十进制字符串")
    route_code: str = Field(description="路线业务编号，例如S26、G4")
    name: str = Field(description="路线名称；演示关联不等于官方核验结果")
    direction_code: str = Field(description="UP上行、DOWN下行、BOTH双向、UNKNOWN待核验")
    direction_label: str | None = Field(description="方向文字说明；未知时可以为空")
    is_primary: bool = Field(description="是否为该站点的主路线关联")
    chainage_m: float | None = Field(description="里程桩号，单位米；未知null，0有效")
    access_type: str = Field(description="DIRECT直接接入、INTERCHANGE互通、OTHER其他")


class SiteOut(ApiModel):
    """站点台账及路线列表，不包含实时功率、历史曲线或模型对象绑定。"""

    id: str = Field(description="数据库站点主键，以字符串传输，避免JavaScript大整数精度损失")
    code: str = Field(description="唯一业务编码；与数据库主键、前端旧演示ID分开")
    name: str = Field(description="站点显示名称；不能作为设备绑定的唯一身份")
    site_type: SiteType = Field(description="SERVICE服务区，TOLL收费站")
    scale_level: ScaleLevel = Field(description="S小型、M中型、L大型，业务展示分级")
    complex_code: str | None = Field(description="共同站区分组码；可用于朝歌两站配对，未分组可为空")
    province_code: str = Field(description="标准六位省级代码，例如410000；兼容库内两位存法")
    city_name: str | None = Field(description="地市名称；当前SQL没有独立city_code，未知可为空")
    longitude: float | None = Field(
        description="经度，单位度；与coordinateSystem共同解释，未知为null"
    )
    latitude: float | None = Field(description="纬度，单位度；未知为null，不使用0代替缺测坐标")
    coordinate_system: str = Field(description="坐标系，例如WGS84；不能混用不同坐标系")
    location_source: str | None = Field(
        description="参考坐标的来源及核验边界；公开位置不等于实测入口"
    )
    is_demo: bool = Field(description="是否为演示台账；使用MySQL并不保证记录为现场资料")
    asset_status: SiteStatus = Field(description="资产生命周期，不表示在线或告警状态")
    routes: list[RouteOut] = Field(description="本站路线及方向关联，无关联返回空数组")


class DeviceOut(ApiModel):
    """设备台账及额定参数；额定kW、kWh、kVA分开，未知参数为None／JSON null。"""

    id: str = Field(description="设备数据库主键，十进制字符串")
    site_id: str = Field(description="唯一所属站点ID；设备详情同时校验站点和设备身份")
    area_id: str | None = Field(description="所属站内区域ID，尚未分配时为空")
    parent_device_id: str | None = Field(description="同站父设备ID，用于组成关系；独立设备为空")
    code: str = Field(description="站内唯一设备业务编码；不同站点可以使用相同编码")
    name: str = Field(description="设备显示名称，不保证全系统唯一")
    device_type: str = Field(description="台账设备类型，如ESS_CABINET、TRANSFORMER；不是模型对象键")
    system_type: EnergySystem = Field(
        description="PV光伏、ESS储能、CHARGING充电、GRID配电、LOAD负荷、AUX辅助"
    )
    asset_status: DeviceStatus = Field(
        description="资产有效、维护、停用或退役；ACTIVE不表示实时在线"
    )
    rated_power_kw: float | None = Field(
        description="额定有功功率，单位kW；不是当前功率，未知为null"
    )
    rated_energy_kwh: float | None = Field(
        description="额定储能电量，单位kWh；不是当天电量，未知为null"
    )
    rated_capacity_kva: float | None = Field(
        description="额定视在容量，单位kVA，常用于变压器；未知为null"
    )
    manufacturer: str | None = Field(description="设备厂家，未录入为空")
    model_code: str | None = Field(description="厂家型号，未录入为空；不代表GLB文件地址")
    is_demo: bool = Field(description="是否为虚构演示设备；额定参数需现场核验")


class AreaOut(ApiModel):
    """站内空间区域；parent_id表达同站区域树，当前接口返回平铺列表。"""

    id: str = Field(description="站内区域主键，十进制字符串")
    site_id: str = Field(description="所属站点ID；父子区域必须同站")
    parent_id: str | None = Field(description="同站上级区域ID；顶层区域为null")
    code: str = Field(description="站内唯一的区域编码")
    name: str = Field(description="区域显示名称，例如配电及储能区")
    area_type: str = Field(
        description="区域类型，例如POWER_ROOM配电房、PARKING停车区、BUILDING建筑"
    )


class HighwayOut(ApiModel):
    """业务路线目录条目；资源地址可空，不代表已经接入该路线的完整几何。"""

    id: str = Field(description="路线数据库主键，十进制字符串")
    route_code: str = Field(description="唯一业务路线编号，例如S26")
    name: str = Field(description="路线名称")
    status: str = Field(description="ACTIVE有效、INACTIVE停用；不是交通拥堵或通行状态")
    geometry_uri: str | None = Field(description="可选路线几何资源地址；为空不意味着道路不存在")
    coordinate_system: str = Field(description="路线几何坐标系统，例如WGS84")
