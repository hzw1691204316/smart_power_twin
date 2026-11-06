# C大屏汇总模块：实现与测试指南

更新日期：2026-10-18。项目：`D:/study_software/PythonProject/smart_power_twin`。

## 1. 当前做到哪个模块
系统六个基础业务模块已完成首轮可测试实现：

| 模块 | 已实现 | 仍需完善 |
| --- | --- | --- |
| system | MySQL登录、账号开通、角色动作、站点范围、账号状态、操作审计 | 部署环境下的认证加固与统一账号体系 |
| assets | 站点、设备、区域、路线的授权查询 | 台账新增/编辑/停用、经核验资料批量导入 |
| monitoring | 测点维护、采样入库、最新值、历史查询、质量/陈旧标识、幂等与乱序处理 | 公司采集接口、协议与设备点表对接 |
| twin | 数据库发布场景、模型对象与设备/测点绑定、草稿保存和发布、模型定位 | 从零创建站点场景的管理UI、真实设备资料和模型配准 |
| alarms | 数值上下限触发/恢复、查询、确认、关闭、设备定位 | 通信中断规则、延时/回差、复杂规则、通知与工单 |
| dashboard（本轮） | 全国/省/市/站点的授权汇总，现场/模拟来源隔离，计量覆盖、设备数据状态、事件数量 | 配置代表计量点、日计量边界、跨站聚合历史曲线和自给率等分析 |

“首轮实现”不代表上述后续能力已完成。下一步建议先补台账维护与公司数据接口，拿到资料后再做计量和趋势扩展。

## 2. 本次页面变化
1. 全国页面的台账统计和并网/光伏代表功率改用数据库查询。
2. 河南省/地市页右侧增加“业务能源汇总”，随行政范围变化。
3. 私有站点三维页的功率摘要与左侧统计改用本站数据库汇总，右侧设备监测继续按发布场景绑定读取。
4. 全国、省市页面的原固定示意功率曲线移除，不伪装成历史聚合结果。
5. 公开通用模型和大型服务区方案保留原来边界：不请求私有大屏，不显示不存在的本站实时数据。
6. 共享汇总组件支持“现场数据/模拟数据”切换与手动刷新，默认现场。切来源后旧数据立即清空。
7. 页面刷新不会启动采集；汇总没有自动轮询。设备值变旧后，点击刷新重新判断有效性。

地图外观、全国/省市下钻、省市固定滚轮朝向、浮动侧栏、模型规模切换、大型服务区快捷入口和登录刷新会话继续保留。

## 3. 你如何测试

### 第一步：准备权限
已有ADMIN/VIEWER网页角色的用户，在MySQL中手动执行本说明同目录的：
`C08大屏汇总模块_权限初始化.sql`

只新增`dashboard:read`权限并关联原ADMIN/VIEWER角色，不改密码、不扩站点范围，不给用户创建新账号。重复执行会补回本脚本声明的权限，主动撤权后不要再次运行。

sim_admin、sim_operator、sim_viewer原全模块素材已经有dashboard:read，通常无需执行C08。自定义角色需要维护者明确授予dashboard:read；脚本不会自动给其他角色授权。

SQL只由用户手动执行，后端启动不建表、不导入。本模块不增加数据库表，继续复用19表。

### 第二步：启动与查看
重启现有后端，刷新前端，并退出后重新登录，以刷新前端权限。

- 全国概览：右侧“能源观察”查看汇总。
- 河南路网：右侧“业务能源汇总”；切换地市核对范围。
- 朝歌等授权台账站点三维：左侧“本站业务汇总”，顶部显示代表功率和所选来源设备数。
- 模型库“大型服务区”：仍为方案预览，明确未接入，不读私有统计。

默认“现场数据”。若库里是模拟设备，现场功率可能为“—”、设备数为0，这是正确的来源隔离。切换“模拟数据”后查看模拟设备；站点总数仍是全部授权台账数。

