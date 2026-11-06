# 后端代码注释与阅读指南

日期：2026-10-15。项目：`D:/study_software/PythonProject/smart_power_twin`。

本次完成现有后端的注释补充，不增加新业务模块，不修改原查询行为。后续新增或修改的模块继续遵循相同要求，已记录在根目录AGENTS.md。

## 一、注释在哪里看

1. 文件顶部三引号：本文件负责什么、与其他模块的分工以及能力边界。
2. 类和函数下方三引号：用途、参数、返回值、必要异常及规则。在PyCharm中悬停或打开文档提示也可查看。
3. 关键代码旁的井号注释：为什么要按此方式处理，例如批量查路线、JSON中文别名、只读模式、大整数和设备归属。
4. `Field(description=...)`：接口返回字段的中文含义、单位、可空值及身份规则，在OpenAPI文档中显示。
5. `Query`／`Path`及接口函数说明：请求参数含义、示例、范围、返回结果与失败条件。

不要只看注释猜功能是否已经完成；当前只有assets只读查询及其基础设施已实现，system、twin、monitoring、alarms、dashboard仍是后续模块。

## 二、推荐阅读顺序

| 顺序 | 文件 | 先理解什么 |
|---|---|---|
| 1 | `main.py`、`app/application.py` | 应用怎样启动，什么时候建立和释放数据库引擎 |
| 2 | `app/api/router.py` | 为什么所有业务接口有/api/v1前缀 |
| 3 | `app/modules/assets/router.py` | 用户能请求哪些查询，各参数怎么填写 |
| 4 | `app/modules/assets/schemas.py` | 接口返回什么字段，数字单位和null代表什么 |
| 5 | `app/api/dependencies.py` | 数据库会话、仓储和服务如何自动注入 |
| 6 | `app/modules/assets/service.py` | ID、省码、站点存在性和设备归属怎么处理 |
| 7 | `app/modules/assets/repository.py` | 组合检索、分页、路线去重和数据库查询怎么实现 |
| 8 | `app/modules/assets/models.py`、`app/db/base.py` | 五张台账表怎么映射，字段关系与时间含义 |
| 9 | `app/db/session.py`、`app/core/config.py` | 演示库与MySQL如何区分，哪些配置需要本地填写 |
| 10 | `app/core/exceptions.py` | 404、422、503分别为什么出现，怎样避免泄露内部信息 |
| 11 | `app/modules/assets/demo.py` | 两站、8台设备、6个区域的演示资料如何准备 |
| 12 | `app/common/`、`tests/`、`scripts/start_backend.ps1` | 公共状态、分页协议、测试范围及启动方法 |

上述路径相对于项目根目录。前端仍在smart_power_web，不直接连接MySQL；本轮未修改前端代码。

## 三、用一个接口理解各层

请求：`GET /api/v1/sites/1/devices?systemType=ESS&page=1&pageSize=20`。

```text
router：校验site_id、systemType和分页参数
    → dependencies：注入当前请求的Session与AssetService
    → service：确认站点1存在
    → repository：按所属站点和ESS系统查询，稳定排序、计数、分页
    → service：主键转字符串、组装额定参数和数据来源
    → schemas：按接口协议输出camelCase字段
```

这里site_id是站点数据库ID，不是站点名称或前端旧演示ID；systemType=ESS表示储能系统；page从1开始；pageSize是每页容量。额定215kWh不是当天用电，也不是实时SOC。不存在站点返回404；已有站点没有储能设备则返回200及空数组。

service参数由FastAPI注入，不需要在Swagger中填写；Session是一次请求使用的数据库会话，不是用户登录会话。

## 四、必须读懂的几个字段

| 字段 | 含义与注意事项 |
|---|---|
| id／siteId／deviceId | 十进制字符串主键，避免浏览器大整数精度丢失 |
| code | 业务编码，与数据库主键分开；设备编码在所属站点内唯一 |
| assetStatus | 有效、维护、停用或退役等生命周期；ACTIVE不能当在线状态 |
| ratedPowerKw | 额定有功功率，kW；不是当前功率 |
| ratedEnergyKwh | 额定储能电量，kWh；不是当日电量 |
| ratedCapacityKva | 额定视在容量，kVA；常用于变压器，与kW不同 |
| null | 未知、未填写或不适用；不能自动替换为0 |
| provinceCode | 接口标准六位省代码；兼容库中41／410000，不能填城市代码410600 |
| meta.dataSource | 本次查询来自demo还是mysql；MySQL来源不保证每条记录真实 |
| isDemo | 该站点／设备是否演示台账；目前默认演示库为true |
| total | 所有筛选条件应用后的总数，不是当前页长度 |
| directionCode | UP／DOWN／BOTH／UNKNOWN；未核验时保留UNKNOWN |

## 五、如何在接口页面查看说明

启动后端后打开 http://127.0.0.1:8000/docs 。

- 展开GET接口：顶部可看功能、参数含义、返回结果及异常说明。
- 点击Try it out：填写page、pageSize、siteType等输入，不需要填写service。
- 查看页面下方Schemas：展开SiteOut、DeviceOut、PageMeta等，可读各返回字段说明。
- API文档由代码生成；不要只改独立Markdown却忘记更新代码中的参数或字段描述。

本轮没有另外启动后台服务，避免与用户PyCharm重复占用8000。若正在运行的服务没有自动重载，请自行停止并重新运行一次后查看更新说明。

## 六、以后每个模块的注释要求

- 文件：说明模块用途、所属业务、依赖及不承担的职责。
- 函数：说明实际参数名、默认行为、返回类型／结构、关键异常；简单函数简明说明，复杂业务展开规则。
- 字段：写清ID与业务编码区别、单位、时区、状态值、空值和来源。
- 关键规则：解释为什么这样做，例如G4精确匹配、迟到数据不能覆盖最新值、确认不等于恢复；避免只翻译语法。
- 变更：代码行为变动时同步修改说明，不保留过期注释；尚未实现的能力明确标注规划。
- 前端：后续新增或修改页面、组件、服务和状态模块时，也按职责、主要参数／事件／返回值及必要边界补充说明。

## 七、本次验证

43项原有测试、Ruff和格式检查通过；23个应用Python文件、26个类、50个函数均具有说明。接口字段说明经生成OpenAPI检查，启动脚本语法与帮助解析通过。

对25个应用及测试Python文件进行了忽略注释、文档字符串与description元数据的语法结构比对，未发现业务结构变化。没有改查询条件、默认值、数据库字段类型、事务逻辑或前端，也未连接真实MySQL。
