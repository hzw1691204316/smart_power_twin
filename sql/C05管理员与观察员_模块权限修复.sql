-- 用途：为已有 ADMIN / VIEWER 角色显式补齐已启用模块的权限。
-- 这是用户主动执行的修复，每次执行都会补回下列缺失授权；不同于C03/C04首次初始化。
-- ADMIN：台账查看、监测查看/配置/采集、三维查看/发布；VIEWER：仅四项读取权限。
-- 作用于这两个角色下所有账号；不按用户名猜角色，不修改密码、状态、角色或站点范围。
-- 不创建账号，不导入模拟数据，不启用告警/汇总，不授予MySQL数据库用户GRANT权限。
USE smart_power_twin;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;
DELIMITER $$
CREATE PROCEDURE c_spt_role_repair_20261017() SQL SECURITY INVOKER
BEGIN
  DECLARE v_lock INT DEFAULT 0;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    IF v_lock=1 THEN DO RELEASE_LOCK('spt-role-repair-20261017'); END IF;
    RESIGNAL;
  END;
  SELECT GET_LOCK('spt-role-repair-20261017',10) INTO v_lock;
  IF COALESCE(v_lock,0)<>1 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ROLE_REPAIR_BUSY';
  END IF;
  START TRANSACTION;
  IF (SELECT COUNT(*) FROM sys_role WHERE code IN ('ADMIN','VIEWER'))<>2 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ROLE_REPAIR_EXPECTS_ADMIN_AND_VIEWER';
  END IF;
  INSERT INTO sys_permission(code,name)
    SELECT wanted.code,wanted.name FROM (
      SELECT 'site:read' AS code,'查询授权站点与区域' AS name
      UNION ALL SELECT 'device:read','查询授权站点设备'
      UNION ALL SELECT 'monitor:read','查询电力监测'
      UNION ALL SELECT 'monitor:configure','维护测点配置'
      UNION ALL SELECT 'telemetry:write','提交采样数据'
      UNION ALL SELECT 'twin:read','查询三维场景'
      UNION ALL SELECT 'twin:publish','管理并发布三维场景'
    ) AS wanted
    WHERE NOT EXISTS(SELECT 1 FROM sys_permission p WHERE p.code=wanted.code);
  INSERT INTO role_permission(role_id,permission_id)
    SELECT r.id,p.id FROM sys_role r CROSS JOIN sys_permission p
    WHERE ((r.code='ADMIN' AND p.code IN (
      'site:read','device:read','monitor:read','monitor:configure',
      'telemetry:write','twin:read','twin:publish'))
      OR (r.code='VIEWER' AND p.code IN (
      'site:read','device:read','monitor:read','twin:read')))
      AND NOT EXISTS(SELECT 1 FROM role_permission rp
        WHERE rp.role_id=r.id AND rp.permission_id=p.id);
  INSERT INTO audit_log(action,target_type,target_id,request_id,occurred_at,after_json)
    VALUES('system:permission-repair','role','ADMIN,VIEWER',
      CONCAT('role-repair-20261017-',UUID()),UTC_TIMESTAMP(3),
      JSON_OBJECT('source','manual_mysql_repair','note','补齐模块权限，保留站点范围和账号资料'));
  COMMIT;
  DO RELEASE_LOCK('spt-role-repair-20261017');
END$$
DELIMITER ;
CALL c_spt_role_repair_20261017();
DROP PROCEDURE c_spt_role_repair_20261017;
-- 核验1：ADMIN在本次七项中应有7项；VIEWER应有4项，只读。
SELECT r.code AS role_code,p.code AS permission_code
  FROM sys_role r JOIN role_permission rp ON rp.role_id=r.id
  JOIN sys_permission p ON p.id=rp.permission_id
  WHERE r.code IN ('ADMIN','VIEWER') AND p.code IN (
    'site:read','device:read','monitor:read','monitor:configure',
    'telemetry:write','twin:read','twin:publish')
  ORDER BY r.code,p.code;
-- 核验2：显示这两个角色下的实际用户名和原授权站点数；不查询密码。
-- 若admin/viewer不在此结果内，检查其实际角色，不要直接扩大其站点范围。
SELECT u.username,r.code AS role_code,u.status,
  (SELECT COUNT(*) FROM user_site_scope s WHERE s.user_id=u.id) AS authorized_site_count
  FROM sys_user u JOIN sys_role r ON r.id=u.role_id
  WHERE r.code IN ('ADMIN','VIEWER') ORDER BY r.code,u.username;