### 第三步：验证新鲜读数
旧C01模拟脚本是固定历史快照，时间过久不会参与当前功率汇总。可用已有模拟采集工具给授权朝歌站发送一批当前数据：

```powershell
.\.venv\Scripts\python.exe -m scripts.simulate_telemetry --username admin --site-code HEBI_CHAOGE_SERVICE_DEMO --scenario normal --cycles 1 --send
```

username请换成实际有采样写入权限的网页账号（例如你的管理员或sim_admin）。工具会在本机隐藏输入密码；不要把密码放到聊天或命令中。`--send`才会提交，否则只预览。它只支持已标明模拟的设备，不会给现场设备注入模拟值。

发送后在页面选择“模拟数据”，点“刷新”。超过测点staleAfterMs后再次刷新，过期功率回到“—”，不会保持假实时读数。

## 4. 功率到底怎么算
当前各站各系统只允许一个唯一、已启用的代表测点：

| 条件 | 要求 |
| --- | --- |
| 测点编码 | `active_power` |
| 单位 | `kW`，不把W直接当kW，也不把kWh当功率 |
| 值类型 | `NUMERIC` |
| 聚合类型 | `INSTANT`，不能把累计表底相加 |
| 台账 | 站点和设备都为ACTIVE |
| 来源 | 按设备is_demo判断，所选FIELD或SIMULATED，不混加 |
| 质量 | 只有GOOD |
| 时间 | 采样不在未来，且距服务端计算时刻不超过本测点stale_after_ms |
| 值 | 非空、有限数；0有效，正负号保留 |

四个系统分别计算：GRID配电并网点、PV光伏、ESS储能、CHARGING充电。

GRID字段叫“并网点代表功率”，不是“全站总负荷”。光伏、充电、储能可能位于总表下级，四个数字不能直接相加；负功率的物理意义取决于设备点表约定，不擅自转换成发电或用电。

同站同系统有两个以上启用active_power候选时，当前无法判断它们是总表/分表还是重复计量，会排除该站该系统并计入ambiguousSites。即使其中一个质量坏或单位不对，也不会凭剩下一个读数推断计量边界。

这是一项保守的初始口径。未来应由维护者配置代表测点/计量边界；不能为了让数字显示出来而删除真实测点或乱改设备分类。

## 5. 覆盖、空值与状态
- `valueKw=null`在页面显示“—”，不是0。
- `contributingSites/eligibleSites`表示有效站点贡献覆盖；分母为筛选后ACTIVE台账站点数。
- 未配置该系统、无读数、过期、质量不合格、错误单位和计量歧义都会导致缺贡献；覆盖不是设备故障率。
- `ambiguousSites`包含在`missingSites`中，不可重复加总。
- `isPartial=true`表示覆盖不足或无法计算；空范围也不能冒充完整0功率。
- 各站采样不一定同刻，返回参与值最早/最晚采样时间；`asOf`只是汇总计算时间。
- `dailyEnergyKwh`当前始终null：日计量边界、时区和表底重置/换表规则尚未配置，不用kW简单相加或把累计表值当今日电量。

设备状态是所选来源的数据状态，不是现场故障诊断：

| 状态 | 规则 |
| --- | --- |
| normal 数据正常 | 有效站点/设备至少有一条启用、GOOD、新鲜且非空采样，无活动告警 |
| warning 关注 | 有效站点/设备有ACTIVE事件；人工确认并不会恢复 |
| offline 无有效新值 | 有测点但无有效新鲜采样，可能未采集、低质量或过期；不能直接断言现场离线 |
| unknown 未知 | 没有启用测点，或台账停用/维护/退役 |

活动事件数只数ACTIVE。待确认事件数数未关闭且未确认的事件，因此已恢复但未确认仍计数；两者不是互斥分组。已CLOSED的事件不参与。

## 6. 接口与字段

`GET /api/v1/dashboard/summary`

必须Bearer登录、有dashboard:read，并限制在当前账号站点范围。

