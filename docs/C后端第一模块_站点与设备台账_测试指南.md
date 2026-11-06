# 后端第一模块：站点与设备台账测试指南

> 2026-10-15更新：台账现需Bearer认证并按站点范围过滤；请先按[C登录与账号开通_实现与测试指南.md](C登录与账号开通_实现与测试指南.md)登录。本文其余首模块步骤是历史基础说明。

日期：2026-10-14。项目根目录：`D:/study_software/PythonProject/smart_power_twin`。

## 1. 这一轮完成了什么

已按确认的根目录方案建立app/api、core、db、common及modules/assets。assets按router、schemas、service、repository、models分层，实现站点、设备、区域、路线的只读查询；保留原两个示例接口。已在现有Python 3.10虚拟环境安装运行和测试依赖。

你选择先用演示数据：默认进程内SQLite，启动创建并初始化，重启恢复。没有生成落盘数据库文件，也没有连接、导入或修改MySQL。前端代码、页面、Token及模型文件保持原样，仍使用原来的前端演示数据。

这是台账模块：回答“站点、区域、设备有哪些”，不是最新值、历史趋势、告警或场景绑定模块；额定参数不等于实时读数。当前不提供编辑删除，方便先测试身份、过滤和归属关系。

## 2. 启动与停止

打开PowerShell，依次执行：

```powershell
cd D:\study_software\PythonProject\smart_power_twin
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

保持窗口运行；打开 http://127.0.0.1:8000/docs 。接口页面选择GET接口，点Try it out，填参数，再点Execute；Response body是查询结果。

若8000端口已有本轮后台服务，直接打开即可，不要重复启动。手工终端启动时用Ctrl+C停止。若端口被其他程序占用，不要直接杀掉不明进程，可以把端口改为8001，访问地址相应改为8001。

最新状态：为解决重复启动冲突，Codex前一轮启动的后台服务已停止；热重载验证服务也已正常关闭，8000端口留给你自行启动。PyCharm和终端选择一种方式运行即可，不要同时启动两份。WinError 10013／10048是绑定端口问题，不是CORS；排查记录见同目录C后端启动端口冲突与跨域说明.md。

也提供脚本 `scripts/start_backend.ps1`，可使用 `& .\scripts\start_backend.ps1 -Port 8000`；若系统脚本策略阻止，直接使用上面的Python命令，无需修改全局策略。

## 3. 演示台账

| 站点ID | 名称 | 业务code | 类型 |
|---|---|---|---|
| 1 | 朝歌服务区 | HEBI_CHAOGE_SERVICE_DEMO | SERVICE |
| 2 | 朝歌收费站 | HEBI_CHAOGE_TOLL_DEMO | TOLL |

两站参考坐标沿用前端，省为410000、城市为鹤壁市、共同分组码为HEBI_CHAOGE_COMPLEX，演示关联S26，具体方向待核验。

每站3个演示区域：配电及储能区、光伏区、停车充电区；每站4台虚构演示设备：储能一体柜、箱式变压器、光伏阵列、直流充电桩。服务区设备ID为101—104，收费站为201—204。储能215kWh、变压器630kVA等均为样例参数，未核验现场配置。

每个业务响应meta明确dataSource=demo及演示说明；站点和设备的isDemo=true。ACTIVE只表示演示资产有效，不表示在线。

## 4. 建议按此顺序验收

| 步骤 | 请求（均在8000端口） | 应看到的结果 |
|---|---|---|
| 1 | `/api/v1/health` | status=ok，dataSource=demo，database=memory-demo |
| 2 | `/api/v1/sites` | total=2，朝歌服务区、朝歌收费站 |
| 3 | `/api/v1/sites?siteType=SERVICE` | total=1，仅服务区 |
| 4 | 在docs的sites接口填q=`鹤壁 朝歌 S26` | 两站；再填siteType=SERVICE则仅服务区 |
| 5 | `/api/v1/sites?page=2&pageSize=1` | 第二页一条，不与第一页重复 |
| 6 | `/api/v1/sites/1` | 服务区详情、参考坐标、路线方向UNKNOWN |
| 7 | `/api/v1/sites/1/devices` | 4台设备，所有siteId为字符串1 |
| 8 | `/api/v1/sites/1/devices?systemType=ESS` | 仅储能；ratedEnergyKwh=215 |
| 9 | `/api/v1/sites/1/devices/101` | 储能设备详情；无实时功率字段 |
| 10 | `/api/v1/sites/2/devices/101` | 404；设备不属于该站 |
| 11 | `/api/v1/sites/1/areas` | 3个演示区域 |
| 12 | `/api/v1/highways` | 一条S26业务路线，geometryUri为null |
| 13 | `/api/v1/sites?highway=G4` | 200空列表，不能误命中G40 |
| 14 | `/api/v1/sites/999` | 404 SITE_NOT_FOUND |
| 15 | `/api/v1/sites?pageSize=101` | 422 INVALID_ARGUMENT |

如果不熟悉Swagger，可直接把上面完整地址放进浏览器查看JSON；也可在PyCharm打开根目录test_main.http，逐项点击执行。HTTP文件含上述示例及预期结果。

## 5. 为什么暂时不改前端

现有前端ID是henan-service-01等字符串，后端正式数字ID使用字符串形式传输；页面还需要模型和测点，而本轮只完成台账。先单独验证模块，再接场景与监测接口，可以避免为了接一个模块改坏已经确认的地图、布局或三维展示。

## 6. MySQL切换准备

同一个模块已具备MySQL只读查询连接配置及5张表的ORM字段映射，本轮没有实际连接MySQL，不能把内存测试当作真实MySQL验收。

后续先核对实际site、site_area、device、highway_route、site_route_link是否与桌面19表SQL一致。准备只读账户后，将.env.example复制为根目录.env，本地填写SPT_MYSQL_HOST、PORT、DATABASE、USER、PASSWORD，改SPT_DATA_SOURCE=mysql并重启。密码不发到聊天、不放前端环境文件。

MySQL模式不会create_all、迁移或自动写演示数据；会设置连接UTC及只读事务。连接错误／缺表返回503，不静默改用演示库；数据库没有站点则返回空列表。当前没有登录与站点权限模块，仅本机访问，后续system模块完成后再扩展部署。

城市暂按SQL现有city_name筛选；省编码兼容41／410000，对外返回六位。公开设施ID、city_code、模型对象和电力读数本轮未擅自增表或填造。

## 7. 验证及后续

测试命令与检查结果见项目README和本轮收尾记录。用例使用全新内存库，覆盖查询、筛选、分页、BIGINT字符串、空值、跨站归属、参数边界、只读请求、错误脱敏、模式隔离和OpenAPI；真实MySQL连通与表结构待下一轮确认。

你完成本轮测试后，先根据反馈调整台账协议；下一步建议补最小system登录与站点权限，再接twin场景绑定，随后接monitoring最新值和历史，最后实现告警和汇总。
