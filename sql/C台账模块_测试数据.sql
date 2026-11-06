-- C台账模块_测试数据.sql（2026-10-15）
-- 目标库smart_power_twin；适用MySQL8.0/8.4。请在SQL客户端按整个脚本执行，支持DELIMITER。
-- 仅补齐：2站点、6区域、8设备、1路线、2路线关联。全部设备/区域为虚构测试台账。
-- 参考坐标及S26关联待核验，不代表现场测绘；额定参数不是实时电力读数。
-- 不建表，不改账号/密码/角色/授权，不注册监测/告警等未启用模块。
-- 仅插入缺失业务编码，不覆盖、删除已有记录；已有两站八设备时重跑不会增加重复记录。
-- 使用临时辅助存储过程确保发生错误时整批ROLLBACK；需要CREATE ROUTINE/EXECUTE/ALTER ROUTINE权限。
-- 请单独打开连接执行，不与尚未提交的其他SQL编辑混用（MySQL的DDL有隐式提交）。
USE `smart_power_twin`;
SET @c_asset_old_sql_mode = @@SESSION.sql_mode;
SET @c_asset_old_time_zone = @@SESSION.time_zone;
SET SESSION sql_mode = CONCAT_WS(',', NULLIF(@c_asset_old_sql_mode,''), 'NO_BACKSLASH_ESCAPES');
SET SESSION time_zone = '+00:00';

