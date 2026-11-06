"""公共响应协议：camelCase字段、数据来源说明和分页结构。

Page[T]表示元素为T的分页数组，Result[T]表示普通结果；这些是API模型，不是数据库表。"""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class ApiModel(BaseModel):
    """接口模型基类：Python内部snake_case，对外JSON与OpenAPI使用camelCase。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SourceMeta(ApiModel):
    """数据来源：正式运行mysql；test只用于自动化测试注入，不是可启动的应用模式。"""

    data_source: Literal["test", "mysql"] = Field(
        description="mysql已有数据库；test仅自动化测试注入；isDemo另行说明记录是否为样例"
    )
    notice: str = Field(description="数据来源、演示边界和本模块能力限制")


class PageMeta(SourceMeta):
    """分页信息：total是筛选后的总数，page从1开始，page_size为每页容量，has_next表示还有下一页。"""

    total: int = Field(description="应用全部筛选条件后的总记录数，不是当前页条数")
    page: int = Field(description="当前页码，从1开始")
    page_size: int = Field(description="每页容量，当前查询允许1—100")
    has_next: bool = Field(description="是否还有下一页；越界空页仍保留total")


class Result(ApiModel, Generic[T]):
    """普通成功响应：data为业务结果T，meta说明数据来源。"""

    data: T = Field(description="单项业务对象或非分页数组，具体类型由当前接口决定")
    meta: SourceMeta = Field(description="当前结果的数据来源及必要说明")


class Page(ApiModel, Generic[T]):
    """分页成功响应：data为当前页T数组，meta含来源和分页；越界页可以为空，但保留总数。"""

    data: list[T] = Field(description="当前页业务记录，无匹配或越界时为空数组")
    meta: PageMeta = Field(description="来源及分页信息，包含筛选总数、页码与是否有下一页")
