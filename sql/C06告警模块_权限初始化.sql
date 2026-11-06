-- 告警模块显式授权补丁：用户手动整份执行，不在后端启动时导入。
-- ADMIN可读/确认/关闭，VIEWER只读；不改变其他权限、密码、状态或站点范围。
-- sim_*素材原本已有告警权限；本脚本针对原ADMIN/VIEWER角色。
-- 重复执行会补回本脚本列明的授权，故有意撤权后不应重跑。
USE smart_power_twin;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;
DELIMITER $$
CREATE PROCEDURE c_spt_alarm_permissions_20261018() SQL SECURITY INVOKER
BEGIN
  DECLARE v_lock INT DEFAULT 0;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    IF v_lock=1 THEN DO RELEASE_LOCK('spt-alarm-permissions-20261018'); END IF;
    RESIGNAL;
  END;
  SELECT GET_LOCK('spt-alarm-permissions-20261018',10) INTO v_lock;
  IF COALESCE(v_lock,0)<>1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ALARM_PATCH_BUSY'; END IF;
  START TRANSACTION;
  IF (SELECT COUNT(*) FROM sys_role WHERE code IN ('ADMIN','VIEWER'))<>2 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ALARM_PATCH_EXPECTS_ADMIN_AND_VIEWER';
  END IF;
  INSERT INTO sys_permission(code,name) SELECT 'alarm:read','查询告警'
    WHERE NOT EXISTS(SELECT 1 FROM sys_permission WHERE code='alarm:read');
  INSERT INTO sys_permission(code,name) SELECT 'alarm:ack','确认告警'
    WHERE NOT EXISTS(SELECT 1 FROM sys_permission WHERE code='alarm:ack');
  INSERT INTO sys_permission(code,name) SELECT 'alarm:close','关闭告警'
    WHERE NOT EXISTS(SELECT 1 FROM sys_permission WHERE code='alarm:close');
  INSERT INTO role_permission(role_id,permission_id)
    SELECT r.id,p.id FROM sys_role r CROSS JOIN sys_permission p
    WHERE ((r.code='ADMIN' AND p.code IN ('alarm:read','alarm:ack','alarm:close'))
        OR (r.code='VIEWER' AND p.code='alarm:read'))
      AND NOT EXISTS(SELECT 1 FROM role_permission rp
        WHERE rp.role_id=r.id AND rp.permission_id=p.id);
  INSERT INTO audit_log(action,target_type,target_id,request_id,occurred_at,after_json)
    VALUES('alarm:bootstrap','module','alarms',CONCAT('alarm-permissions-',UUID()),UTC_TIMESTAMP(3),
      JSON_OBJECT('source','manual_mysql_patch','note','补齐告警动作，不扩站点范围'));
  COMMIT;
  DO RELEASE_LOCK('spt-alarm-permissions-20261018');
END$$
DELIMITER ;
CALL c_spt_alarm_permissions_20261018();
DROP PROCEDURE c_spt_alarm_permissions_20261018;
SELECT r.code AS role_code,p.code AS permission_code FROM sys_role r
  JOIN role_permission rp ON rp.role_id=r.id JOIN sys_permission p ON p.id=rp.permission_id
  WHERE r.code IN ('ADMIN','VIEWER') AND p.code IN ('alarm:read','alarm:ack','alarm:close')
  ORDER BY r.code,p.code;
