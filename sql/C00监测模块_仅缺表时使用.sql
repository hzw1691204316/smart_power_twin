-- 电力监测所需3表；依赖已有site/device。仅缺表时执行，不修改旧表、不导入数据。
USE smart_power_twin;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;
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

