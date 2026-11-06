-- 大屏汇总权限补丁：手动整份执行；仅为原ADMIN/VIEWER角色增加dashboard:read。
-- 不更改密码、账号状态、站点范围或其他动作。模拟sim_*角色原本已有此权限。
-- 重跑会补回本脚本声明的权限，有意撤权后不应重跑。
USE smart_power_twin;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;
DELIMITER $$
CREATE PROCEDURE c_spt_dashboard_permissions_20261018() SQL SECURITY INVOKER
BEGIN
  DECLARE v_lock INT DEFAULT 0;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    IF v_lock=1 THEN DO RELEASE_LOCK('spt-dashboard-permissions-20261018'); END IF;
    RESIGNAL;
  END;
  SELECT GET_LOCK('spt-dashboard-permissions-20261018',10) INTO v_lock;
  IF COALESCE(v_lock,0)<>1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='DASHBOARD_PATCH_BUSY'; END IF;
  START TRANSACTION;
  IF (SELECT COUNT(*) FROM sys_role WHERE code IN ('ADMIN','VIEWER'))<>2 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='DASHBOARD_PATCH_EXPECTS_ADMIN_AND_VIEWER';
  END IF;
  INSERT INTO sys_permission(code,name) SELECT 'dashboard:read','查询大屏汇总'
    WHERE NOT EXISTS(SELECT 1 FROM sys_permission WHERE code='dashboard:read');
  INSERT INTO role_permission(role_id,permission_id)
    SELECT r.id,p.id FROM sys_role r CROSS JOIN sys_permission p
    WHERE r.code IN ('ADMIN','VIEWER') AND p.code='dashboard:read'
      AND NOT EXISTS(SELECT 1 FROM role_permission rp WHERE rp.role_id=r.id AND rp.permission_id=p.id);
  INSERT INTO audit_log(action,target_type,target_id,request_id,occurred_at,after_json)
    VALUES('dashboard:bootstrap','module','dashboard',CONCAT('dashboard-permissions-',UUID()),UTC_TIMESTAMP(3),
      JSON_OBJECT('source','manual_mysql_patch','note','仅补齐大屏读取动作，不扩大站点范围'));
  COMMIT;
  DO RELEASE_LOCK('spt-dashboard-permissions-20261018');
END$$
DELIMITER ;
CALL c_spt_dashboard_permissions_20261018();
DROP PROCEDURE c_spt_dashboard_permissions_20261018;
SELECT r.code AS role_code,p.code AS permission_code FROM sys_role r
  JOIN role_permission rp ON rp.role_id=r.id JOIN sys_permission p ON p.id=rp.permission_id
  WHERE r.code IN ('ADMIN','VIEWER') AND p.code='dashboard:read' ORDER BY r.code;
