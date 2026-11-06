# 电力监测模块：实现与测试指南

更新日期：2026-10-16。项目：`D:\study_software\PythonProject\smart_power_twin`。

> 后续状态更新：twin三维绑定也已完成，2026-10-18起当前启动检查19表，增加告警模块，参见最新告警指南。前端固定模型键→设备编码映射已移除，监测组件改接数据库对象的deviceId和绑定pointIds；原监测读数、历史、采集与质量规则保留。场景管理与权限见《C三维场景与测点绑定模块_实现与测试指南.md》，本说明保留监测初次接入时的记录。

## 1. 这次完成了什么

按模块顺序完成monitoring电力监测。当前正式启用的后端模块为：system账号权限、assets台账查询、monitoring电力监测。

- 查询设备测点：名称、单位、类型、采样周期、陈旧阈值及启用状态。
- 查询最新读数：数值/文本、源时间、接收时间、质量、是否陈旧及模拟/现场来源。
- 查询原始历史，以及1分钟、5分钟、1小时聚合；范围与返回数量有上限。
- 接收采样批次：重复采样去重、内容冲突拒绝、迟到数据只进历史、整批事务回滚。
- 新建测点与配置周期/阈值/启用状态；单位和数据类型不会被配置接口偷偷改变。
- 站点三维页右侧设备面板接入MySQL最新值及历史曲线。
- 提供独立模拟采集脚本，默认不发送，显式`--send`才写模拟站点。

初次接入时threshold仅保存配置。2026-10-18起，twin和alarms均已启用，采样最新值推进时会按新鲜GOOD数值评估阈值告警；具体边界及C06权限补丁见《C告警模块_实现与测试指南.md》。dashboard仍未启用。前端现有GLB、地图、朝歌配对、返回路径、合并页头、字体、海蓝主题、登录刷新恢复均保留。

## 2. 你现在怎样测试

### 第一步：确认表与数据

已导入上一轮19表结构及全模块模拟数据，可直接使用，不用重建或重新导入采样。

若只有原账号/台账11表，先执行同目录 `C00监测模块_仅缺表时使用.sql` 补3表，再按全模块模拟数据说明补测试数据。已有同名旧表的字段不会被这个文件修复；启动发现结构不符会明确停止，不自动改库。

本次后端启动检查从11表扩大到14表，新增：`device_point`、`point_latest`、`point_history`。其余5表仍不纳入监测启动要求。

### 第二步：网页账号权限

你原来使用 `mysql_admin` 或 `mysql_viewer` 时，在MySQL工具中完整执行：

`C03监测模块_权限初始化.sql`

这会为原ADMIN角色新增监测查询、采样提交、测点配置三项动作，为原VIEWER角色新增监测只读动作，不修改密码、账号状态或站点范围。补丁带事务及固定审计标记；首次成功后，重跑不恢复人工撤销的权限。

如果用上一轮的 `sim_admin`、`sim_operator`、`sim_viewer`，它们本来已有监测权限，不必须执行这个补丁。权限更改后退出前端重新登录，保证前端当前用户信息更新。

**不要重新执行旧账号初始化文件来获得新权限。** 旧文件针对首期五权限角色做了安全预检，角色已扩展后可能报EXISTING_ROLE_HAS_EXTRA_PERMISSIONS；后续使用本模块权限补丁即可。

### 第三步：启动并查看前端

