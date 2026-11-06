-- 三维场景所需4表；依赖已有台账、监测表。仅缺表时执行，不修改已有表、不插入数据。
USE smart_power_twin;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;
CREATE TABLE IF NOT EXISTS `scene_template` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `template_code` VARCHAR(64) NOT NULL COMMENT 'TOLL_S/TOLL_M/TOLL_L/SERVICE_S/SERVICE_M/SERVICE_L',
  `name` VARCHAR(100) NOT NULL COMMENT '模板名称',
  `site_type` VARCHAR(16) NOT NULL COMMENT 'TOLL/SERVICE',
  `scale_level` CHAR(1) NOT NULL COMMENT 'S/M/L',
  `version_no` INT UNSIGNED NOT NULL COMMENT '模板版本',
  `status` VARCHAR(16) NOT NULL DEFAULT 'DRAFT' COMMENT 'DRAFT/PUBLISHED/ARCHIVED',
  `model_uri` VARCHAR(1000) NULL COMMENT '模板场景GLB/glTF地址，草稿可空',
  `layout_json` JSON NULL COMMENT '模板布局和组件引用',
  `resource_manifest_json` JSON NULL COMMENT '组件来源/版本/SHA256/许可证清单',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_scene_template_1` (`template_code`, `version_no`),
  UNIQUE KEY `uk_scene_template_2` (`id`, `site_type`),
  CONSTRAINT `ck_scene_template_1` CHECK (site_type IN ('TOLL','SERVICE')),
  CONSTRAINT `ck_scene_template_2` CHECK (scale_level IN ('S','M','L')),
  CONSTRAINT `ck_scene_template_3` CHECK (version_no > 0),
  CONSTRAINT `ck_scene_template_4` CHECK (status IN ('DRAFT','PUBLISHED','ARCHIVED')),
  CONSTRAINT `ck_scene_template_5` CHECK (template_code = CONCAT(site_type,'_',scale_level))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='三维 六类模板定义及资源地址';

CREATE TABLE IF NOT EXISTS `twin_scene` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `site_id` BIGINT UNSIGNED NOT NULL COMMENT '真实站点',
  `site_type` VARCHAR(16) NOT NULL COMMENT '冗余站型，约束模板与站点匹配',
  `template_id` BIGINT UNSIGNED NOT NULL COMMENT '所用模板版本',
  `version_no` INT UNSIGNED NOT NULL COMMENT '站点场景版本',
  `status` VARCHAR(16) NOT NULL DEFAULT 'DRAFT' COMMENT 'DRAFT/PUBLISHED/ARCHIVED',
  `is_demo` TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '演示场景标志',
  `published_at` DATETIME(3) NULL COMMENT '发布时间UTC',
  `current_slot` TINYINT GENERATED ALWAYS AS (CASE WHEN status = 'PUBLISHED' THEN 1 ELSE NULL END) STORED COMMENT '同站仅一个当前发布场景',
  `model_uri` VARCHAR(1000) NULL COMMENT '本站模型文件覆盖地址，为空采用模板文件',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_twin_scene_1` (`site_id`, `version_no`),
  UNIQUE KEY `uk_twin_scene_2` (`site_id`, `current_slot`),
  UNIQUE KEY `uk_twin_scene_3` (`site_id`, `id`),
  CONSTRAINT `fk_twin_scene_1` FOREIGN KEY (`site_id`, `site_type`) REFERENCES `site` (`id`, `site_type`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_twin_scene_2` FOREIGN KEY (`template_id`, `site_type`) REFERENCES `scene_template` (`id`, `site_type`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_twin_scene_1` CHECK (version_no > 0),
  CONSTRAINT `ck_twin_scene_2` CHECK (status IN ('DRAFT','PUBLISHED','ARCHIVED')),
  CONSTRAINT `ck_twin_scene_3` CHECK (is_demo IN (0,1)),
  CONSTRAINT `ck_twin_scene_4` CHECK (status <> 'PUBLISHED' OR published_at IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M09 站点三维场景实例版本';

CREATE TABLE IF NOT EXISTS `twin_object` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `site_id` BIGINT UNSIGNED NOT NULL COMMENT '站点',
  `scene_id` BIGINT UNSIGNED NOT NULL COMMENT '场景版本',
  `parent_id` BIGINT UNSIGNED NULL COMMENT '同场景父对象',
  `object_key` VARCHAR(100) NOT NULL COMMENT '稳定对象键，对应模型可选中对象',
  `name` VARCHAR(100) NOT NULL COMMENT '对象显示名称',
  `device_id` BIGINT UNSIGNED NULL COMMENT '真实设备，装饰/分组对象可空',
  `area_id` BIGINT UNSIGNED NULL COMMENT '空间区域',
  `transform_json` JSON NULL COMMENT '位置xyz米/旋转xyz弧度/缩放xyz',
  `is_demo` TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '对象模拟标志',
  `model_uri` VARCHAR(1000) NULL COMMENT '独立对象模型地址，为空则在场景文件中按object_key查找',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_twin_object_1` (`scene_id`, `object_key`),
  UNIQUE KEY `uk_twin_object_2` (`site_id`, `scene_id`, `id`),
  UNIQUE KEY `uk_twin_object_3` (`site_id`, `device_id`, `id`),
  UNIQUE KEY `uk_twin_object_4` (`site_id`, `id`),
  CONSTRAINT `fk_twin_object_1` FOREIGN KEY (`site_id`, `scene_id`) REFERENCES `twin_scene` (`site_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_twin_object_2` FOREIGN KEY (`site_id`, `scene_id`, `parent_id`) REFERENCES `twin_object` (`site_id`, `scene_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_twin_object_3` FOREIGN KEY (`site_id`, `device_id`) REFERENCES `device` (`site_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_twin_object_4` FOREIGN KEY (`site_id`, `area_id`) REFERENCES `site_area` (`site_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_twin_object_1` CHECK (is_demo IN (0,1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M09 场景内可定位对象';

CREATE TABLE IF NOT EXISTS `twin_binding` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `site_id` BIGINT UNSIGNED NOT NULL COMMENT '站点',
  `device_id` BIGINT UNSIGNED NOT NULL COMMENT '设备，确保对象与测点属于同设备',
  `object_id` BIGINT UNSIGNED NOT NULL COMMENT '设备三维对象',
  `point_id` BIGINT UNSIGNED NOT NULL COMMENT '数据测点',
  `property_code` VARCHAR(64) NOT NULL COMMENT '标签/颜色/动画等属性',
  `mapping_config_json` JSON NULL COMMENT '显示阈值、单位及转换配置',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_twin_binding_1` (`object_id`, `property_code`),
  UNIQUE KEY `uk_twin_binding_2` (`site_id`, `id`),
  CONSTRAINT `fk_twin_binding_1` FOREIGN KEY (`site_id`, `device_id`, `object_id`) REFERENCES `twin_object` (`site_id`, `device_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_twin_binding_2` FOREIGN KEY (`site_id`, `device_id`, `point_id`) REFERENCES `device_point` (`site_id`, `device_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M09 三维属性与真实测点绑定';

