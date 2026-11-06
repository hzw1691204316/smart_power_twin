-- 告警模块仅补缺表；已有全模块19表则不需执行。不迁移已有字段、不导入数据。
USE smart_power_twin;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;
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
