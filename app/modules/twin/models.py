"""twin模块的数据库映射，字段沿用已确认SQL。

正式运行只连接已有MySQL；隔离测试才创建表。字段注释说明身份、单位、状态及UTC时间。"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Computed,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.modules.assets.models import ID_TYPE


class SceneTemplate(TimestampMixin, Base):
    """scene_template表：字段含义见各列注释；外键保证跨表归属一致。"""

    __tablename__ = "scene_template"
    __table_args__ = (
        UniqueConstraint("template_code", "version_no", name="uk_scene_template_1"),
        UniqueConstraint("id", "site_type", name="uk_scene_template_2"),
    )
    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True, nullable=False)
    # TOLL_S/TOLL_M/TOLL_L/SERVICE_S/SERVICE_M/SERVICE_L
    template_code: Mapped[str] = mapped_column(String(64), nullable=False)
    # 模板名称
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # TOLL/SERVICE
    site_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # S/M/L
    scale_level: Mapped[str] = mapped_column(String(1), nullable=False)
    # 模板版本
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # DRAFT/PUBLISHED/ARCHIVED
    status: Mapped[str] = mapped_column(String(16), server_default=text("'DRAFT'"), nullable=False)
    # 模板场景GLB/glTF地址，草稿可空
    model_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # 模板布局和组件引用
    layout_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    # 组件来源/版本/SHA256/许可证清单
    resource_manifest_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class TwinScene(TimestampMixin, Base):
    """twin_scene表：字段含义见各列注释；外键保证跨表归属一致。"""

    __tablename__ = "twin_scene"
    __table_args__ = (
        UniqueConstraint("site_id", "version_no", name="uk_twin_scene_1"),
        UniqueConstraint("site_id", "current_slot", name="uk_twin_scene_2"),
        UniqueConstraint("site_id", "id", name="uk_twin_scene_3"),
        ForeignKeyConstraint(
            ["site_id", "site_type"], ["site.id", "site.site_type"], name="fk_twin_scene_1"
        ),
        ForeignKeyConstraint(
            ["template_id", "site_type"],
            ["scene_template.id", "scene_template.site_type"],
            name="fk_twin_scene_2",
        ),
    )
    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True, nullable=False)
    # 真实站点
    site_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    # 冗余站型，约束模板与站点匹配
    site_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # 所用模板版本
    template_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    # 站点场景版本
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # DRAFT/PUBLISHED/ARCHIVED
    status: Mapped[str] = mapped_column(String(16), server_default=text("'DRAFT'"), nullable=False)
    # 演示场景标志
    is_demo: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    # 发布时间UTC
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 同站仅一个当前发布场景
    current_slot: Mapped[int | None] = mapped_column(
        Integer,
        Computed("CASE WHEN status = 'PUBLISHED' THEN 1 ELSE NULL END", persisted=True),
        nullable=True,
    )
    # 本站模型文件覆盖地址，为空采用模板文件
    model_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class TwinObject(TimestampMixin, Base):
    """twin_object表：字段含义见各列注释；外键保证跨表归属一致。"""

    __tablename__ = "twin_object"
    __table_args__ = (
        UniqueConstraint("scene_id", "object_key", name="uk_twin_object_1"),
        UniqueConstraint("site_id", "scene_id", "id", name="uk_twin_object_2"),
        UniqueConstraint("site_id", "device_id", "id", name="uk_twin_object_3"),
        UniqueConstraint("site_id", "id", name="uk_twin_object_4"),
        ForeignKeyConstraint(
            ["site_id", "scene_id"],
            ["twin_scene.site_id", "twin_scene.id"],
            name="fk_twin_object_1",
        ),
        ForeignKeyConstraint(
            ["site_id", "scene_id", "parent_id"],
            ["twin_object.site_id", "twin_object.scene_id", "twin_object.id"],
            name="fk_twin_object_2",
        ),
        ForeignKeyConstraint(
            ["site_id", "device_id"], ["device.site_id", "device.id"], name="fk_twin_object_3"
        ),
        ForeignKeyConstraint(
            ["site_id", "area_id"], ["site_area.site_id", "site_area.id"], name="fk_twin_object_4"
        ),
    )
    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True, nullable=False)
    # 站点
    site_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    # 场景版本
    scene_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    # 同场景父对象
    parent_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    # 稳定对象键，对应模型可选中对象
    object_key: Mapped[str] = mapped_column(String(100), nullable=False)
    # 对象显示名称
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 真实设备，装饰/分组对象可空
    device_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    # 空间区域
    area_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    # 位置xyz米/旋转xyz弧度/缩放xyz
    transform_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    # 对象模拟标志
    is_demo: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    # 独立对象模型地址，为空则在场景文件中按object_key查找
    model_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class TwinBinding(TimestampMixin, Base):
    """twin_binding表：字段含义见各列注释；外键保证跨表归属一致。"""

    __tablename__ = "twin_binding"
    __table_args__ = (
        UniqueConstraint("object_id", "property_code", name="uk_twin_binding_1"),
        UniqueConstraint("site_id", "id", name="uk_twin_binding_2"),
        ForeignKeyConstraint(
            ["site_id", "device_id", "object_id"],
            ["twin_object.site_id", "twin_object.device_id", "twin_object.id"],
            name="fk_twin_binding_1",
        ),
        ForeignKeyConstraint(
            ["site_id", "device_id", "point_id"],
            ["device_point.site_id", "device_point.device_id", "device_point.id"],
            name="fk_twin_binding_2",
        ),
    )
    # 内部主键
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True, nullable=False)
    # 站点
    site_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    # 设备，确保对象与测点属于同设备
    device_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    # 设备三维对象
    object_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    # 数据测点
    point_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    # 标签/颜色/动画等属性
    property_code: Mapped[str] = mapped_column(String(64), nullable=False)
    # 显示阈值、单位及转换配置
    mapping_config_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
