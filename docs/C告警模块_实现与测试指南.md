# 告警模块：实现与测试指南

更新：2026-10-18。项目根目录：`D:\study_software\PythonProject\smart_power_twin`。

## 1. 现在做到哪个模块

| 顺序 | 模块 | 当前可以做什么 |
|---|---|---|
| 1 | system 账号权限 | MySQL登录、开户、角色动作、站点范围、操作审计 |
| 2 | assets 站点设备台账 | 查询站点、设备、区域及关联高速；维护/批量导入仍待完善 |
| 3 | monitoring 电力监测 | 测点配置、采样接收、最新值、历史、质量、陈旧及幂等处理 |
| 4 | twin 三维绑定 | 读取发布场景、模型对象关联设备/测点、复制草稿与显式发布 |
| 5 | alarms 告警处置 | 本轮完成数值阈值触发/恢复、分页筛选、详情、确认、关闭、模型定位 |
| 6 | dashboard 大屏汇总 | 下一主要模块，尚未注册；现有总览/能耗统计仍明确标为示例 |

当前正式后端启用五个模块、十九张表。已有全模块十九表无需重建。公司提供的真实资料与接口尚未接入，模型仍为通用样板，不应描述为现场实测成果。

## 2. 你现在先做这三步

1. 已有 `alarm_event` 表则跳过建表。确实缺表时，整份执行 `C00告警模块_仅缺表时使用.sql`；需要原站点、设备、测点、账号表已经存在。它只补缺表，不修复已有旧字段。
2. 使用原 admin/viewer 或 mysql_admin/mysql_viewer 网页账号时，在 MySQL 客户端整份执行 `C06告警模块_权限初始化.sql`。实际按角色编码 ADMIN/VIEWER 授权，不凭用户名修改角色。C06 不包含以前缺失的监测/三维权限；这些仍由 C03/C04 或 C05 补齐。
3. 重启后端或等待 PyCharm reload 完成，前端退出重新登录；进入朝歌服务区/收费站三维页，查看右侧“站点告警 · MySQL”。底部“告警中心”仍在同页，不额外开标签页。

`sim_admin`、`sim_operator`、`sim_viewer` 使用之前全模块模拟素材时本来已有对应告警权限。已有模拟数据不必重新导入，不要为补权限重跑账号初始化或覆盖密码。

本轮没有连接、导入或改动你的实际 MySQL；上述 SQL 仍由你手动执行。SQL 和本文均有桌面“智慧电力文档”副本，项目 sql/docs 保存镜像。

## 3. 告警状态怎样理解

| 字段/状态 | 业务含义 |
|---|---|
| ACTIVE | 异常已发生，尚无符合条件的恢复采样 |
| acknowledgedAt 为空 | 尚未人工确认，与是否恢复无关 |
| acknowledgedAt 有时间 | 值班人员已知晓；不代表设备恢复 |
| RECOVERED | 本引擎已收到符合条件的正常新采样；仍可能未确认 |
| CLOSED | 已恢复，并已人工确认，再手动关闭 |

例：温度上限55°C，收到62°C触发 → 点“确认”后仍为ACTIVE → 新采样45°C使它RECOVERED → 点“关闭”后CLOSED。也可以先恢复再确认，最终仍须两个条件同时满足。

连续多个超限样本仅保留一条活动事件；恢复后又异常属于新的一次发生，即使上一次还没人工关闭，也可以产生新事件。重复确认/关闭不会覆盖首次确认人、确认时间或重复追加处置审计。

## 4. 本轮的自动规则和限制

本轮沿用 `device_point.alarm_low / alarm_high`，没有新建复杂规则表。

- 启用的 NUMERIC 测点，至少配置一个阈值；高低阈值必须有效，低值小于高值。
- 数值严格小于下限或严格大于上限才触发，等于边界视为正常。
- 只有推进“最新值”的 GOOD 数值才参与评估。与同一时刻相比，源序号更高的修订也算更新。
- 样本时间须处于服务器当前时刻之前，且未超过测点 `stale_after_ms`。未来样本虽可能满足监测接收条件，仍不用于本轮告警评估。
- 重复样本、迟到历史、陈旧历史、BAD/SUSPECT/MANUAL/ESTIMATED 不触发，也不恢复当前告警。
- BOOL/TEXT 不使用数值阈值。没有定时断流检测，不把页面“陈旧”直接写成离线告警。
- 修改阈值或停用测点本身不自动恢复事件；至少还有一个阈值时，下次有效新采样按当前阈值判断。旧事件发生时的阈值快照保持不变，配置变更有审计。
- 新阈值事件等级暂为 MINOR（一般），不凭空制定公司的紧急分级。

