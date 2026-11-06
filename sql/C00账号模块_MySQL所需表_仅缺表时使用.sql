-- C00可选：仅在活动表缺失时使用；已有19张表无需执行。
-- IF NOT EXISTS不会改造已有旧表，结构不符需人工核对，不删库/表。
-- DDL隐式提交，不能保证整份建表原子回滚。目标MySQL8.0.16+/8.4，非MariaDB。
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
