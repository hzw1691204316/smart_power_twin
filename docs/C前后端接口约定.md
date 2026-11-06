# 前后端接口约定：台账及后续模块入口

更新：2026-10-19。台账查询纳入Bearer认证及站点范围；前端按授权业务code过滤场景。monitoring已接入，六个监测接口、参数、来源和新鲜度规则详见[C电力监测模块_实现与测试指南.md](C电力监测模块_实现与测试指南.md)。本文下方仍为assets台账协议。

三维七接口与场景版本/绑定ID协议见[C三维场景与测点绑定模块_实现与测试指南.md](C三维场景与测点绑定模块_实现与测试指南.md)。私有模型由当前发布场景选择，monitoring仅展示所选对象绑定的测点。

2026-10-18补齐三维配置页/admin/scenes与三个接口：GET /scene-templates/{template_id}/objects、POST /sites/{site_id}/scenes/from-template、PUT /scenes/{scene_id}/objects。详见[C三维场景创建与配置_实现与测试指南.md](C三维场景创建与配置_实现与测试指南.md)。从模板创建支持新站，原POST /sites/{site_id}/scenes仍为复制当前发布版；同键对象保留ID，已有绑定时禁止直接删除对象或换设备。复用twin:read/twin:publish及站点范围，不新增表。

告警四接口、阈值评估与确认/恢复/关闭协议见[C告警模块_实现与测试指南.md](C告警模块_实现与测试指南.md)。私有站点使用数据库事件，公开模板不请求私有告警。

大屏接口`GET /api/v1/dashboard/summary`已启用：需dashboard:read，按站点权限及省市/站点交集查询，source=FIELD（默认）或SIMULATED。字段与计量/覆盖规则见[C大屏汇总模块_实现与测试指南.md](C大屏汇总模块_实现与测试指南.md)。站点数含全部授权台账，设备/功率/事件按来源隔离，缺测null不补0。

新增台账维护四接口（POST站点/设备，PUT站点/设备），身份字段创建后固定、写入和审计同事务，详见[C站点与设备台账维护_实现与测试指南.md](C站点与设备台账维护_实现与测试指南.md)。旧查询响应不得整份作为PUT请求。

## 协议

2026-10-19新增站内关系维护：POST /sites/{site_id}/areas、PUT /sites/{site_id}/areas/{area_id}、POST /sites/{site_id}/routes、PUT /sites/{site_id}/routes/{link_id}；需site:read+asset:manage+本站范围。SiteOut.routes补齐siteId/linkCode/areaId/chainageM/accessType；chainageM单位米，未知null，0有效。区域防环、主关联互斥，编码创建后固定；公共路线/地图几何不修改。详见[C区域与高速关联维护_实现与测试指南.md](C区域与高速关联维护_实现与测试指南.md)。

测点维护前端入口 `/admin/points` 已接入已有GET /devices/{device_id}/points、POST /devices/{device_id}/points、PUT /points/{point_id}/config，无新增后端接口。PointConfigInput只提交sampleIntervalMs/staleAfterMs/enabled/alarmLow/alarmHigh；身份/单位/类型固定，阈值空为null，0与负数保留。详见[C测点管理页面_实现与测试指南.md](C测点管理页面_实现与测试指南.md)。

- 前缀 `/api/v1`，响应JSON字段使用camelCase。
- 所有数据库主键用字符串传输，避免JavaScript BIGINT精度丢失。ID从查询返回取得，不要求从1开始，也不是前端原有`henan-service-01`等ID；通过稳定业务code关联，不直接覆盖前端路由。
- 成功响应为`data`与`meta`。正式`meta.dataSource`为mysql，自动化测试注入时为test；`meta.notice`描述来源与限制；记录的`isDemo`说明台账是否为演示。
- 列表分页响应额外含`meta.total`、`page`、`pageSize`、`hasNext`。page从1开始，pageSize为1—100，page最高10000；超过末页返回空data，total仍为筛选后的总数。
- 422为参数错误，404为站点不存在或设备不属于本站，503为数据库查询失败。错误体`error.code`与`error.message`；参数错误可含details，不回显密码等原始输入。
- 资产状态与在线状态分开：assets返回`assetStatus`和额定参数，采样读数/质量/陈旧状态由monitoring接口提供，不混入台账字段。

## 站点

`GET /api/v1/sites` 查询参数：

| 参数 | 含义 |
|---|---|
| q | 最长120字符；空格关键词同时满足，可匹配名称、编码、城市、别名及关联路线 |
| siteType | SERVICE服务区、TOLL收费站 |
| scale | S、M、L |
| provinceCode | 41或410000；底层兼容两种存法，对外六位；不接受城市编码410600 |
| cityName | 鹤壁或鹤壁市；当前数据库只有城市名称字段 |
| highway | 如S26、G4；大小写归一后精确匹配路线身份 |
| status | ACTIVE、INACTIVE、RETIRED；资产生命周期 |
| page / pageSize | 页码与每页数量 |

空查询返回当前账号授权范围内的台账；多个筛选条件同时满足；`%`、`_`是字面字符，不是搜索通配符。路线存在多条方向关联时不重复计算站点。未登录401，无动作权限403，未授权具体站点与不存在均404。

`GET /api/v1/sites/{site_id}` 返回站点及routes，含id、code、name、siteType、scaleLevel、complexCode、provinceCode、cityName、longitude、latitude、coordinateSystem、locationSource、isDemo、assetStatus。未核验或无坐标时可以为null，不能当0坐标。

routes含关联id、routeId、routeCode、name、directionCode、directionLabel和isPrimary。演示两站方向是UNKNOWN，不伪造上下行。

## 设备与区域

`GET /api/v1/sites/{site_id}/devices` 支持q、page、pageSize、systemType、status。systemType为PV、ESS、CHARGING、GRID、LOAD、AUX；status为ACTIVE、MAINTENANCE、INACTIVE、RETIRED。

设备字段含id、siteId、areaId、parentDeviceId、code、name、deviceType、systemType、assetStatus、ratedPowerKw、ratedEnergyKwh、ratedCapacityKva、manufacturer、modelCode、isDemo。额定参数用JSON数字，未知为null；额定kW、储能kWh、变压器kVA分开。不返回powerKw等实时数据或objectKey等未来twin模块内容。

`GET /api/v1/sites/{site_id}/devices/{device_id}` 在本站范围查询；设备存在但属于别站，也返回DEVICE_NOT_FOUND。

`GET /api/v1/sites/{site_id}/areas` 返回区域数组，字段id、siteId、parentId、code、name、areaType；当前为平铺列表，父子关系由parentId表达。设备/区域均无数据时：存在的站点返回空数组，不存在的站点返回404。

## 路线与健康检查

`GET /api/v1/highways` 支持q、page、pageSize，返回id、routeCode、name、status、geometryUri、coordinateSystem。默认演示库仅一条S26业务关联；不替代前端全省GeoJSON。

`GET /api/v1/health` 含status、module、dataSource、database、accessMode和authenticationImplemented。正式运行仅MySQL，database为配置库名；自动化测试显式注入时为isolated-test。健康检查执行只读SELECT 1，连接失败返回503。

## 后续前端适配

siteType与前端现有type、scaleLevel与scale、cityName与city等需要在services中明确转换。页面读取MySQL前先确定旧演示ID到正式站点ID映射、当前发布场景与模型地址来源、测点协议。不能把当前台账接口的ACTIVE直接映射成normal在线。

CORS仅允许localhost:5173与127.0.0.1:5173的GET/POST/PUT及Bearer头。账号、角色及站点范围授权已启用，仍限定本机测试。
