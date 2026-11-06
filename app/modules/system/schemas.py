"""账号与权限的数据协议；密码只作为输入，不出现在用户、审计或登录响应中。"""

from dataclasses import dataclass
from typing import Literal

from pydantic import ConfigDict, Field, SecretStr

from app.common.access import IdValue
from app.common.pagination import ApiModel


@dataclass(frozen=True)
class Principal:
    """每次请求从数据库重查的身份；权限码和站点范围不是只信任JWT中的旧快照。"""

    user_id: int
    username: str
    role_code: str
    permissions: frozenset[str]
    site_ids: frozenset[int]


class SystemInput(ApiModel):
    """拒绝未知字段，避免将拼错的授权参数静默丢弃。"""

    model_config = ConfigDict(extra="forbid")


class LoginIn(SystemInput):
    """JSON登录输入；演示账号见测试文档，不能用于真实部署。"""

    username: str = Field(min_length=1, max_length=64, description="登录账号")
    password: SecretStr = Field(
        min_length=1, max_length=128, description="密码，只在本地或受保护连接中提交"
    )


class UserCreate(SystemInput):
    """管理员创建账号；角色和站点必须存在，按用户要求明文保存密码但不返回。"""

    username: str = Field(
        pattern=r"^[A-Za-z0-9_.-]{3,64}$", description="唯一账号，3—64位字母数字及_.-"
    )
    display_name: str = Field(min_length=1, max_length=100, description="显示名称")
    password: SecretStr = Field(min_length=10, max_length=128, description="初始密码，至少10字符")
    role_id: IdValue
    site_ids: list[IdValue] = Field(
        max_length=1000, description="授予的站点ID，可为空；只能授予自己拥有的范围"
    )


class ScopeIn(SystemInput):
    """完整替换用户站点范围；空数组表示不授权任何站点，不是全部站点。"""

    site_ids: list[IdValue] = Field(max_length=1000, description="新的站点ID全集")


class UserStatusIn(SystemInput):
    """锁定或停用会使已有令牌下一次请求立即失效；当前不能锁定自身。"""

    status: Literal["ACTIVE", "LOCKED", "INACTIVE"] = Field(description="账号有效、锁定或停用")