在项目根目录只启动一个后端：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_backend_mysql
```

也可在PyCharm按原方式启动`main:app`。前端进入`smart_power_web`运行`npm.cmd run dev`，然后登录。

进入河南→鹤壁→朝歌服务区或收费站，点击模型设备或左侧设备列表。右侧“设备监测·MySQL”显示数据库中的四个测点，并能切换历史测点与1小时/24小时/7天范围。

这里的历史范围以所选测点**最新采样时刻**为终点，明确显示具体时间。因此昨天导入的静态快照仍可看历史，但读数会标记“数据陈旧”，不会假装是现在的实时数据。

“刷新”重新查询；勾选“30秒自动刷新”才定时查询，浏览器标签页不可见时暂停查询。刷新不会自动生成新采样。

### 第四步：需要动态数据时再运行采集工具

只看已有数据不需要开启写入。需要提交新采样时，后端本地配置必须允许业务写入：

```dotenv
SPT_MYSQL_ALLOW_WRITES=true
```

配置位于项目根目录 `.env.mysql.local`，修改后重启后端。MySQL连接账号也需要相应权限：读取已启用14表，向监测三表INSERT/UPDATE及audit_log INSERT。已有账号管理的写权限仍按原配置；应用不会替你GRANT数据库权限。只读开关未开启时接口返回409 MYSQL_READ_ONLY，属于预期保护行为。

先查看计划，不登录、不联网、不写数据库：

```powershell
.\.venv\Scripts\python.exe -m scripts.simulate_telemetry
```

实际生成一批朝歌服务区模拟采样：

```powershell
.\.venv\Scripts\python.exe -m scripts.simulate_telemetry --send --username sim_operator --cycles 1
```

脚本会提示输入**网页账号密码**，输入不回显、不保存。不要填写MySQL连接密码。

持续模拟（15秒一批，Ctrl+C停止）：

```powershell
.\.venv\Scripts\python.exe -m scripts.simulate_telemetry --send --username sim_operator --cycles 0 --interval 15
```

其他参数：

| 参数 | 用途 |
| --- | --- |
| `--site-code HEBI_CHAOGE_TOLL_DEMO` | 改为朝歌收费站，必须已授权且是模拟站点 |
| `--scenario normal` | 正常模拟值，默认；储能可正负功率，光伏随北京时间昼夜变化 |
| `--scenario hot` | 充电桩温度62.1°C，用于监测展示，尚不生成告警 |
| `--scenario bad` | 光伏功率质量BAD、读数NULL，用于缺测展示 |
| `--api-url http://127.0.0.1:8000` | 本机API地址，拒绝远端地址及重定向 |

工具按真实查询到的数字ID采集，不假定ID是1或101；不会直连MySQL，不读取.env、真实Token或账号初始密码文档。累计电量从现有表底向上递增，不将时间戳当作电量。

一次性SQL中的测点建议周期仍为15分钟、陈旧阈值30分钟。模拟器的15秒用于快速演示，不自动更改这些定义。若要测试“停止采集后很快变陈旧”，可用sim_admin在Swagger完整提交较短的配置，例如sampleIntervalMs=5000、staleAfterMs=15000，再停止采集并刷新。配置接口是完整替换，应同时填回需要保留的阈值和enabled，不要只提交周期而误清阈值。

## 3. 六个接口怎样使用

后端文档地址：`http://127.0.0.1:8000/docs`。先调用登录接口，复制accessToken到Authorize，不要把密码填到Authorize里。

先从`GET /api/v1/sites`取得站点ID，再从`GET /api/v1/sites/{siteId}/devices`取得设备ID；不要用前端的`henan-service-01`作数据库ID。

| 方法与路径（均带/api/v1前缀） | 功能 | 动作权限 |
| --- | --- | --- |
| GET /devices/{deviceId}/points | 测点定义，含测点ID与单位 | monitor:read |
| GET /devices/{deviceId}/latest | 最新值、质量、源时间、陈旧状态 | monitor:read |
| GET /points/{pointId}/history | 有界历史及聚合 | monitor:read |
| POST /telemetry/batches | 整批采样入库 | telemetry:write＋写开关 |
| POST /devices/{deviceId}/points | 新建定义，不生成假读数 | monitor:configure＋写开关 |
| PUT /points/{pointId}/config | 完整替换周期/阈值/启用配置 | monitor:configure＋写开关 |

每个接口都校验站点范围；知道其他站点设备/测点ID也不能越权查询。未知和未授权统一404；无动作权限403；未登录或失效401。

新建测点示例：

```json
{
  "code": "cabinet_temperature",
  "name": "柜内温度",
  "unit": "°C",
  "valueType": "NUMERIC",
  "aggregationType": "INSTANT",
  "sampleIntervalMs": 5000,
  "staleAfterMs": 15000,
  "enabled": true,
  "alarmLow": null,
  "alarmHigh": 55,
  "directionConvention": null
}
```

新测点创建后会在设备监测和历史选择中出现；模拟采集工具只认识约定编码，不会自动为自定义指标编造值。可以通过采样接口提交自定义测试值。

采样示例，把pointId换成查到的测点ID，sampledAt换成你的当前时间：

```json
{
  "source": "SIMULATED",
  "samples": [
    {"pointId": "你的数字测点ID", "sampledAt": "2026-10-16T15:30:00+08:00", "sourceSequence": "1", "valueNumeric": 28.6, "valueText": null, "quality": "GOOD"}
  ]
}
```

source必须与设备isDemo匹配。样本身份是`pointId＋sampledAt（规范到UTC毫秒）＋sourceSequence`；相同身份重传保持原内容。再次提交不同值会返回409 SAMPLE_CONFLICT，不悄悄覆盖旧历史。新时刻提交新样本；同一时刻的修订需使用更大序号。

