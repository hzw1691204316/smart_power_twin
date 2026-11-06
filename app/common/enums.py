"""公共枚举：限定API筛选值和响应类型，保持与现有台账表一致。

此处状态均是资产生命周期，不代表监测在线、告警或数据新鲜度。"""

from enum import Enum


class SiteType(str, Enum):
    """站点类型：TOLL收费站；SERVICE服务区。"""

    TOLL = "TOLL"
    SERVICE = "SERVICE"


class ScaleLevel(str, Enum):
    """业务展示规模：S小型、M中型、L大型；不表示模型文件一定已经制作。"""

    S = "S"
    M = "M"
    L = "L"


class SiteStatus(str, Enum):
    """站点生命周期：ACTIVE有效、INACTIVE停用、RETIRED退役。"""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    RETIRED = "RETIRED"


class DeviceStatus(str, Enum):
    """设备生命周期：ACTIVE有效、MAINTENANCE维护、INACTIVE停用、RETIRED退役。"""

    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    INACTIVE = "INACTIVE"
    RETIRED = "RETIRED"


class EnergySystem(str, Enum):
    """设备所属系统：PV光伏、ESS储能、CHARGING充电、GRID配电／电网、LOAD负荷、AUX辅助。"""

    PV = "PV"
    ESS = "ESS"
    CHARGING = "CHARGING"
    GRID = "GRID"
    LOAD = "LOAD"
    AUX = "AUX"
