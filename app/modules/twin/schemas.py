"""场景版本与绑定输入；对象身份和测点必须属于同站同设备，不通过名称猜测。"""

from datetime import datetime

from pydantic import ConfigDict, Field, JsonValue, field_validator

from app.common.access import IdValue
from app.common.pagination import ApiModel


class CloneIn(ApiModel):
    """复制当前发布场景为新草稿，选填模型路径只能位于前端/models下。"""

    model_config = ConfigDict(extra="forbid")

    model_url: str | None = Field(
        default=None,
        pattern=r"^/models/[A-Za-z0-9_-]+\.glb$",
        description="可选本站GLB路径，未填沿用现有模型；不是任意本地文件或外网URL",
    )


class ObjectIn(ApiModel):
    """草稿模型对象：稳定GLB键、显示名称和可空的本站设备ID；不改变模型位姿。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    object_key: str = Field(min_length=1, max_length=100, description="GLB节点名或完整下划线前缀")
    name: str = Field(min_length=1, max_length=100, description="对象的中文显示名称")
    device_id: IdValue | None = Field(default=None, description="本站设备ID；空值为非监测对象")


class ObjectsIn(ApiModel):
    """完整替换草稿对象配置；保留相同键的ID，已有绑定的对象不能直接删除或换设备。"""

    model_config = ConfigDict(extra="forbid")

    objects: list[ObjectIn] = Field(max_length=200, description="对象全集，空数组清空未绑定对象")


class FromTemplateIn(ObjectsIn):
    """从本站类型与规模相符的已发布模板创建空绑定草稿，不要求已有发布场景。"""

    template_id: IdValue = Field(description="已发布模板的数据库ID；不等于模板编码")


class TemplateObjectsOut(ApiModel):
    """经实际GLB校验的推荐对象键；没有清单时列出可配置的命名节点。"""

    template_id: str = Field(description="模板数据库ID")
    object_keys: list[str] = Field(description="可选对象键；设备关系必须人工选择，不通过名称推测")


class BindingIn(ApiModel):
    """一个对象属性与测点的绑定；propertyCode同对象内唯一，映射参数仅为展示配置。"""

    model_config = ConfigDict(extra="forbid")

    object_id: IdValue
    point_id: IdValue
    property_code: str = Field(
        pattern=r"^[a-z][a-z0-9_]{0,63}$", description="属性编码，如power_kw、soc、temperature"
    )
    mapping_config: dict[str, JsonValue] | None = Field(
        default=None, description="可选显示映射，限制在配置中使用，不能执行脚本"
    )

    @field_validator("mapping_config")
    @classmethod
    def valid_mapping(cls, value):
        """参数value仅作JSON展示元数据，拒绝非有限数及超过8192字节，不执行其中脚本。"""
        import json

        if value is not None:
            try:
                payload = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
            except ValueError:
                raise ValueError("映射配置不能含NaN或无穷") from None
            if len(payload) > 8192:
                raise ValueError("映射配置最多8192字节")
        return value


class BindingsIn(ApiModel):
    """完整替换指定草稿的绑定；空数组清空，已发布场景必须先复制草稿。"""

    model_config = ConfigDict(extra="forbid")

    bindings: list[BindingIn] = Field(
        max_length=500, description="草稿绑定全集；重复对象属性或跨站跨设备拒绝"
    )


class TemplateOut(ApiModel):
    """模板目录：未制作资源可空；中型及已注册大型服务区可用，目录不等于现场测绘。"""

    id: str = Field(description="模板数据库ID，字符串")
    code: str = Field(description="TOLL/SERVICE加S/M/L的模板编码")
    site_type: str = Field(description="收费站TOLL或服务区SERVICE")
    scale_level: str = Field(description="S小、M中、L大")
    version: int = Field(description="模板版本号")
    status: str = Field(description="DRAFT/PUBLISHED/ARCHIVED")
    model_url: str | None = Field(description="前端/models下GLB路径；未制作为空")


class SceneSummary(ApiModel):
    """场景版本身份和资源；不携带测点读数，资源采用本站覆盖或模板地址。"""

    id: str = Field(description="场景版本ID，字符串，不是站点ID")
    site_id: str = Field(description="唯一所属授权站点ID")
    template_id: str = Field(description="所用模板版本ID")
    version: int = Field(description="站点场景版本号")
    status: str = Field(description="DRAFT草稿、PUBLISHED当前、ARCHIVED历史")
    is_demo: bool = Field(description="是否模拟场景，不等于实时数据")
    published_at: datetime | None = Field(description="发布时间，UTC带时区；草稿为空")
    model_url: str | None = Field(description="整场景GLB路径，为空时不能展示模型")


class SceneDeviceOut(ApiModel):
    """模型对象所指向的数据库设备身份，不以模型名称猜测设备。"""

    id: str = Field(description="设备ID，传入monitoring查询")
    code: str = Field(description="站内设备业务编码")
    name: str = Field(description="设备名称")
    system_type: str = Field(description="PV/ESS/CHARGING/GRID/LOAD/AUX")
    asset_status: str = Field(description="资产生命周期，不等于在线状态")
    is_demo: bool = Field(description="模拟设备标志")


class ObjectOut(ApiModel):
    """GLB对象身份；objectKey用于匹配实际节点，device为空代表装饰/分组对象。"""

    id: str = Field(description="场景对象ID，字符串；各版本对象ID独立")
    parent_id: str | None = Field(description="同场景父对象ID，可空")
    object_key: str = Field(description="GLB精确节点名或完整下划线前缀；最长匹配优先")
    name: str = Field(description="对象显示名称")
    device_id: str | None = Field(description="设备ID，装饰对象为空")
    device: SceneDeviceOut | None = Field(description="对应设备；非在线监测结果")
    area_id: str | None = Field(description="站内区域ID，可空")
    transform: JsonValue | None = Field(description="原资源变换说明；本版保留GLB内置变换")
    is_demo: bool = Field(description="模拟对象标志")


class BindingOut(ApiModel):
    """某对象属性→同设备测点；属性编码和测点编码可以不同。"""

    id: str = Field(description="绑定ID")
    object_id: str = Field(description="当前场景对象ID")
    device_id: str = Field(description="对象与测点共同所属设备ID")
    point_id: str = Field(description="测点ID，历史查询使用")
    property_code: str = Field(description="对象内展示属性编码")
    mapping_config: JsonValue | None = Field(description="只读展示元数据，不执行脚本")
    point_code: str = Field(description="测点实际业务编码")
    point_name: str = Field(description="测点显示名称")
    unit: str = Field(description="数据库测点单位，不用映射伪造单位")
    enabled: bool = Field(description="测点是否启用")


class SceneOut(SceneSummary):
    """完整场景、数据库对象和测点绑定；读数通过monitoring独立获取。"""

    objects: list[ObjectOut] = Field(description="本站本版本对象，不混用其他版本")
    bindings: list[BindingOut] = Field(description="本站本版本绑定，与测点同设备")
