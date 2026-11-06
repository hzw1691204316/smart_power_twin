"""采样输入协议：显式时间、质量、序号和来源；不把缺测当0，不允许NaN／无穷。"""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from app.common.access import IdValue
from app.common.pagination import ApiModel


class SampleIn(ApiModel):
    """一个测点采样；(pointId,sampledAt,sourceSequence)是幂等身份，不是接收时间。"""

    model_config = ConfigDict(extra="forbid")

    point_id: IdValue
    sampled_at: AwareDatetime = Field(
        description="带时区采样时间，服务端规范到UTC毫秒；不能超过服务器时间5分钟"
    )
    source_sequence: int = Field(
        default=0,
        ge=0,
        le=9223372036854775807,
        description="同时间源序号；重传保持不变，可传十进制字符串，响应为字符串避免JS精度损失",
    )
    value_numeric: float | None = Field(
        default=None,
        strict=True,
        allow_inf_nan=False,
        description="数值或布尔0/1；质量BAD时可无值，不代填0",
    )
    value_text: str | None = Field(
        default=None, max_length=500, description="文本型测点的值，不与数值同时填写"
    )
    quality: Literal["GOOD", "SUSPECT", "BAD", "MANUAL", "ESTIMATED"] = Field(
        default="GOOD", description="质量独立于来源和过期；仅新鲜GOOD最新数值参与阈值告警"
    )


class BatchIn(ApiModel):
    """同一事务的采样批次；任一身份、类型或来源错误导致整批回滚。"""

    model_config = ConfigDict(extra="forbid")

    source: Literal["SIMULATED", "FIELD"] = Field(
        description="模拟或现场来源；必须与设备isDemo匹配，不允许混入同一身份"
    )
    samples: list[SampleIn] = Field(
        min_length=1, max_length=500, description="1—500条，重复身份且内容一致时忽略，内容冲突409"
    )


class PointConfigIn(ApiModel):
    """完整替换测点周期、阈值及启用配置；不改变单位，以免混淆既有历史。"""

    model_config = ConfigDict(extra="forbid")

    sample_interval_ms: int = Field(
        default=5000, ge=100, le=3600000, description="建议采样周期，毫秒，至少100ms"
    )
    stale_after_ms: int = Field(
        default=15000, ge=100, le=86400000, description="陈旧阈值毫秒，必须不少于采样周期"
    )
    enabled: bool = Field(default=True, description="是否接收该点新采样；停用不自动恢复告警")
    alarm_low: float | None = Field(
        default=None, allow_inf_nan=False, description="简单低阈值，可空；超过边界才告警"
    )
    alarm_high: float | None = Field(
        default=None, allow_inf_nan=False, description="简单高阈值，可空；修改不覆盖旧事件快照"
    )

    @model_validator(mode="after")
    def check_ranges(self):
        """陈旧周期不得比采样周期短，高低阈值必须递增，错误返回422。"""
        if self.stale_after_ms < self.sample_interval_ms:
            raise ValueError("陈旧阈值不能小于采样周期")
        if (
            self.alarm_low is not None
            and self.alarm_high is not None
            and self.alarm_low >= self.alarm_high
        ):
            raise ValueError("低阈值必须小于高阈值")
        return self


class LatestOut(ApiModel):
    """一个测点的最新样本；空值、质量、陈旧和启用状态独立表达。"""

    point_id: str = Field(description="测点ID，用于历史查询")
    code: str = Field(description="设备内测点业务编码")
    name: str = Field(description="测点名称")
    unit: str = Field(description="单位，如kW、kWh、%、°C、BOOL")
    value_type: str = Field(description="NUMERIC、TEXT或BOOLEAN")
    aggregation_type: str = Field(description="INSTANT、COUNTER或STATE")
    value_numeric: float | None = Field(description="数值/布尔0或1；缺失不代填0")
    value_text: str | None = Field(description="文本测点值，非文本或缺失时为空")
    sampled_at: datetime | None = Field(description="源采样UTC带时区时间，无采样为空")
    received_at: datetime | None = Field(description="平台接收UTC带时区时间，无采样为空")
    quality: str | None = Field(description="样本质量，无采样为空；GOOD不代表仍然新鲜")
    is_stale: bool = Field(description="无值或超过配置陈旧阈值；不是资产停用状态")
    age_ms: int | None = Field(description="距采样的毫秒数；无值为空")
    enabled: bool = Field(description="测点是否启用，停用不删除历史")
    source: str = Field(description="SIMULATED模拟或FIELD现场，按设备身份隔离")
    source_sequence: str | None = Field(description="源序号字符串，无采样为空")