事件快照记录 `rule=numeric_threshold_v1`、source、发生值、上下限、单位、源采样时间及源序号。引擎只恢复自己产生且带此规则标记的活动事件，不擅自恢复外部平台或手工导入事件。

上一批六条告警模拟数据用于演示不同状态，未带本引擎规则标记。例如其中的BAD、断流记录只是导入示例，不代表已实现对应自动规则。可查看、确认，已恢复记录可关闭；导入的活动记录不会被新的正常数值自动消除。本轮不提供人工伪造恢复接口。

## 5. 前端怎样测试

### A. 查看与筛选

进入已授权站点，右侧“站点告警 · MySQL”可按状态、级别、是否确认筛选，每页10条。显示的数量是本站当前筛选总数，不是全省总数。

点击一条记录，查看发生/恢复/确认时间、确认用户名、处理说明和发生快照。界面使用北京时间显示，数据库与API时间使用UTC。

“没有匹配记录”仅说明查询为空，不代表设备在线或故障已恢复。没有告警权限时会明确提示C06，不退回前端演示告警。

### B. 确认与关闭

ADMIN管理员：未确认且未关闭的记录可填写说明后确认。已恢复且已确认时才显示关闭按钮。活动事件不会出现可关闭入口，后端也会再次校验。

VIEWER观察员：可读本人站点，不能确认和关闭。原站点范围不扩展，观察员只有服务区范围时，不能查看旁边收费站。

如果页面报“当前MySQL只读模式”，检查自己的 `.env.mysql.local` 中是否已按现有方案开启 `SPT_MYSQL_ALLOW_WRITES=true`，修改配置后重启。这里的写开关只允许业务写入，不等于给网页viewer授予处置权限。

### C. 定位模型

详情中点击“定位关联设备”，使用事件deviceId匹配当前已发布场景的对象；同设备有多个对象时，优先选择绑定该事件pointId的对象。不会用固定的设备编码表猜GLB节点。

定位后打开设备监测区域，显示当前对象绑定的读数；这是当前监测，不代表事件发生时的值。事件发生值请看快照。站点级事件没有设备ID，不提供模型定位；设备尚未绑定当前场景时显示原因，不定位到其他设备。

公开地图中未绑定私有台账的设施继续使用通用模板示意，不请求本站私有告警，也不展示其他站点事件。

## 6. 怎样产生一条新的模拟阈值告警