sourceSequence响应始终为字符串，避免JavaScript大整数精度损失。SampleIn拒绝NaN/无穷、混合数值与文本、错误布尔值和超过服务器时间5分钟的采样；BAD允许无值。

历史请求参数：

- startTime/endTime必须带时区，查询`[开始,结束)`，最长31天。
- grain为raw/1m/5m/1h；raw最多2000条，超出返回hasMore=true。
- 聚合最多读取1万条原始记录，超过返回413，需缩小范围。
- INSTANT数值按GOOD样本求均值；COUNTER、文本及状态取桶末值，累计电量不能求和。
- 同一采样时刻聚合仅采用最大源序号；BAD或缺口不补0。前端曲线也会在BAD/缺测间隔断开。

## 4. 以后想修改，去哪些文件

| 文件/目录 | 负责什么 |
| --- | --- |
| app/modules/monitoring/models.py | 三张表映射与字段说明 |
| app/modules/monitoring/schemas.py | 参数/响应、单位/空值/ID说明，Swagger可查看 |
| app/modules/monitoring/router.py | 六个HTTP接口及动作权限 |
| app/modules/monitoring/service.py | 类型/来源校验、幂等、锁定、事务、最新排序、历史聚合 |
| app/modules/monitoring/repository.py | 设备测点、最新值和有界历史查询 |
| app/db/validation.py | 14张启用表的只读启动预检 |
| scripts/simulate_telemetry.py | 独立模拟采集工具，禁止在应用启动时自动运行 |
| smart_power_web/src/services/monitoringService.ts | 请求协议、授权站点/设备查找 |
| smart_power_web/src/types/monitoring.ts | 前端监测数据类型 |
| smart_power_web/src/components/twin/DeviceMonitoring.vue | 最新值、质量/陈旧提示、历史范围、曲线与刷新 |
| smart_power_web/src/utils/monitoringPresentation.ts | 数值格式与曲线缺口/同时间修订处理 |
| smart_power_web/src/views/SiteView.vue | 站点页组件接入点 |
| tests/test_monitoring.py | 监测业务与采集工具离线测试 |
| tests/test_full_mock_data.py | 真MySQL并发采样与权限补丁等集成验收 |

主要文件和函数均有中文用途、参数或规则说明。保持.vue文件template→script→style顺序。

最新实现已移除初次接入时的固定模型键→设备编码映射，由twin_scene/twin_object/twin_binding返回deviceId和pointIds。监测组件只显示当前对象绑定的测点，不把同设备所有指标默认当成已绑定。

## 5. 页面上哪些已经来自数据库

私有授权站点的右侧“设备监测·MySQL”中的读数和历史来自监测接口。未绑定台账的公开设施仍使用标注清楚的通用模板示意，不请求其他私有站点数据。

站点总负荷、能耗分析、左侧模板状态和告警演示仍是明确标注的样例；不要把它们和新监测卡混认为同一来源。大屏汇总和告警后续分别接入，避免现在直接相加不同测量边界的功率或伪造告警闭环。

切换站点、设备、账号、权限或历史范围时，迟到响应会丢弃；请求失败清除当前监测数据并提示，不回退到固定演示数字。前端暂存仅为当前组件状态，不缓存密码、读数或新增登录凭据。

## 6. 验证结果与边界

2026-10-16后端ruff检查、格式检查通过；开启专用隔离MySQL8.0.33后pytest共93项通过，其中8项MySQL集成用例。验证了4并发采样只插入一次、毫秒时刻与大源序号、迟到不覆盖、内容冲突、只读拒写、权限补丁重复不恢复撤权、旧账号及全表模拟数据保护。监测采样不写alarm_event。

前端`npm.cmd run verify`通过：Vue类型检查、生产构建、监测0/空值与断线规则、真实SFC内存渲染器下的设备/历史迟到响应隔离和权限撤销清空，以及已有地图层级、滚轮、布局、朝歌导航、登录刷新回归。构建仍有Cesium/Three大包提示，后端有已有依赖弃用提示，不影响本次检查通过。

浏览器预览受现有访问策略限制，本轮未做实际浏览器画面验收；内存组件检查不是视觉验收。你可以按第二节检查实际右侧面板的字号和滚动效果。

没有连接/修改你的实际数据库、配置密码或自动导入权限；所有数据库执行测试都在专用13316端口和隔离数据目录。需要你手动执行的SQL已放桌面“智慧电力文档”。

## 7. 下一步

先测试本模块。接下来是twin三维场景与测点绑定：把目前写在前端的样板对象映射改为数据库场景/对象/测点绑定，并保持同站同设备约束。然后完成alarms告警，最后dashboard汇总。本轮到监测模块完成为止，不继续注册后三个模块。
