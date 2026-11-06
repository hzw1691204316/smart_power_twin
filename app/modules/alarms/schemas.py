"""告警协议：动作参数严格校验；确认、恢复、关闭各自表达，不允许客户端伪造事件快照。"""

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from app.common.pagination import ApiModel

AlarmStatus = Literal["ACTIVE", "RECOVERED", "CLOSED"]
AlarmSeverity = Literal["INFO", "MINOR", "MAJOR", "CRITICAL"]


class ActionIn(ApiModel):
    """首次确认/关闭的可选处理说明；未知字段422，不接受恢复时间、确认人等身份字段。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    handling_note: str = Field(
        default="", max_length=1000, description="本次处理说明；重试不覆盖首次操作记录"
    )


class AlarmOut(ApiModel):
    """事件详情，主键均为字符串；关联名称是当前台账，triggerSnapshot是发生时的快照。"""

    id: str = Field(description="告警事件ID，用于详情、确认及关闭")
    site_id: str = Field(description="所属授权站点ID")
    site_name: str = Field(description="当前站点名称")
    device_id: str | None = Field(description="设备ID；站点级事件可空")
    device_name: str | None = Field(description="当前设备名称；站点级事件可空")
    point_id: str | None = Field(description="测点ID，用于历史趋势；无测点可空")
    point_name: str | None = Field(description="当前测点名称")
    unit: str | None = Field(description="当前测点单位；发生时单位以triggerSnapshot为准")
    status: AlarmStatus = Field(description="ACTIVE活动/RECOVERED已恢复/CLOSED已关闭；确认独立")
    severity: AlarmSeverity = Field(description="INFO提示/MINOR一般/MAJOR重要/CRITICAL紧急")
    message: str = Field(description="事件发生时的描述，非设备当前状态")
    raised_at: datetime = Field(description="发生时间，带时区UTC")
    recovered_at: datetime | None = Field(description="恢复采样时间，带时区UTC；未恢复为空")
    acknowledged_at: datetime | None = Field(description="首次人工确认UTC时间；未确认为空")
    acknowledged_by: str | None = Field(description="首次确认人用户ID，不返回密码")
    acknowledged_by_name: str | None = Field(description="首次确认人的当前用户名")
    handling_note: str | None = Field(description="最近一次有效确认/关闭填写的说明")
    trigger_snapshot: dict | list | None = Field(description="发生时的来源、规则、阈值和值等快照")
    is_demo: bool = Field(description="站点/设备是否为演示资产；不能当作现场事件")
    source: Literal["SIMULATED", "FIELD", "UNKNOWN"] = Field(
        description="发生快照中的来源；无明确标记则UNKNOWN，库在MySQL不等于现场数据"
    )
