-- 监测模块动作权限补丁；不修改账号密码、状态或站点范围。不导入测点/采样。
-- 已用全模块模拟数据的sim_*账号本来已有权限；本补丁为原ADMIN/VIEWER角色补齐。
-- 只在本补丁首次成功时授予；重复执行不恢复后来人工撤销的角色权限。
USE smart_power_twin;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;
DELIMITER $$
CREATE PROCEDURE c_spt_monitor_permissions_20261016() SQL SECURITY INVOKER
BEGIN
  DECLARE v_lock INT DEFAULT 0;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    IF v_lock=1 THEN DO RELEASE_LOCK('spt-monitor-permissions-20261016'); END IF;
    RESIGNAL;
  END;
  SELECT GET_LOCK('spt-monitor-permissions-20261016',10) INTO v_lock;
  IF COALESCE(v_lock,0)<>1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='MONITOR_PATCH_BUSY'; END IF;
  START TRANSACTION;
  IF NOT EXISTS(SELECT 1 FROM audit_log WHERE request_id='monitor-permissions-20261016') THEN
    INSERT INTO sys_permission(code,name) SELECT 'monitor:read','查询电力监测'
      WHERE NOT EXISTS(SELECT 1 FROM sys_permission WHERE code='monitor:read');
    INSERT INTO sys_permission(code,name) SELECT 'telemetry:write','提交采样数据'
      WHERE NOT EXISTS(SELECT 1 FROM sys_permission WHERE code='telemetry:write');
    INSERT INTO sys_permission(code,name) SELECT 'monitor:configure','维护测点配置'
      WHERE NOT EXISTS(SELECT 1 FROM sys_permission WHERE code='monitor:configure');
    INSERT INTO role_permission(role_id,permission_id)
      SELECT r.id,p.id FROM sys_role r CROSS JOIN sys_permission p
      WHERE ((r.code='ADMIN' AND p.code IN ('monitor:read','telemetry:write','monitor:configure'))
          OR (r.code='VIEWER' AND p.code='monitor:read'))
        AND NOT EXISTS(SELECT 1 FROM role_permission rp WHERE rp.role_id=r.id AND rp.permission_id=p.id);
    INSERT INTO audit_log(action,target_type,target_id,request_id,occurred_at,after_json)
      VALUES('monitor:bootstrap','module','monitoring','monitor-permissions-20261016',UTC_TIMESTAMP(3),
             JSON_OBJECT('source','manual_mysql_patch','note','只初始化监测动作，不扩站点范围'));
  END IF;
  COMMIT;
  DO RELEASE_LOCK('spt-monitor-permissions-20261016');
END$$
DELIMITER ;
CALL c_spt_monitor_permissions_20261016();
DROP PROCEDURE c_spt_monitor_permissions_20261016;
-- 查询结果不含密码；ADMIN预期3项，VIEWER预期1项；sim_*原授权保留。
SELECT r.code,p.code AS permission_code FROM sys_role r JOIN role_permission rp ON rp.role_id=r.id
JOIN sys_permission p ON p.id=rp.permission_id WHERE p.code IN ('monitor:read','telemetry:write','monitor:configure')
ORDER BY r.code,p.code;
