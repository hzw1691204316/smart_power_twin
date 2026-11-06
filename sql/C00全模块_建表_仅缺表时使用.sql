-- 全模块19表；2026-10-16；MySQL8.0.16+/8.4。仅缺表时手动执行。
-- 已有同名表不重建、不迁移，IF NOT EXISTS不能修复旧字段；不用DROP/TRUNCATE/FOREIGN_KEY_CHECKS=0。
-- 不创建数据库、账号或任何演示记录。DDL隐式提交，失败时停止并核对错误。
USE `smart_power_twin`;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;
CREATE TABLE IF NOT EXISTS `sys_role` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `code` VARCHAR(64) NOT NULL COMMENT '角色编码',
  `name` VARCHAR(100) NOT NULL COMMENT '角色名称',
  `description` VARCHAR(500) NULL COMMENT '角色说明',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sys_role_1` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M01 角色';

CREATE TABLE IF NOT EXISTS `sys_permission` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `code` VARCHAR(100) NOT NULL COMMENT '例如 site:read/device:control',
  `name` VARCHAR(100) NOT NULL COMMENT '权限名称',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sys_permission_1` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M01 动作权限';

CREATE TABLE IF NOT EXISTS `role_permission` (
  `role_id` BIGINT UNSIGNED NOT NULL COMMENT '角色',
  `permission_id` BIGINT UNSIGNED NOT NULL COMMENT '权限',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`role_id`, `permission_id`),
  CONSTRAINT `fk_role_permission_1` FOREIGN KEY (`role_id`) REFERENCES `sys_role` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_role_permission_2` FOREIGN KEY (`permission_id`) REFERENCES `sys_permission` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M01 角色与权限关系';

CREATE TABLE IF NOT EXISTS `sys_user` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `username` VARCHAR(64) NOT NULL COMMENT '登录账号',
  `password` VARCHAR(255) NOT NULL COMMENT '网页登录密码，按用户要求明文保存',
  `display_name` VARCHAR(100) NOT NULL COMMENT '显示名称',
  `status` VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' COMMENT 'ACTIVE有效/LOCKED锁定/INACTIVE停用',
  `role_id` BIGINT UNSIGNED NOT NULL COMMENT '首期每用户一个角色',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sys_user_1` (`username`),
  CONSTRAINT `fk_sys_user_1` FOREIGN KEY (`role_id`) REFERENCES `sys_role` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_sys_user_1` CHECK (status IN ('ACTIVE','LOCKED','INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M01 用户';

CREATE TABLE IF NOT EXISTS `highway_route` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `route_code` VARCHAR(32) NOT NULL COMMENT '路线编号，例如G4',
  `name` VARCHAR(150) NOT NULL COMMENT '路线名称',
  `aliases_json` JSON NULL COMMENT '路线别名，检索可后续规范化',
  `status` VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' COMMENT 'ACTIVE/INACTIVE',
  `geometry_uri` VARCHAR(1000) NULL COMMENT '路线GeoJSON等资源地址，前端按省范围展示',
  `coordinate_system` VARCHAR(32) NOT NULL DEFAULT 'WGS84' COMMENT '路线几何坐标系统',
  `source_url` VARCHAR(1000) NULL COMMENT '路线数据来源',
  `license_ref` VARCHAR(1000) NULL COMMENT '地图资源授权依据',
  `data_version` VARCHAR(100) NULL COMMENT '路网资源版本',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_highway_route_1` (`route_code`),
  CONSTRAINT `ck_highway_route_1` CHECK (status IN ('ACTIVE','INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M11 高速路线身份';

CREATE TABLE IF NOT EXISTS `site` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `code` VARCHAR(64) NOT NULL COMMENT '唯一站点业务编码',
  `name` VARCHAR(150) NOT NULL COMMENT '真实站点名称',
  `site_type` VARCHAR(16) NOT NULL COMMENT 'TOLL收费站/SERVICE服务区',
  `scale_level` CHAR(1) NOT NULL COMMENT 'S小/M中/L大，业务展示分级',
  `complex_code` VARCHAR(64) NULL COMMENT '独立上下行站点的共同分组码',
  `longitude` DECIMAL(11,7) NULL COMMENT '经度',
  `latitude` DECIMAL(10,7) NULL COMMENT '纬度',
  `coordinate_system` VARCHAR(32) NOT NULL DEFAULT 'WGS84' COMMENT '坐标系统，按实际数据修改',
  `location_source` VARCHAR(500) NULL COMMENT '坐标来源',
  `location_verified_at` DATETIME(3) NULL COMMENT '坐标核验时间UTC',
  `timezone` VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai' COMMENT '业务时区',
  `is_demo` TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '1为演示站点',
  `status` VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' COMMENT 'ACTIVE/INACTIVE/RETIRED',
  `management_name` VARCHAR(150) NULL COMMENT '管理单位名称，首期不建组织树',
  `province_code` VARCHAR(16) NOT NULL COMMENT '省级编码，例如41；编码规范由应用统一',
  `city_name` VARCHAR(100) NULL COMMENT '地市名称',
  `aliases_json` JSON NULL COMMENT '站点简称/别名字符串数组',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_site_1` (`code`),
  UNIQUE KEY `uk_site_2` (`id`, `site_type`),
  KEY `ix_site_1` (`province_code`, `site_type`),
  KEY `ix_site_2` (`name`),
  KEY `ix_site_3` (`complex_code`),
  CONSTRAINT `ck_site_1` CHECK (site_type IN ('TOLL','SERVICE')),
  CONSTRAINT `ck_site_2` CHECK (scale_level IN ('S','M','L')),
  CONSTRAINT `ck_site_3` CHECK (longitude BETWEEN -180 AND 180),
  CONSTRAINT `ck_site_4` CHECK (latitude BETWEEN -90 AND 90),
  CONSTRAINT `ck_site_5` CHECK ((longitude IS NULL) = (latitude IS NULL)),
  CONSTRAINT `ck_site_6` CHECK (is_demo IN (0,1)),
  CONSTRAINT `ck_site_7` CHECK (status IN ('ACTIVE','INACTIVE','RETIRED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M02 收费站或服务区';

CREATE TABLE IF NOT EXISTS `user_site_scope` (
  `user_id` BIGINT UNSIGNED NOT NULL COMMENT '用户',
  `site_id` BIGINT UNSIGNED NOT NULL COMMENT '授权站点',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`user_id`, `site_id`),
  CONSTRAINT `fk_user_site_scope_1` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_user_site_scope_2` FOREIGN KEY (`site_id`) REFERENCES `site` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M01 用户可访问站点';

CREATE TABLE IF NOT EXISTS `site_area` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `site_id` BIGINT UNSIGNED NOT NULL COMMENT '站点',
  `parent_id` BIGINT UNSIGNED NULL COMMENT '上级区域，须同站',
  `code` VARCHAR(64) NOT NULL COMMENT '站内区域编码',
  `area_type` VARCHAR(32) NOT NULL COMMENT 'DIRECTION/BUILDING/PARKING/POWER_ROOM等',
  `name` VARCHAR(150) NOT NULL COMMENT '区域名称',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_site_area_1` (`site_id`, `code`),
  UNIQUE KEY `uk_site_area_2` (`site_id`, `id`),
  CONSTRAINT `fk_site_area_1` FOREIGN KEY (`site_id`) REFERENCES `site` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_site_area_2` FOREIGN KEY (`site_id`, `parent_id`) REFERENCES `site_area` (`site_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M02 站内空间区域';

CREATE TABLE IF NOT EXISTS `site_route_link` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `site_id` BIGINT UNSIGNED NOT NULL COMMENT '站点',
  `area_id` BIGINT UNSIGNED NULL COMMENT '具体上下行区域',
  `route_id` BIGINT UNSIGNED NOT NULL COMMENT '高速路线',
  `link_code` VARCHAR(64) NOT NULL COMMENT '站内关联编码',
  `direction_code` VARCHAR(24) NOT NULL DEFAULT 'BOTH' COMMENT 'UP/DOWN/BOTH/UNKNOWN',
  `direction_label` VARCHAR(100) NULL COMMENT '例如往郑州方向',
  `chainage_m` DECIMAL(12,3) NULL COMMENT '该路线该方向里程桩号，单位米',
  `access_type` VARCHAR(24) NOT NULL DEFAULT 'DIRECT' COMMENT 'DIRECT/INTERCHANGE/OTHER',
  `is_primary` TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '主路线标志，唯一性由服务校验',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_site_route_link_1` (`site_id`, `link_code`),
  UNIQUE KEY `uk_site_route_link_2` (`site_id`, `id`),
  KEY `ix_site_route_link_1` (`route_id`, `site_id`),
  CONSTRAINT `fk_site_route_link_1` FOREIGN KEY (`site_id`) REFERENCES `site` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_site_route_link_2` FOREIGN KEY (`site_id`, `area_id`) REFERENCES `site_area` (`site_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_site_route_link_3` FOREIGN KEY (`route_id`) REFERENCES `highway_route` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_site_route_link_1` CHECK (direction_code IN ('UP','DOWN','BOTH','UNKNOWN')),
  CONSTRAINT `ck_site_route_link_2` CHECK (chainage_m >= 0),
  CONSTRAINT `ck_site_route_link_3` CHECK (is_primary IN (0,1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M11 站点路线方向关联';

CREATE TABLE IF NOT EXISTS `device` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `site_id` BIGINT UNSIGNED NOT NULL COMMENT '唯一所属站点',
  `area_id` BIGINT UNSIGNED NULL COMMENT '物理安装区域',
  `parent_device_id` BIGINT UNSIGNED NULL COMMENT '组成关系中的父设备',
  `code` VARCHAR(64) NOT NULL COMMENT '站内设备编码',
  `name` VARCHAR(150) NOT NULL COMMENT '设备名称',
  `device_type` VARCHAR(32) NOT NULL COMMENT '设备类型，须与型号一致',
  `rated_power_kw` DECIMAL(14,4) NULL COMMENT '额定功率kW',
  `rated_energy_kwh` DECIMAL(14,4) NULL COMMENT '额定储能电量kWh',
  `rated_capacity_kva` DECIMAL(14,4) NULL COMMENT '额定视在容量kVA',
  `is_demo` TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '演示设备标志',
  `status` VARCHAR(24) NOT NULL DEFAULT 'ACTIVE' COMMENT 'ACTIVE/MAINTENANCE/INACTIVE/RETIRED',
  `system_type` VARCHAR(24) NOT NULL DEFAULT 'AUX' COMMENT 'PV/ESS/CHARGING/GRID/LOAD/AUX',
  `manufacturer` VARCHAR(100) NULL COMMENT '设备厂家',
  `model_code` VARCHAR(100) NULL COMMENT '厂家型号',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_device_1` (`site_id`, `code`),
  UNIQUE KEY `uk_device_2` (`site_id`, `id`),
  KEY `ix_device_1` (`site_id`, `device_type`),
  CONSTRAINT `fk_device_1` FOREIGN KEY (`site_id`) REFERENCES `site` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_device_2` FOREIGN KEY (`site_id`, `area_id`) REFERENCES `site_area` (`site_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_device_3` FOREIGN KEY (`site_id`, `parent_device_id`) REFERENCES `device` (`site_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_device_1` CHECK (rated_power_kw > 0),
  CONSTRAINT `ck_device_2` CHECK (rated_energy_kwh > 0),
  CONSTRAINT `ck_device_3` CHECK (rated_capacity_kva > 0),
  CONSTRAINT `ck_device_4` CHECK (is_demo IN (0,1)),
  CONSTRAINT `ck_device_5` CHECK (status IN ('ACTIVE','MAINTENANCE','INACTIVE','RETIRED')),
  CONSTRAINT `ck_device_6` CHECK (system_type IN ('PV','ESS','CHARGING','GRID','LOAD','AUX'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M02 实体设备台账';

CREATE TABLE IF NOT EXISTS `device_point` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `site_id` BIGINT UNSIGNED NOT NULL COMMENT '站点',
  `device_id` BIGINT UNSIGNED NOT NULL COMMENT '所属设备',
  `code` VARCHAR(64) NOT NULL COMMENT '设备内测点编码',
  `name` VARCHAR(100) NOT NULL COMMENT '测点名称',
  `sample_interval_ms` INT UNSIGNED NOT NULL DEFAULT 5000 COMMENT '建议采样周期毫秒',
  `stale_after_ms` INT UNSIGNED NOT NULL DEFAULT 15000 COMMENT '数据陈旧阈值毫秒',
  `enabled` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '启用标志',
  `unit` VARCHAR(32) NOT NULL COMMENT 'kW/kWh/%/BOOL等',
  `value_type` VARCHAR(16) NOT NULL DEFAULT 'NUMERIC' COMMENT 'NUMERIC/TEXT/BOOLEAN',
  `aggregation_type` VARCHAR(24) NOT NULL DEFAULT 'INSTANT' COMMENT 'INSTANT瞬时/COUNTER累计/STATE状态',
  `direction_convention` VARCHAR(300) NULL COMMENT '正负方向约定',
  `alarm_low` DOUBLE NULL COMMENT '简单低阈值，可空',
  `alarm_high` DOUBLE NULL COMMENT '简单高阈值，可空',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_device_point_1` (`device_id`, `code`),
  UNIQUE KEY `uk_device_point_2` (`site_id`, `device_id`, `id`),
  UNIQUE KEY `uk_device_point_3` (`site_id`, `id`),
  CONSTRAINT `fk_device_point_1` FOREIGN KEY (`site_id`, `device_id`) REFERENCES `device` (`site_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_device_point_1` CHECK (sample_interval_ms > 0),
  CONSTRAINT `ck_device_point_2` CHECK (stale_after_ms >= sample_interval_ms),
  CONSTRAINT `ck_device_point_3` CHECK (enabled IN (0,1)),
  CONSTRAINT `ck_device_point_4` CHECK (value_type IN ('NUMERIC','TEXT','BOOLEAN')),
  CONSTRAINT `ck_device_point_5` CHECK (aggregation_type IN ('INSTANT','COUNTER','STATE')),
  CONSTRAINT `ck_device_point_6` CHECK (alarm_low IS NULL OR alarm_high IS NULL OR alarm_low < alarm_high)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='监测 测点及指标属性，合并标准指标字典';

CREATE TABLE IF NOT EXISTS `point_latest` (
  `point_id` BIGINT UNSIGNED NOT NULL COMMENT '测点',
  `source_time` DATETIME(3) NOT NULL COMMENT '源采样时间UTC',
  `received_time` DATETIME(3) NOT NULL COMMENT '平台接收时间UTC',
  `value_numeric` DOUBLE NULL COMMENT '数值/布尔值',
  `value_text` VARCHAR(500) NULL COMMENT '文本值',
  `quality` VARCHAR(16) NOT NULL COMMENT 'GOOD/SUSPECT/BAD/MANUAL/ESTIMATED',
  `source_sequence` BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '去重及同时间排序序号',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`point_id`),
  CONSTRAINT `fk_point_latest_1` FOREIGN KEY (`point_id`) REFERENCES `device_point` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_point_latest_1` CHECK (quality IN ('GOOD','SUSPECT','BAD','MANUAL','ESTIMATED')),
  CONSTRAINT `ck_point_latest_2` CHECK (value_numeric IS NULL OR value_text IS NULL),
  CONSTRAINT `ck_point_latest_3` CHECK (quality = 'BAD' OR value_numeric IS NOT NULL OR value_text IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M05 每测点一条最新值，可选持久化投影';

CREATE TABLE IF NOT EXISTS `point_history` (
  `point_id` BIGINT UNSIGNED NOT NULL COMMENT '测点',
  `sampled_at` DATETIME(3) NOT NULL COMMENT '采样时间UTC',
  `source_sequence` BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '源序号，重传保持相同值',
  `received_at` DATETIME(3) NOT NULL COMMENT '接收时间UTC',
  `value_numeric` DOUBLE NULL COMMENT '数值',
  `value_text` VARCHAR(500) NULL COMMENT '文本值',
  `quality` VARCHAR(16) NOT NULL COMMENT 'GOOD/SUSPECT/BAD/MANUAL/ESTIMATED',
  PRIMARY KEY (`point_id`, `sampled_at`, `source_sequence`),
  KEY `ix_point_history_1` (`sampled_at`),
  CONSTRAINT `fk_point_history_1` FOREIGN KEY (`point_id`) REFERENCES `device_point` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_point_history_1` CHECK (quality IN ('GOOD','SUSPECT','BAD','MANUAL','ESTIMATED')),
  CONSTRAINT `ck_point_history_2` CHECK (value_numeric IS NULL OR value_text IS NULL),
  CONSTRAINT `ck_point_history_3` CHECK (quality = 'BAD' OR value_numeric IS NOT NULL OR value_text IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M05 小规模原型历史采样，非大规模时序库替代';

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

CREATE TABLE IF NOT EXISTS `alarm_event` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `site_id` BIGINT UNSIGNED NOT NULL COMMENT '站点',
  `device_id` BIGINT UNSIGNED NULL COMMENT '设备，站级告警可空',
  `point_id` BIGINT UNSIGNED NULL COMMENT '测点，可空',
  `event_key` VARCHAR(128) NOT NULL COMMENT '发生事件去重键，非规则编码',
  `raised_at` DATETIME(3) NOT NULL COMMENT '发生时间UTC',
  `recovered_at` DATETIME(3) NULL COMMENT '恢复时间UTC',
  `acknowledged_at` DATETIME(3) NULL COMMENT '确认时间UTC',
  `status` VARCHAR(24) NOT NULL DEFAULT 'ACTIVE' COMMENT 'ACTIVE/RECOVERED/CLOSED，确认独立记录',
  `message` VARCHAR(1000) NOT NULL COMMENT '发生时描述快照',
  `severity` VARCHAR(16) NOT NULL DEFAULT 'MINOR' COMMENT 'INFO/MINOR/MAJOR/CRITICAL',
  `trigger_snapshot_json` JSON NULL COMMENT '发生时阈值与观测值快照，保留历史解释',
  `acknowledged_by` BIGINT UNSIGNED NULL COMMENT '确认用户',
  `handling_note` VARCHAR(1000) NULL COMMENT '首期简要处理说明',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间，UTC',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间，UTC',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_alarm_event_1` (`site_id`, `event_key`),
  UNIQUE KEY `uk_alarm_event_2` (`site_id`, `id`),
  KEY `ix_alarm_event_1` (`site_id`, `status`, `raised_at`),
  CONSTRAINT `fk_alarm_event_1` FOREIGN KEY (`site_id`, `device_id`) REFERENCES `device` (`site_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_alarm_event_2` FOREIGN KEY (`site_id`, `device_id`, `point_id`) REFERENCES `device_point` (`site_id`, `device_id`, `id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_alarm_event_3` FOREIGN KEY (`acknowledged_by`) REFERENCES `sys_user` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_alarm_event_1` CHECK (point_id IS NULL OR device_id IS NOT NULL),
  CONSTRAINT `ck_alarm_event_2` CHECK (recovered_at IS NULL OR recovered_at >= raised_at),
  CONSTRAINT `ck_alarm_event_3` CHECK (acknowledged_at IS NULL OR acknowledged_at >= raised_at),
  CONSTRAINT `ck_alarm_event_4` CHECK (status IN ('ACTIVE','RECOVERED','CLOSED')),
  CONSTRAINT `ck_alarm_event_5` CHECK (status = 'ACTIVE' OR recovered_at IS NOT NULL),
  CONSTRAINT `ck_alarm_event_6` CHECK (severity IN ('INFO','MINOR','MAJOR','CRITICAL'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='告警 告警发生/确认/恢复，合并简单规则及处置';

CREATE TABLE IF NOT EXISTS `audit_log` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `actor_id` BIGINT UNSIGNED NULL COMMENT '操作用户，系统操作可空',
  `site_id` BIGINT UNSIGNED NULL COMMENT '站点，全局操作可空',
  `action` VARCHAR(100) NOT NULL COMMENT '动作编码',
  `target_type` VARCHAR(64) NOT NULL COMMENT '目标实体类型',
  `target_id` VARCHAR(100) NULL COMMENT '目标编号文本，审计描述非外键',
  `request_id` VARCHAR(100) NOT NULL COMMENT '请求追踪编号',
  `occurred_at` DATETIME(3) NOT NULL COMMENT '发生时间UTC',
  `before_json` JSON NULL COMMENT '变更前脱敏快照',
  `after_json` JSON NULL COMMENT '变更后脱敏快照',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_audit_log_1` (`site_id`, `id`),
  KEY `ix_audit_log_1` (`site_id`, `occurred_at`),
  KEY `ix_audit_log_2` (`request_id`),
  CONSTRAINT `fk_audit_log_1` FOREIGN KEY (`actor_id`) REFERENCES `sys_user` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_audit_log_2` FOREIGN KEY (`site_id`) REFERENCES `site` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs COMMENT='M01 操作审计，追加记录';
