-- 台账维护权限：用户手动执行；只为ADMIN和现有SIM_ADMIN角色增加site:create、asset:manage。
-- VIEWER/SIM_VIEWER/SIM_OPERATOR不授予写入能力；不改既有账号、密码或站点范围。
-- site:create仅使创建者获得其新建站点的范围；不会扩展现有站点范围。
-- 重复执行会补回本脚本声明的权限，有意撤权后不要重跑。
USE smart_power_twin;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;
DELIMITER $$
CREATE PROCEDURE c_spt_asset_permissions_20261018() SQL SECURITY INVOKER
BEGIN
  DECLARE v_lock INT DEFAULT 0;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    IF v_lock=1 THEN DO RELEASE_LOCK('spt-asset-permissions-20261018'); END IF;
    RESIGNAL;
  END;
  SELECT GET_LOCK('spt-asset-permissions-20261018',10) INTO v_lock;
  IF COALESCE(v_lock,0)<>1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ASSET_PATCH_BUSY'; END IF;
  START TRANSACTION;
  IF NOT EXISTS(SELECT 1 FROM sys_role WHERE code='ADMIN') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ASSET_PATCH_EXPECTS_ADMIN';
  END IF;
  INSERT INTO sys_permission(code,name) SELECT 'site:create','新增业务站点'
    WHERE NOT EXISTS(SELECT 1 FROM sys_permission WHERE code='site:create');
  INSERT INTO sys_permission(code,name) SELECT 'asset:manage','维护站点与设备台账'
    WHERE NOT EXISTS(SELECT 1 FROM sys_permission WHERE code='asset:manage');
  INSERT INTO role_permission(role_id,permission_id)
    SELECT r.id,p.id FROM sys_role r CROSS JOIN sys_permission p
    WHERE r.code IN ('ADMIN','SIM_ADMIN') AND p.code IN ('site:create','asset:manage')
      AND NOT EXISTS(SELECT 1 FROM role_permission rp WHERE rp.role_id=r.id AND rp.permission_id=p.id);
  INSERT INTO audit_log(action,target_type,target_id,request_id,occurred_at,after_json)
    VALUES('asset:bootstrap','module','assets',CONCAT('asset-permissions-',UUID()),UTC_TIMESTAMP(3),
      JSON_OBJECT('source','manual_mysql_patch','note','新增台账维护动作，不扩大既有站点范围'));
  COMMIT;
  DO RELEASE_LOCK('spt-asset-permissions-20261018');
END$$
DELIMITER ;
CALL c_spt_asset_permissions_20261018();
DROP PROCEDURE c_spt_asset_permissions_20261018;
SELECT r.code AS role_code,p.code AS permission_code FROM sys_role r
 JOIN role_permission rp ON rp.role_id=r.id JOIN sys_permission p ON p.id=rp.permission_id
 WHERE p.code IN ('site:create','asset:manage') ORDER BY r.code,p.code;
