-- 只读核验19表模拟数据；不会修改业务记录，也不会显示密码。
-- 第1组是整库数量，旧账号/原模板等仍在时总数可大于模拟集数量。
-- 后面按批次/版本/站点检查。人工改过数据后应结合实际解释，不能盲目补回已撤销权限。
USE `smart_power_twin`;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;
SET @mock_batch='sim-full-v1-20261016';
SET @mock_version=20261016;
SET @mock_sequence=20261016;

-- 1. 19表全覆盖；expected_fixture_rows是空库首次导入预期，actual_total_rows是当前全表数量。
SELECT 'sys_role' AS table_name,3 AS expected_fixture_rows,COUNT(*) AS actual_total_rows FROM sys_role
UNION ALL SELECT 'sys_permission',14,COUNT(*) FROM sys_permission
UNION ALL SELECT 'role_permission',29,COUNT(*) FROM role_permission
UNION ALL SELECT 'sys_user',4,COUNT(*) FROM sys_user
UNION ALL SELECT 'highway_route',3,COUNT(*) FROM highway_route
UNION ALL SELECT 'site',6,COUNT(*) FROM site
UNION ALL SELECT 'user_site_scope',10,COUNT(*) FROM user_site_scope
UNION ALL SELECT 'site_area',18,COUNT(*) FROM site_area
UNION ALL SELECT 'site_route_link',6,COUNT(*) FROM site_route_link
UNION ALL SELECT 'device',24,COUNT(*) FROM device
UNION ALL SELECT 'device_point',96,COUNT(*) FROM device_point
UNION ALL SELECT 'point_latest',96,COUNT(*) FROM point_latest
UNION ALL SELECT 'point_history',9216,COUNT(*) FROM point_history
UNION ALL SELECT 'scene_template',6,COUNT(*) FROM scene_template
UNION ALL SELECT 'twin_scene',6,COUNT(*) FROM twin_scene
UNION ALL SELECT 'twin_object',24,COUNT(*) FROM twin_object
UNION ALL SELECT 'twin_binding',96,COUNT(*) FROM twin_binding
UNION ALL SELECT 'alarm_event',6,COUNT(*) FROM alarm_event
UNION ALL SELECT 'audit_log',11,COUNT(*) FROM audit_log;

-- 2. 首次导入快照时间：数据库约定UTC，+8小时用于北京时间展示；重跑此时间不应变化。
SELECT request_id,occurred_at AS snapshot_utc,TIMESTAMPADD(HOUR,8,occurred_at) AS snapshot_beijing,
       JSON_UNQUOTE(JSON_EXTRACT(after_json,'$.source')) AS source
FROM audit_log WHERE request_id=@mock_batch;

-- 3. 六站各3区域、4设备、16测点、1条本批次告警。均为模拟台账，朝歌位置仍待实地核验。
SELECT s.code,s.name,s.site_type,s.city_name,s.is_demo,
       (SELECT COUNT(*) FROM site_area a WHERE a.site_id=s.id) AS areas,
       (SELECT COUNT(*) FROM device d WHERE d.site_id=s.id) AS devices,
       (SELECT COUNT(*) FROM device_point p WHERE p.site_id=s.id) AS points,
       (SELECT COUNT(*) FROM alarm_event e WHERE e.site_id=s.id AND e.event_key LIKE CONCAT(@mock_batch,'-alarm-%')) AS mock_alarms
FROM site s WHERE s.code IN ('HEBI_CHAOGE_SERVICE_DEMO','HEBI_CHAOGE_TOLL_DEMO',
  'DEMO_SERVICE_02','DEMO_TOLL_02','DEMO_SERVICE_03','DEMO_TOLL_03') ORDER BY s.code;

-- 4. 账号范围：新建时sim_admin=6、sim_operator=2、sim_viewer=1、sim_locked=1；锁定账号应无法登录。
SELECT u.username,u.display_name,u.status,r.code AS role_code,COUNT(us.site_id) AS authorized_sites
FROM sys_user u JOIN sys_role r ON r.id=u.role_id LEFT JOIN user_site_scope us ON us.user_id=u.id
WHERE u.username IN ('sim_admin','sim_operator','sim_viewer','sim_locked')
GROUP BY u.id,u.username,u.display_name,u.status,r.code ORDER BY u.username;