| 参数 | 说明 |
| --- | --- |
| provinceCode | 可选41或410000，不接受410100这样的城市编码 |
| cityName | 可选郑州/郑州市、鹤壁/鹤壁市，和省筛选取交集；空白422 |
| siteId | 可选数据库主键字符串，未授权或不存在404，不能用前端henan-service-01替代 |
| source | FIELD现场（默认）或SIMULATED模拟，其他值422 |

示例：
```http
GET /api/v1/dashboard/summary?provinceCode=410000&cityName=鹤壁市&source=SIMULATED
Authorization: Bearer <登录令牌>
```

响应沿用`{data,meta}`，meta.dataSource表示数据库来源；data.source表示选定的设备/功率来源，MySQL不等于全部现场数据。

- siteCount/demoSiteCount/activeSiteCount/serviceCount/tollCount：授权台账站点统计，含所有来源。
- deviceCount/deviceStates/activeAlarmCount/unacknowledgedAlarmCount：只含所选设备来源。站点级无设备事件按站点is_demo区分。
- power.GRID/PV/ESS/CHARGING：valueKw、contributingSites、eligibleSites、missingSites、ambiguousSites、isPartial、oldestSampledAt、newestSampledAt。
- asOf、source、dailyEnergyKwh、note。

无权限403；无登录401；无授权范围返回空统计，不退回全库。查询只读，即使业务写入开关关闭也能访问。

## 7. 代码结构，方便你后续修改

| 文件 | 职责 |
| --- | --- |
| app/modules/dashboard/router.py | 查询参数、权限入口、响应协议 |
| schemas.py | 字段含义、来源、单位和可空值的OpenAPI说明 |
| repository.py | 先限定站点授权，再按省市与设备来源批量查询 |
| service.py | 有效采样、唯一代表点、功率覆盖、设备状态和告警计数规则 |
| app/api/router.py | 注册dashboard路由 |
| smart_power_web/src/types/dashboard.ts | 前端协议 |
| src/services/dashboardService.ts | HTTP查询，站点code解析成授权数据库ID |
| src/composables/useDashboardSummary.ts | 加载/失败/来源/范围与竞态隔离，不自动轮询 |
| src/components/dashboard/DashboardSummaryPanel.vue | 可复用统计组件，展示0/缺数/负数、覆盖和采样时间 |
| src/views/OverviewView.vue、ProvinceView.vue、SiteView.vue | 全国、省市、私有站点接入 |
| sql/C08大屏汇总模块_权限初始化.sql | 用户手动授权补丁 |
| tests/test_dashboard.py | 规则、权限、范围、空值和时间边界验收 |
| tests/test_full_mock_data.py | 隔离真实MySQL大屏只读与权限补丁验收 |
| smart_power_web/scripts/check-dashboard.mjs | 状态竞态与真实Vue组件输出验收 |

所有新增模块有中文职责/参数说明；Vue文件继续template、script、style顺序。

## 8. 本轮验证与限制
- 前端完整verify覆盖原地图、模型、会话、监测、三维、告警及新增大屏状态/组件测试，类型检查与生产构建通过。
- 后端139项测试通过，其中12项在13316专用隔离MySQL运行；Ruff检查与格式检查通过。
- 验证来源不混加、0/负数、过期与未来值、质量、单位、重复候选、停用、空授权及跨站404。
- 验证只读数据库账号可查询、旧账号补权不改账号/密码/范围、模拟观察员只能统计一站、撤销范围立即生效。
- 未连接/写入用户3306数据库，测试专用实例已关闭。
- 本轮未进行真实浏览器视觉验收；Vue组件输出与构建通过不替代实际屏幕验收。
- 仍有原有Starlette测试依赖弃用和Cesium/Three构建体积提示，不影响本轮测试通过。
- 本轮不计算跨站历史聚合曲线、日用电、自给率或完整能量平衡；单测点历史继续使用已有monitoring接口。