DELIMITER $$
CREATE PROCEDURE `c_spt_seed_assets_test_20261015`()
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;
  IF (SELECT COUNT(*) FROM information_schema.tables
      WHERE table_schema=DATABASE() AND table_name IN ('site','site_area','device','highway_route','site_route_link') AND engine='InnoDB') <> 5 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='MISSING_ASSET_TABLE_OR_NOT_INNODB';
  END IF;
  START TRANSACTION;
  IF EXISTS (SELECT 1 FROM site WHERE code='HEBI_CHAOGE_SERVICE_DEMO' AND (is_demo<>1 OR site_type<>'SERVICE')) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='EXISTING_SITE_CODE_CONFLICT';
  END IF;
  IF EXISTS (SELECT 1 FROM site WHERE code='HEBI_CHAOGE_TOLL_DEMO' AND (is_demo<>1 OR site_type<>'TOLL')) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='EXISTING_SITE_CODE_CONFLICT';
  END IF;
  IF EXISTS (SELECT 1 FROM device WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='ESS_01' AND is_demo<>1) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='EXISTING_DEVICE_CODE_CONFLICT';
  END IF;
  IF EXISTS (SELECT 1 FROM device WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='TRANSFORMER_01' AND is_demo<>1) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='EXISTING_DEVICE_CODE_CONFLICT';
  END IF;
  IF EXISTS (SELECT 1 FROM device WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='PV_01' AND is_demo<>1) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='EXISTING_DEVICE_CODE_CONFLICT';
  END IF;
  IF EXISTS (SELECT 1 FROM device WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='CHARGER_01' AND is_demo<>1) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='EXISTING_DEVICE_CODE_CONFLICT';
  END IF;
  IF EXISTS (SELECT 1 FROM device WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='ESS_01' AND is_demo<>1) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='EXISTING_DEVICE_CODE_CONFLICT';
  END IF;
  IF EXISTS (SELECT 1 FROM device WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='TRANSFORMER_01' AND is_demo<>1) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='EXISTING_DEVICE_CODE_CONFLICT';
  END IF;
  IF EXISTS (SELECT 1 FROM device WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='PV_01' AND is_demo<>1) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='EXISTING_DEVICE_CODE_CONFLICT';
  END IF;
  IF EXISTS (SELECT 1 FROM device WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='CHARGER_01' AND is_demo<>1) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='EXISTING_DEVICE_CODE_CONFLICT';
  END IF;

  INSERT INTO `highway_route` (`route_code`, `name`, `aliases_json`, `status`, `geometry_uri`, `coordinate_system`, `source_url`, `license_ref`, `data_version`)
    SELECT 'S26', '台辉高速（朝歌站区演示关联）', NULL, 'ACTIVE', NULL, 'WGS84', NULL, NULL, NULL FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `highway_route` WHERE route_code='S26');
  INSERT INTO `site` (`code`, `name`, `site_type`, `scale_level`, `complex_code`, `longitude`, `latitude`, `coordinate_system`, `location_source`, `location_verified_at`, `timezone`, `is_demo`, `status`, `management_name`, `province_code`, `city_name`, `aliases_json`)
    SELECT 'HEBI_CHAOGE_SERVICE_DEMO', '朝歌服务区', 'SERVICE', 'M', 'HEBI_CHAOGE_COMPLEX', 114.2275190, 35.6656470, 'WGS84', '公开参考位置，非实测入口；设备与区域为虚构演示台账，需现场核验', NULL, 'Asia/Shanghai', 1, 'ACTIVE', NULL, '410000', '鹤壁市', CAST('["朝歌", "鹤壁"]' AS JSON) FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `site` WHERE code='HEBI_CHAOGE_SERVICE_DEMO');
  INSERT INTO `site` (`code`, `name`, `site_type`, `scale_level`, `complex_code`, `longitude`, `latitude`, `coordinate_system`, `location_source`, `location_verified_at`, `timezone`, `is_demo`, `status`, `management_name`, `province_code`, `city_name`, `aliases_json`)
    SELECT 'HEBI_CHAOGE_TOLL_DEMO', '朝歌收费站', 'TOLL', 'M', 'HEBI_CHAOGE_COMPLEX', 114.2248910, 35.6640720, 'WGS84', '公开参考位置，非实测入口；设备与区域为虚构演示台账，需现场核验', NULL, 'Asia/Shanghai', 1, 'ACTIVE', NULL, '410000', '鹤壁市', CAST('["朝歌", "鹤壁"]' AS JSON) FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `site` WHERE code='HEBI_CHAOGE_TOLL_DEMO');
  INSERT INTO `site_area` (`site_id`, `parent_id`, `code`, `area_type`, `name`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO'), NULL, 'POWER', 'POWER_ROOM', '配电及储能区（演示）' FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `site_area` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='POWER');
  INSERT INTO `site_area` (`site_id`, `parent_id`, `code`, `area_type`, `name`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO'), NULL, 'PV', 'BUILDING', '光伏区（演示）' FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `site_area` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='PV');
  INSERT INTO `site_area` (`site_id`, `parent_id`, `code`, `area_type`, `name`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO'), NULL, 'PARK', 'PARKING', '停车充电区（演示）' FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `site_area` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='PARK');
  INSERT INTO `site_area` (`site_id`, `parent_id`, `code`, `area_type`, `name`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO'), NULL, 'POWER', 'POWER_ROOM', '配电及储能区（演示）' FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `site_area` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='POWER');
  INSERT INTO `site_area` (`site_id`, `parent_id`, `code`, `area_type`, `name`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO'), NULL, 'PV', 'BUILDING', '光伏区（演示）' FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `site_area` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='PV');
  INSERT INTO `site_area` (`site_id`, `parent_id`, `code`, `area_type`, `name`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO'), NULL, 'PARK', 'PARKING', '停车充电区（演示）' FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `site_area` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='PARK');
  INSERT INTO `site_route_link` (`site_id`, `area_id`, `route_id`, `link_code`, `direction_code`, `direction_label`, `chainage_m`, `access_type`, `is_primary`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO'), NULL, (SELECT id FROM `highway_route` WHERE `route_code` = 'S26'), 'S26_DEMO', 'UNKNOWN', '鹤辉高速段，方向待核验', NULL, 'DIRECT', 1 FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `site_route_link` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND link_code='S26_DEMO');
  INSERT INTO `site_route_link` (`site_id`, `area_id`, `route_id`, `link_code`, `direction_code`, `direction_label`, `chainage_m`, `access_type`, `is_primary`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO'), NULL, (SELECT id FROM `highway_route` WHERE `route_code` = 'S26'), 'S26_DEMO', 'UNKNOWN', '鹤辉高速段，方向待核验', NULL, 'DIRECT', 1 FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `site_route_link` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND link_code='S26_DEMO');
  INSERT INTO `device` (`site_id`, `area_id`, `parent_device_id`, `code`, `name`, `device_type`, `rated_power_kw`, `rated_energy_kwh`, `rated_capacity_kva`, `is_demo`, `status`, `system_type`, `manufacturer`, `model_code`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO'), (SELECT id FROM site_area WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='POWER'), NULL, 'ESS_01', '储能一体柜01（演示）', 'ESS_CABINET', 100.0000, 215.0000, NULL, 1, 'ACTIVE', 'ESS', NULL, NULL FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `device` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='ESS_01');
  INSERT INTO `device` (`site_id`, `area_id`, `parent_device_id`, `code`, `name`, `device_type`, `rated_power_kw`, `rated_energy_kwh`, `rated_capacity_kva`, `is_demo`, `status`, `system_type`, `manufacturer`, `model_code`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO'), (SELECT id FROM site_area WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='POWER'), NULL, 'TRANSFORMER_01', '箱式变压器01（演示）', 'TRANSFORMER', NULL, NULL, 630.0000, 1, 'ACTIVE', 'GRID', NULL, NULL FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `device` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='TRANSFORMER_01');
  INSERT INTO `device` (`site_id`, `area_id`, `parent_device_id`, `code`, `name`, `device_type`, `rated_power_kw`, `rated_energy_kwh`, `rated_capacity_kva`, `is_demo`, `status`, `system_type`, `manufacturer`, `model_code`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO'), (SELECT id FROM site_area WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='PV'), NULL, 'PV_01', '光伏阵列（演示）', 'PV_ARRAY', 120.0000, NULL, NULL, 1, 'ACTIVE', 'PV', NULL, NULL FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `device` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='PV_01');
  INSERT INTO `device` (`site_id`, `area_id`, `parent_device_id`, `code`, `name`, `device_type`, `rated_power_kw`, `rated_energy_kwh`, `rated_capacity_kva`, `is_demo`, `status`, `system_type`, `manufacturer`, `model_code`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO'), (SELECT id FROM site_area WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='PARK'), NULL, 'CHARGER_01', '直流充电桩01（演示）', 'DC_CHARGER', 120.0000, NULL, NULL, 1, 'ACTIVE', 'CHARGING', NULL, NULL FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `device` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_SERVICE_DEMO') AND code='CHARGER_01');
  INSERT INTO `device` (`site_id`, `area_id`, `parent_device_id`, `code`, `name`, `device_type`, `rated_power_kw`, `rated_energy_kwh`, `rated_capacity_kva`, `is_demo`, `status`, `system_type`, `manufacturer`, `model_code`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO'), (SELECT id FROM site_area WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='POWER'), NULL, 'ESS_01', '储能一体柜01（演示）', 'ESS_CABINET', 100.0000, 215.0000, NULL, 1, 'ACTIVE', 'ESS', NULL, NULL FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `device` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='ESS_01');
  INSERT INTO `device` (`site_id`, `area_id`, `parent_device_id`, `code`, `name`, `device_type`, `rated_power_kw`, `rated_energy_kwh`, `rated_capacity_kva`, `is_demo`, `status`, `system_type`, `manufacturer`, `model_code`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO'), (SELECT id FROM site_area WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='POWER'), NULL, 'TRANSFORMER_01', '箱式变压器01（演示）', 'TRANSFORMER', NULL, NULL, 630.0000, 1, 'ACTIVE', 'GRID', NULL, NULL FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `device` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='TRANSFORMER_01');
  INSERT INTO `device` (`site_id`, `area_id`, `parent_device_id`, `code`, `name`, `device_type`, `rated_power_kw`, `rated_energy_kwh`, `rated_capacity_kva`, `is_demo`, `status`, `system_type`, `manufacturer`, `model_code`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO'), (SELECT id FROM site_area WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='PV'), NULL, 'PV_01', '光伏阵列（演示）', 'PV_ARRAY', 120.0000, NULL, NULL, 1, 'ACTIVE', 'PV', NULL, NULL FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `device` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='PV_01');
  INSERT INTO `device` (`site_id`, `area_id`, `parent_device_id`, `code`, `name`, `device_type`, `rated_power_kw`, `rated_energy_kwh`, `rated_capacity_kva`, `is_demo`, `status`, `system_type`, `manufacturer`, `model_code`)
    SELECT (SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO'), (SELECT id FROM site_area WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='PARK'), NULL, 'CHARGER_01', '直流充电桩01（演示）', 'DC_CHARGER', 120.0000, NULL, NULL, 1, 'ACTIVE', 'CHARGING', NULL, NULL FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `device` WHERE site_id=(SELECT id FROM `site` WHERE `code` = 'HEBI_CHAOGE_TOLL_DEMO') AND code='CHARGER_01');

  COMMIT;
END$$
DELIMITER ;
CALL `c_spt_seed_assets_test_20261015`();
DROP PROCEDURE `c_spt_seed_assets_test_20261015`;
SET SESSION sql_mode = @c_asset_old_sql_mode;
SET SESSION time_zone = @c_asset_old_time_zone;

-- 核验：空台账导入后，两站应各有3区域、4设备。已有其他记录时数量可以更多。
SELECT s.id,s.code,s.name,s.is_demo,
       COUNT(DISTINCT a.id) AS area_count,COUNT(DISTINCT d.id) AS device_count
FROM site s
LEFT JOIN site_area a ON a.site_id=s.id
LEFT JOIN device d ON d.site_id=s.id
WHERE s.code IN ('HEBI_CHAOGE_SERVICE_DEMO','HEBI_CHAOGE_TOLL_DEMO')
GROUP BY s.id,s.code,s.name,s.is_demo;

-- 核验每台设备的归属和额定参数（不是实际采集值）。
SELECT s.name AS site_name,d.code,d.name,d.device_type,d.system_type,
       d.rated_power_kw,d.rated_energy_kwh,d.rated_capacity_kva,d.is_demo
FROM device d JOIN site s ON s.id=d.site_id
WHERE s.code IN ('HEBI_CHAOGE_SERVICE_DEMO','HEBI_CHAOGE_TOLL_DEMO')
ORDER BY s.code,d.code;