class HistoryItem(ApiModel):
    """原始采样或聚合桶；BAD空值留作曲线断点，不能补成0。"""

    sampled_at: datetime = Field(description="带时区UTC采样时间；聚合为UTC桶起点")
    source_sequence: str | None = Field(default=None, description="raw源序号字符串；聚合为空")
    value_numeric: float | None = Field(description="有效数值；聚合无GOOD值时为空")
    value_text: str | None = Field(description="文本值；不适用或无有效值时为空")
    quality: str = Field(description="原始质量；聚合仅使用GOOD，结果GOOD或BAD")
    sample_count: int | None = Field(default=None, description="聚合桶内去除同时间旧修订后的样本数")
    valid_count: int | None = Field(default=None, description="聚合桶内GOOD样本数")


class HistoryOut(ApiModel):
    """有界历史结果；截断时hasMore为true，不能当作完整时段。"""

    point_id: str = Field(description="测点ID")
    unit: str = Field(description="测点单位")
    grain: str = Field(description="raw、1m、5m或1h")
    aggregation: str = Field(description="raw原样、mean瞬时均值、last状态/累计末值")
    items: list[HistoryItem] = Field(description="时间升序历史；空列表代表查询范围无采样")
    has_more: bool = Field(description="返回点数截断；可缩小时间范围或调整粒度")
    note: str = Field(description="累计值与缺口的解释规则")


class IngestOut(ApiModel):
    """整批成功入库统计；重复采样不再插入或修改最新值。"""

    inserted: int = Field(description="本批新增历史行数")
    duplicates: int = Field(description="身份及内容相同的重复行数")
    latest_updated: int = Field(description="推进最新投影的样本条数")
    source: str = Field(description="本批SIMULATED或FIELD")


class PointCreate(PointConfigIn):
    """新增设备测点；编码在本设备内唯一，文本／布尔按STATE处理，不可配置数值阈值。"""

    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$", description="设备内唯一测点编码")
    name: str = Field(min_length=1, max_length=100, description="显示名称")
    unit: str = Field(
        min_length=1, max_length=32, description="单位，如kW、kWh、°C、BOOL；创建后本接口不修改单位"
    )
    value_type: Literal["NUMERIC", "TEXT", "BOOLEAN"] = Field(
        default="NUMERIC", description="数值、文本或布尔0/1"
    )
    aggregation_type: Literal["INSTANT", "COUNTER", "STATE"] = Field(
        default="INSTANT", description="瞬时、累计或状态；TEXT/BOOLEAN需STATE"
    )
    direction_convention: str | None = Field(
        default=None, max_length=300, description="明确正负方向，例如储能正放电、负充电"
    )

    @model_validator(mode="after")
    def check_type(self):
        """禁止将文本／布尔当数值计量或应用数值阈值。"""
        if self.value_type != "NUMERIC" and (
            self.aggregation_type != "STATE"
            or self.alarm_low is not None
            or self.alarm_high is not None
        ):
            raise ValueError("文本／布尔必须使用STATE且不配置数值阈值")
        return self


class PointOut(ApiModel):
    """已存在测点的只读定义；ID以字符串传输，阈值是配置而非采样。"""

    id: str = Field(description="测点主键，十进制字符串")
    site_id: str = Field(description="所属授权站点主键")
    device_id: str = Field(description="所属设备主键")
    code: str = Field(description="设备内唯一测点编码")
    name: str = Field(description="测点显示名称")
    unit: str = Field(description="测量单位")
    value_type: str = Field(description="NUMERIC、TEXT或BOOLEAN")
    aggregation_type: str = Field(description="INSTANT瞬时、COUNTER累计或STATE状态")
    sample_interval_ms: int = Field(description="建议采样周期，毫秒")
    stale_after_ms: int = Field(description="陈旧阈值，毫秒")
    enabled: bool = Field(description="是否接收新样本")
    alarm_low: float | None = Field(description="低阈值配置，可空；本模块不执行告警评估")
    alarm_high: float | None = Field(description="高阈值配置，可空；本模块不执行告警评估")
    direction_convention: str | None = Field(description="正负方向说明，可空")
