"""system模块的数据库映射，字段沿用已确认SQL。

仅自动化测试创建临时表；应用启动不迁移MySQL。字段注释说明身份、状态及UTC时间。"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.modules.assets.models import ID_TYPE


class Role(TimestampMixin, Base):
    """sys_role表：字段含义见各列注释；外键保证跨表归属一致。"""

    __tablename__ = "sys_role"
    __table_args__ = (UniqueConstraint("code", name="uk_sys_role_1"),)
    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True, nullable=False)
    # 角色编码
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    # 角色名称
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 角色说明
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Permission(TimestampMixin, Base):
    """sys_permission表：字段含义见各列注释；外键保证跨表归属一致。"""

    __tablename__ = "sys_permission"
    __table_args__ = (UniqueConstraint("code", name="uk_sys_permission_1"),)
    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True, nullable=False)
    # 例如 site:read/device:control
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    # 权限名称
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class RolePermission(TimestampMixin, Base):
    """role_permission表：字段含义见各列注释；外键保证跨表归属一致。"""

    __tablename__ = "role_permission"
    __table_args__ = (
        ForeignKeyConstraint(["role_id"], ["sys_role.id"], name="fk_role_permission_1"),
        ForeignKeyConstraint(["permission_id"], ["sys_permission.id"], name="fk_role_permission_2"),
    )
    # 角色
    role_id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, nullable=False)
    # 权限
    permission_id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, nullable=False)


class User(TimestampMixin, Base):
    """sys_user表：字段含义见各列注释；外键保证跨表归属一致。"""

    __tablename__ = "sys_user"
    __table_args__ = (
        UniqueConstraint("username", name="uk_sys_user_1"),
        ForeignKeyConstraint(["role_id"], ["sys_role.id"], name="fk_sys_user_1"),
    )
    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True, nullable=False)
    # 登录账号
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    # 用户明确要求的本机学习模式：明文网页登录密码；不通过用户查询API返回。
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    # 显示名称
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # ACTIVE有效/LOCKED锁定/INACTIVE停用
    status: Mapped[str] = mapped_column(String(16), server_default=text("'ACTIVE'"), nullable=False)
    # 首期每用户一个角色
    role_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)


class UserSiteScope(TimestampMixin, Base):
    """user_site_scope表：字段含义见各列注释；外键保证跨表归属一致。"""

    __tablename__ = "user_site_scope"
    __table_args__ = (
        ForeignKeyConstraint(["user_id"], ["sys_user.id"], name="fk_user_site_scope_1"),
        ForeignKeyConstraint(["site_id"], ["site.id"], name="fk_user_site_scope_2"),
    )
    # 用户
    user_id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, nullable=False)
    # 授权站点
    site_id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, nullable=False)


class AuditLog(Base):
    """audit_log表：字段含义见各列注释；外键保证跨表归属一致。"""

    __tablename__ = "audit_log"
    __table_args__ = (
        UniqueConstraint("site_id", "id", name="uk_audit_log_1"),
        ForeignKeyConstraint(["actor_id"], ["sys_user.id"], name="fk_audit_log_1"),
        ForeignKeyConstraint(["site_id"], ["site.id"], name="fk_audit_log_2"),
    )
    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True, nullable=False)
    # 操作用户，系统操作可空
    actor_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    # 站点，全局操作可空
    site_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    # 动作编码
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    # 目标实体类型
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # 目标编号文本，审计描述非外键
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 请求追踪编号
    request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # 发生时间UTC
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 变更前脱敏快照
    before_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    # 变更后脱敏快照
    after_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