-- 5. 模板：中型2条有GLB，小/大型4条只是草稿；已有版本1模板不在此结果中。
SELECT template_code,version_no,status,model_uri FROM scene_template
WHERE version_no=@mock_version ORDER BY template_code;
SELECT s.code,sc.version_no,sc.status,t.template_code,COALESCE(sc.model_uri,t.model_uri) AS model_uri
FROM twin_scene sc JOIN site s ON s.id=sc.site_id JOIN scene_template t ON t.id=sc.template_id
WHERE sc.version_no=@mock_version ORDER BY s.code;

-- 6. 历史曲线：每测点96条/15分钟采样，共9216条；跨午夜时是最近23小时45分的96个采样时刻。
SELECT s.code,d.code AS device_code,p.code AS point_code,p.unit,p.value_type,p.aggregation_type,
       COUNT(h.point_id) AS samples,MIN(h.sampled_at) AS from_utc,MAX(h.sampled_at) AS to_utc
FROM point_history h JOIN device_point p ON p.id=h.point_id JOIN device d ON d.id=p.device_id
JOIN site s ON s.id=p.site_id WHERE h.source_sequence=@mock_sequence
GROUP BY s.code,d.code,p.code,p.unit,p.value_type,p.aggregation_type ORDER BY s.code,d.code,p.code;

-- 7. 最新值：BAD的空值不能当0；许昌全站故意滞后2小时，其他静态快照30分钟后也会变陈旧。
SELECT s.code,d.code AS device_code,p.code AS point_code,p.unit,l.value_numeric,l.value_text,l.quality,
       l.source_time AS sampled_utc,
       CASE WHEN TIMESTAMPDIFF(MICROSECOND,l.source_time,UTC_TIMESTAMP(3))>p.stale_after_ms*1000
            THEN 'STALE' ELSE 'WITHIN_WINDOW' END AS freshness
FROM point_latest l JOIN device_point p ON p.id=l.point_id JOIN device d ON d.id=p.device_id
JOIN site s ON s.id=p.site_id WHERE l.source_sequence=@mock_sequence ORDER BY s.code,d.code,p.code;

-- 8. 告警：初始ACTIVE=4、RECOVERED=1、CLOSED=1；确认是独立字段，不等于恢复。
SELECT status,COUNT(*) AS events FROM alarm_event WHERE event_key LIKE CONCAT(@mock_batch,'-alarm-%') GROUP BY status;
SELECT s.code,a.message,a.severity,a.status,a.raised_at,a.recovered_at,a.acknowledged_at,u.username AS acknowledged_by
FROM alarm_event a JOIN site s ON s.id=a.site_id LEFT JOIN sys_user u ON u.id=a.acknowledged_by
WHERE a.event_key LIKE CONCAT(@mock_batch,'-alarm-%') ORDER BY a.event_key;

-- 9. 关系与一致性检查，初始导入以下五项应均为0。后续撤权/人工改最新值时后两项需按变更解释。
SELECT 'missing_point_parent' AS check_name,COUNT(*) AS problems
FROM device_point p LEFT JOIN device d ON d.id=p.device_id AND d.site_id=p.site_id WHERE d.id IS NULL
UNION ALL
SELECT 'binding_site_device_mismatch',COUNT(*) FROM twin_binding b
LEFT JOIN twin_object o ON o.id=b.object_id AND o.site_id=b.site_id AND o.device_id=b.device_id
LEFT JOIN device_point p ON p.id=b.point_id AND p.site_id=b.site_id AND p.device_id=b.device_id
WHERE o.id IS NULL OR p.id IS NULL
UNION ALL
SELECT 'missing_history_point',COUNT(*) FROM point_history h LEFT JOIN device_point p ON p.id=h.point_id WHERE p.id IS NULL
UNION ALL
SELECT 'alarm_actor_scope_mismatch',COUNT(*) FROM alarm_event a
WHERE a.event_key LIKE CONCAT(@mock_batch,'-alarm-%') AND a.acknowledged_by IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM user_site_scope us WHERE us.user_id=a.acknowledged_by AND us.site_id=a.site_id)
UNION ALL
SELECT 'mock_latest_history_mismatch',COUNT(*) FROM point_latest l
LEFT JOIN point_history h ON h.point_id=l.point_id AND h.sampled_at=l.source_time AND h.source_sequence=l.source_sequence
WHERE l.source_sequence=@mock_sequence AND (h.point_id IS NULL OR NOT(l.value_numeric <=> h.value_numeric)
  OR NOT(l.value_text <=> h.value_text) OR l.quality<>h.quality);