需要之前的模拟站点、设备、测点以及具备采集权限的账号。请先在项目根目录启动后端：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_backend_mysql
```

另开终端，在同一项目根目录使用原独立模拟工具；只有显式 `--send` 才会提交数据。网页登录密码交互输入，不写进命令参数。下面的 admin 请替换为你实际具备采集权限的用户名，也可用已有 sim_operator：

```powershell
# 一次提交朝歌服务区“充电桩温度偏高”模拟采样。
.\.venv\Scripts\python.exe -m scripts.simulate_telemetry --username admin --site-code HEBI_CHAOGE_SERVICE_DEMO --scenario hot --cycles 1 --send
```

默认模拟素材的充电桩温度上限55°C，hot情景给出62.1°C；如果你已修改阈值，先以实际测点配置为准。刷新告警面板，注意区分原导入事件和本次新事件：新事件快照有 `numeric_threshold_v1`。

确认新事件，然后提交一次正常模拟采样：

```powershell
.\.venv\Scripts\python.exe -m scripts.simulate_telemetry --username admin --site-code HEBI_CHAOGE_SERVICE_DEMO --scenario normal --cycles 1 --send
```

正常情景温度通常在正常范围；刷新后核对该新事件是否为RECOVERED，再关闭。模拟程序只提交数据，不自动人工确认。服务器启动时不会自动运行模拟采集，前端本轮也不自动轮询，需手动刷新告警。

## 7. 后端接口与字段

所有接口前缀 `/api/v1`，需要Bearer登录。四个端点：

| 方法/路径 | 权限 | 作用 |
|---|---|---|
| GET /alarms | alarm:read | 当前授权范围内分页查询 |
| GET /alarms/{eventId} | alarm:read | 详情与发生快照 |
| POST /alarms/{eventId}/acknowledge | alarm:ack | 首次人工确认 |
| POST /alarms/{eventId}/close | alarm:close | 关闭已恢复且已确认的事件 |

查询参数：page从1起，pageSize为1—100；siteId/deviceId/pointId为可选十进制字符串；status为ACTIVE/RECOVERED/CLOSED；severity为INFO/MINOR/MAJOR/CRITICAL；acknowledged为布尔值。startTime/endTime须带时区，按发生时间半开区间 `[start,end)` 筛选，起点须小于终点；不填写则不限制时间。

动作请求例：`{"handlingNote":"已检查，等待正常采样"}`。说明最长1000字符，可留空。未知字段422，客户端不能指定确认人、恢复时刻、发生值或修改事件等级。

响应为data与meta；分页meta含total/page/pageSize/hasNext。事件ID、站点ID、设备ID、测点ID和确认人ID均用字符串，避免JS整数精度损失。response_model及中文字段说明已进入 `/docs` OpenAPI。

- status与acknowledgedAt独立；recoveredAt未恢复为空，不填0或页面时间。
- siteName/deviceName/pointName是当前台账名称；triggerSnapshot是发生时资料。
- isDemo标明资产演示身份，source从快照取SIMULATED/FIELD，未知为UNKNOWN；MySQL不代表现场采集。
- 无动作权限403，具体资源不存在或范围外404，活动/未确认关闭409，参数422，数据库不可用503。

没有POST“恢复”接口，恢复从经校验的采样事务产生。

## 8. 代码在哪里、以后怎样修改

| 文件/目录 | 职责与修改位置 |
|---|---|
| app/modules/alarms/models.py | 既有alarm_event表映射；不自动建表 |
| app/modules/alarms/schemas.py | 严格动作参数与完整事件响应字段 |
| app/modules/alarms/router.py | 分页/筛选、动作权限及接口装配 |
| app/modules/alarms/repository.py | 范围过滤、排序、活动事件锁定当前读 |
| app/modules/alarms/service.py | evaluate触发/恢复；act确认/关闭；alarm_out响应 |
| app/modules/monitoring/service.py | 在latest推进分支调用evaluate，共用采样事务 |
| smart_power_web/src/types/alarms.ts | 前后端事件字段类型 |
| smart_power_web/src/services/alarmService.ts | 按授权code解析站点ID及HTTP请求 |
| smart_power_web/src/composables/useAlarmEvents.ts | 分页筛选、详情/处置状态、跨账号/站点的迟到响应隔离 |
| smart_power_web/src/components/twin/AlarmPanel.vue | 三维页右侧告警界面，局部海蓝样式 |
| smart_power_web/src/views/SiteView.vue | 私有告警入口与真实设备到模型对象的定位 |
| tests/test_alarms.py | 业务边界和状态机测试 |
| tests/test_full_mock_data.py | 独立MySQL并发、权限补丁与故障回滚验收 |
| smart_power_web/scripts/check-alarms.mjs | 真实Vue状态/组件的身份隔离、分页及只读按钮验收 |

以后若增加短信、延时触发、回差、按来源区分的规则或现场故障码，应先确认业务协议，避免在路由里堆判断。设备质量/断流告警需要单独评估机制，不通过本轮数值规则硬套。

## 9. 事务与数据库连接账号

采样按升序锁定测点，再锁当前最新值与本引擎的活动告警；同一测点并发首次异常只发生一次。采样历史、最新值、事件与审计同事务，任何后续错误会回滚整批。

确认/关闭锁定事件行后再检查最新状态，重复请求不重复审计。网页用户动作权限与后端连接MySQL账号的数据库权限是两层：C06只处理前者，不执行数据库GRANT。

使用受限数据库账号时，管理员需按实际连接账号/Host授予alarm_event的SELECT/INSERT/UPDATE，以及原采样流程的point_history/point_latest写入、测点行锁权限、audit_log INSERT。MySQL8.0.33实测行锁需要相关UPDATE权限；只锁测点可按既有约定使用device_point.id列的UPDATE授权。不要给网页viewer对应数据库超级权限；网页登录身份并非数据库连接身份。

## 10. 本次验证和未验证项

- 后端Ruff检查、格式检查通过；独立MySQL8.0.33验收时，pytest共123项通过，其中11项实际连接专用MySQL实例。
- 覆盖阈值边界、持续异常、重复/迟到/陈旧/未来/低质量样本、恢复/确认的先后顺序、重复处置、快照不被配置覆盖、越权、只读、分页和参数校验。
- 实测并发触发只生成一条活动事件；并发确认仅一次审计；告警审计故障会回滚事件、最新值与历史。原账号补权限和重复补丁也已验证。
- 前端verify通过：地图及其省市滚轮行为、登录会话、监测、三维绑定、告警交互、类型与生产构建。原Cesium/Three大包提示仍存在。
- 测试只连接核对专用数据目录后的13316实例；完成后关闭。没有使用用户实际库，没有自动导入SQL、启动后台模拟或占用用户8000后端端口。
- 本轮未进行实际浏览器视觉验收，也没有现场设备数据验收。请你按第5—6节测试界面和真实配置。

下一主要模块是dashboard：先确认计量拓扑与指标口径，再按授权范围汇总有效新鲜测点，并显示缺失/陈旧数据覆盖情况；不能直接把总表和分表相加。
