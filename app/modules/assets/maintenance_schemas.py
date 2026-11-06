"""台账维护输入：白名单字段、明确单位与缺省值；身份和来源在创建后不允许改写。"""

from decimal import Decimal

from pydantic import ConfigDict, Field, model_validator

from app.common.access import IdValue
from app.common.enums import DeviceStatus, EnergySystem, ScaleLevel, SiteStatus, SiteType
from app.common.pagination import ApiModel


class AssetInput(ApiModel):
    """拒绝未知字段，字符串统一去空白；禁止注入ID/来源身份等未声明列。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SiteEdit(AssetInput):
    """完整保存可编辑字段；code/siteType/isDemo创建后固定，防止原场景/采样关系失效。"""

    name: str = Field(min_length=1, max_length=150, description="站点显示名称，不能作为关联主键")
    scale_level: ScaleLevel = Field(description="S/M/L；已有三维场景时禁止改变规模")
    province_code: str = Field(
        pattern=r"^[1-9][0-9](?:0000)?$", description="两位或六位省级代码，如41/410000"
    )
    city_name: str | None = Field(None, max_length=100, description="地市名称，未知null")
    longitude: Decimal | None = Field(
        None,
        ge=-180,
        le=180,
        max_digits=11,
        decimal_places=7,
        description="WGS84经度；和纬度同时填写或同时为空，最多7位小数",
    )
    latitude: Decimal | None = Field(
        None,
        ge=-90,
        le=90,
        max_digits=10,
        decimal_places=7,
        description="WGS84纬度；未知null，不能用0代替",
    )
    location_source: str | None = Field(None, max_length=500, description="坐标资料来源及核验说明")
    complex_code: str | None = Field(None, max_length=64, description="共同站区分组码；无配对null")
    asset_status: SiteStatus = Field(description="ACTIVE/INACTIVE/RETIRED，停用不级联删除历史")
    primary_route_id: IdValue | None = Field(
        None, description="可选有效主路线ID；null只取消主标记，不删除其他路线关系"
    )

    @model_validator(mode="after")
    def coordinate_pair(self):
        """只允许完整坐标或都未知，防止在地图上生成半个位置。"""
        if (self.longitude is None) != (self.latitude is None):
            raise ValueError("经纬度必须同时填写或同时为空")
        return self


class SiteCreate(SiteEdit):
    """新增站点；创建者在同一事务获得新站范围，不给其他用户自动授权。"""

    code: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$", description="全局唯一业务编码；创建后固定")
    site_type: SiteType = Field(description="SERVICE或TOLL；创建后固定")
    is_demo: bool = Field(description="是否模拟台账；必须明确选择，创建后固定")


class DeviceEdit(AssetInput):
    """设备可编辑资料；站点/编码/类型/系统/模拟身份不可变，历史和测点归属保持。"""

    name: str = Field(min_length=1, max_length=150, description="设备显示名称")
    asset_status: DeviceStatus = Field(
        description="ACTIVE/MAINTENANCE/INACTIVE/RETIRED；不是实时状态"
    )
    area_id: IdValue | None = Field(None, description="本站区域ID，未知null")
    parent_device_id: IdValue | None = Field(None, description="本站父设备ID；禁止自指和父设备环")
    rated_power_kw: Decimal | None = Field(
        None, ge=0, max_digits=14, decimal_places=4, description="额定功率kW，非实时功率；未知null"
    )
    rated_energy_kwh: Decimal | None = Field(
        None,
        ge=0,
        max_digits=14,
        decimal_places=4,
        description="额定储能电量kWh，非日用电；未知null",
    )
    rated_capacity_kva: Decimal | None = Field(
        None, ge=0, max_digits=14, decimal_places=4, description="额定视在容量kVA，未知null"
    )
    manufacturer: str | None = Field(None, max_length=100, description="厂家名称，未知null")
    model_code: str | None = Field(
        None, max_length=100, description="厂家型号；不是GLB路径，未知null"
    )


class DeviceCreate(DeviceEdit):
    """在已授权有效站点新增设备；没有测点、历史或场景时不自动生成样例数据。"""

    code: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$", description="站内唯一设备编码，创建后固定")
    device_type: str = Field(
        min_length=1, max_length=32, description="设备类型编码，如TRANSFORMER、CHARGER"
    )
    system_type: EnergySystem = Field(description="PV/ESS/CHARGING/GRID/LOAD/AUX，创建后固定")
    is_demo: bool = Field(description="模拟或现场设备身份，创建后固定；采样来源必须匹配")
