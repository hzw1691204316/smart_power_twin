-- C02只读核验：不读取password，不修改任何数据。
USE `smart_power_twin`;
SELECT VERSION() AS mysql_version, DATABASE() AS current_database;
SELECT r.code AS role_code,p.code AS permission_code FROM sys_role r
 JOIN role_permission rp ON rp.role_id=r.id JOIN sys_permission p ON p.id=rp.permission_id
 WHERE r.code IN ('ADMIN','VIEWER') ORDER BY r.code,p.code;
SELECT u.id,u.username,u.display_name,u.status,r.code AS role_code,s.code AS site_code,s.name
 FROM sys_user u JOIN sys_role r ON r.id=u.role_id
 LEFT JOIN user_site_scope uss ON uss.user_id=u.id LEFT JOIN site s ON s.id=uss.site_id
 WHERE u.username IN ('mysql_admin','mysql_viewer') ORDER BY u.username,s.code;
SELECT s.code,s.name,s.is_demo,COUNT(DISTINCT a.id) AS area_count,COUNT(DISTINCT d.id) AS device_count
 FROM site s LEFT JOIN site_area a ON a.site_id=s.id LEFT JOIN device d ON d.site_id=s.id
 WHERE s.code IN ('HEBI_CHAOGE_SERVICE_DEMO','HEBI_CHAOGE_TOLL_DEMO') GROUP BY s.id,s.code,s.name,s.is_demo;
-- 每站3区域/4设备；管理员两站，观察员仅服务区；ADMIN五权限/VIEWER两权限。
SELECT u.username,COUNT(*) AS bootstrap_audits FROM audit_log a JOIN sys_user u ON u.id=a.actor_id
 WHERE a.action='user:bootstrap' GROUP BY u.username;
