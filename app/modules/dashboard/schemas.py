"""大屏响应：来源、计量覆盖、采样时间和缺数均显式返回，功率为kW而非电量。"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.common.pagination import ApiModel


class PowerOut(ApiModel):
    """每站每系统唯一代表测点的当前值之和；多候选排除，不表示完整站点负荷。"""

    value_kw: float | None = Field(
        description="有效代表功率和，kW；缺测/溢出为null；保留正负号，不是kWh"
    )
    contributing_sites: int = Field(description="参与本系统汇总的有效站点数")
    ambiguous_sites: int = Field(description="多候选计量口径未配置的站点数，包含在missingSites中")
    missing_sites: int = Field(
        description="未贡献有效读数的有效站点数，含无此系统、缺测、过期及歧义"
    )
    eligible_sites: int = Field(description="分母：授权筛选后ACTIVE站点数，不随设备来源变化")
    is_partial: bool = Field(description="有效覆盖不足或无法计算时true，须连同覆盖数展示")
    oldest_sampled_at: datetime | None = Field(description="参与值最早采样时间UTC；无值为null")
    newest_sampled_at: datetime | None = Field(
        description="参与值最晚采样时间UTC；各站采样不一定同刻"
    )


class DeviceStates(ApiModel):
    """所选来源设备的数据状态；不表示设备故障诊断。"""

    normal: int = Field(description="有效站点/设备至少有一条GOOD且新鲜的非空采样，无活动告警")
    warning: int = Field(description="有效站点/设备存在活动事件，不因已确认而恢复")
    offline: int = Field(
        description="有效站点/设备有启用测点但无有效新值，仅表示数据中断或无有效采样"
    )
    unknown: int = Field(description="无启用测点或台账已停用，不能推定现场在线状态")


class SummaryOut(ApiModel):
    """按授权与地理范围统计；站点总数含所有来源，设备/功率/事件按source隔离。"""

    as_of: datetime = Field(description="服务端计算时间UTC，不是源采样时间")
    source: Literal["FIELD", "SIMULATED"] = Field(description="所选设备/功率/事件来源；不允许混加")
    site_count: int = Field(description="全部来源的授权业务台账站点数，不是地图公开位置数")
    demo_site_count: int = Field(description="上述站点中is_demo=1的模拟台账数量")
    active_site_count: int = Field(description="上述站点中ACTIVE的数量，作为功率覆盖分母")
    service_count: int = Field(description="授权业务服务区数量")
    toll_count: int = Field(description="授权业务收费站数量")
    device_count: int = Field(description="所选来源台账设备数，含停用/维护设备")
    device_states: DeviceStates = Field(description="所选来源的设备数据状态，与台账生命周期分开")
    active_alarm_count: int = Field(description="所选来源ACTIVE事件数，确认不等于恢复")
    unacknowledged_alarm_count: int = Field(
        description="所选来源未关闭且未确认事件数，包括已恢复待确认事件"
    )
    power: dict[Literal["GRID", "PV", "ESS", "CHARGING"], PowerOut] = Field(
        description="四系统唯一代表active_power瞬时kW功率；不得将配电/光伏/充电/储能直接相加作为负荷"
    )
    daily_energy_kwh: float | None = Field(
        description="日计量边界尚未配置，当前固定null，不累加瞬时功率或累计表值"
    )
    note: str = Field(description="覆盖、来源、授权集合及未实现计量边界说明")
