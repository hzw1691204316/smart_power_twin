-- 大型服务区统一模板注册：手动执行；只新增模板版本和审计，不修改任何站点、授权或现有场景。
-- 网页“ 大型服务区模型 ”入口无需执行本SQL即可查看。私有业务站点仍须显式配置并发布场景。
-- 模板规模L是方案分类；不自动把所有服务区都改成大型。
USE smart_power_twin;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;
DELIMITER $$
DROP PROCEDURE IF EXISTS c_spt_service_large_20261018$$
CREATE PROCEDURE c_spt_service_large_20261018() SQL SECURITY INVOKER
BEGIN
  DECLARE v_lock INT DEFAULT 0;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    IF v_lock=1 THEN DO RELEASE_LOCK('spt-service-large-20261018'); END IF;
    RESIGNAL;
  END;
  SELECT GET_LOCK('spt-service-large-20261018',10) INTO v_lock;
  IF COALESCE(v_lock,0)<>1 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='SERVICE_L_PATCH_BUSY';
  END IF;
  START TRANSACTION;
  -- 同编号同版本若已经有其他资源，不擅自覆盖，先由维护者核查冲突。
  IF EXISTS(SELECT 1 FROM scene_template WHERE template_code='SERVICE_L' AND version_no=20261018
      AND (site_type<>'SERVICE' OR scale_level<>'L' OR status<>'PUBLISHED'
           OR NOT(model_uri <=> '/models/service_large.glb'))) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='SERVICE_L_VERSION_CONFLICT';
  END IF;
  INSERT INTO scene_template
    (template_code,name,site_type,scale_level,version_no,status,model_uri,layout_json,resource_manifest_json)
  SELECT 'SERVICE_L','大型双侧服务区·光伏储能充电','SERVICE','L',20261018,'PUBLISHED',
    '/models/service_large.glb','{"source":"PROPOSED","templateCode":"SERVICE_L","pvPanelCount":154,"energyObjectKeys":["pv_roof_north_01","pv_roof_north_02","pv_roof_south_01","pv_roof_south_02","pv_roof_north_aux","pv_roof_south_aux","pv_canopy_north","charger_north_01","charger_north_02","charger_north_03","charger_north_04","charger_north_05","charger_north_06","pv_canopy_south","charger_south_01","charger_south_02","charger_south_03","charger_south_04","charger_south_05","charger_south_06","transformer_north_01","storage_north_01","storage_north_02","inverter_north_01","inverter_north_02","meter_north_01","fire_cabinet_north","transformer_south_01","storage_south_01","storage_south_02","inverter_south_01","inverter_south_02","meter_south_01","fire_cabinet_south"]}','{"uri":"/models/service_large.glb","sha256":"56ec895b36acb59af98ac14c125f2f68d60162fd2b5ceea3e3dcdb4744d36c75","byteSize":12501780,"source":"用户参考总平面图与本地Blender生成，外观及设备布局待核验","objectKeys":["pv_roof_north_01","pv_roof_north_02","pv_roof_south_01","pv_roof_south_02","pv_roof_north_aux","pv_roof_south_aux","charging_canopy_north","pv_canopy_north","charger_north_01","charger_north_02","charger_north_03","charger_north_04","charger_north_05","charger_north_06","charging_canopy_south","pv_canopy_south","charger_south_01","charger_south_02","charger_south_03","charger_south_04","charger_south_05","charger_south_06","energy_yard_north","transformer_north_01","storage_north_01","storage_north_02","inverter_north_01","inverter_north_02","meter_north_01","fire_cabinet_north","energy_yard_south","transformer_south_01","storage_south_01","storage_south_02","inverter_south_01","inverter_south_02","meter_south_01","fire_cabinet_south"]}'
  WHERE NOT EXISTS(SELECT 1 FROM scene_template WHERE template_code='SERVICE_L' AND version_no=20261018);
  INSERT INTO audit_log(action,target_type,target_id,request_id,occurred_at,after_json)
  SELECT 'twin:template_register','scene_template',CAST(id AS CHAR),
    'service-large-template-20261018',UTC_TIMESTAMP(3),
    JSON_OBJECT('source','manual_template_registration','modelUri','/models/service_large.glb','scale','L')
  FROM scene_template
  WHERE template_code='SERVICE_L' AND version_no=20261018
    AND NOT EXISTS(SELECT 1 FROM audit_log WHERE request_id='service-large-template-20261018');
  COMMIT;
  DO RELEASE_LOCK('spt-service-large-20261018');
END$$
DELIMITER ;
CALL c_spt_service_large_20261018();
DROP PROCEDURE c_spt_service_large_20261018;
-- 核验注册结果；旧版草稿可继续保留，不应为改模板而删除旧场景。
SELECT id,template_code,name,site_type,scale_level,version_no,status,model_uri
FROM scene_template WHERE template_code='SERVICE_L' ORDER BY version_no DESC;
