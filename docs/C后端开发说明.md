# 后端开发说明与本轮验收记录

> 2026-10-18最新状态：system/assets/monitoring/twin/alarms/dashboard六个基础模块已启用，共19表，最新版以《C大屏汇总模块_实现与测试指南.md》及README为准。以下为阶段历史记录。

> 2026-10-16状态更新：当前正式运行仅MySQL，已启用system、assets、monitoring共14表；三维绑定、告警、大屏尚未启用。当前启动、SQL准备和测试以《C电力监测模块_实现与测试指南.md》及README为准。以下为2026-10-14第一模块历史记录，旧demo配置不再支持，不按其中旧启动示例操作。

日期：2026-10-14。采用根目录main.py与app的方案，不新增backend目录。

## 已实现范围

第一模块为assets站点与设备台账只读查询。基础目录api、core、db、common已经为该模块建立；system、twin、monitoring、alarms、dashboard尚未实现，不创建空壳冒充完成。

主要文件：

- main.py：创建应用；app/application.py管理生命周期、基础接口、本机访问限制和CORS。
- app/api/router.py：统一/api/v1；dependencies.py提供请求级Session及assets服务。
- app/core/config.py：读取SPT_配置，默认demo；exceptions.py提供明确且不泄露数据库细节的错误。
- app/db/base.py与session.py：ORM基类、内存演示库及可配置的MySQL只读连接。
- app/modules/assets/models.py：已有5张台账表的查询映射；schemas.py为响应协议；repository.py为只读查询；service.py为身份、归属及响应组装；router.py为接口；demo.py为独立演示资料。
- tests/test_assets.py：本轮自动检查；test_main.http：手工测试请求。

## 本轮检查结果

- 43项pytest检查通过：搜索、组合过滤、中文JSON别名、字面通配符、稳定分页、路线精确匹配及关联去重、额定参数、设备归属、空态、输入范围、BIGINT字符串、无符号边界、只读请求、错误脱敏、OpenAPI及模式隔离；新增两个前端Origin的GET和OPTIONS检查、不允许的Origin／写方法检查，以及数据库错误仍保留CORS头的检查。
- Ruff代码与格式检查通过；pip依赖一致性检查通过。
- 逐项核对ORM与桌面SQL：site的20列、site_area的8列、device的17列、highway_route的12列、site_route_link的12列名称完全匹配。仅核对源文件，未核对真实数据库实例或执行建表。
- 实际启动127.0.0.1:8000后，通过HTTP验证健康、两站查询、4台服务区设备、组合检索、OpenAPI、docs返回200，以及跨站设备查询返回404。
- 前端src及package文件共55个SHA256与修改前一致；本轮未编辑前端、Token或原GLB。
- 测试环境保留一条Starlette针对HTTPX兼容测试客户端的弃用提示；测试通过，运行接口不依赖该测试客户端。后续统一框架版本时再升级测试适配。

后续启动问题已处理：8000被前一轮Codex后台服务占用，已确认父子进程归属后停止。Windows未列出TCP排除端口范围。实际以--reload热重载方式在8000启动成功，GET、OPTIONS跨域响应均通过；验证后用Ctrl+C正常关闭，不保持后台服务。启动脚本新增独占绑定预检与清晰冲突提示。

## 实现取舍与后续

demo在进程内SQLite运行，与MySQL模式复用同一查询服务；演示库重启重置。MySQL连接具备密码安全编码、超时、UTC与只读事务配置；本轮未实际连接MySQL。未来联调前必须核对实际表、账户和数据，不自动重建已有表、不自动导入demo、不在连接失败时切回演示。

省编码兼容41与410000，城市按city_name；所有主键对外字符串。没有擅自添加city_code、publicFacilityId等SQL不存在的字段；资产状态不当在线状态。地图geometry和GLB继续留前端静态资源，待twin模块提供版本及绑定协议。

先请用户按测试指南确认台账协议和查询体验，再补最小system登录／站点范围授权，再做twin对象绑定与monitoring测点读数。真实MySQL连接、前端数据源切换、数据库迁移基线及正式权限测试均待后续。

完整手工步骤见同目录C后端第一模块_站点与设备台账_测试指南.md；字段协议见C前后端接口约定.md。继续修改时参照根目录AGENTS.md。

## 2026-10-15：中文代码注释完善

现有23个应用Python文件均有模块说明，26个类、50个函数均有用途说明；主要业务函数说明参数、返回结果、必要异常与边界。5张ORM表的59个专属字段及公共时间字段附有说明。API响应字段与查询参数提供中文描述，可在/docs中查看；启动脚本增加帮助、Port含义和端口检测说明。

43项原测试、Ruff及格式检查继续通过。对25个应用及测试Python文件的规范化语法结构比对确认只调整注释、docstring和description元数据，没有修改查询、过滤、默认值和事务逻辑；OpenAPI字段说明及PowerShell帮助解析检查通过。本轮未启动后台服务，未占用8000端口，未修改前端或连接MySQL。

每个后续模块也必须提供中文职责、主要函数参数和返回值、必要异常、字段单位及空值规则；业务变化时同步更新说明。该要求已经记录到根目录AGENTS.md。完整阅读路线见同目录C后端代码注释与阅读指南.md。
