# 后端开发约定

- 根目录main.py与app是后端，smart_power_web是独立前端。2026-10-18用户授权继续大屏汇总模块：共19表，system/assets/monitoring/twin/alarms/dashboard六个基础模块已启用。保留已确认地图和模型，不自动导入用户数据库。
- 后端按api/core/db/common/modules分层。2026-10-18六模块共19表；dashboard只读聚合按授权与source筛设备/功率/事件，默认FIELD；站点数含全部授权台账。唯一active_power瞬时kW候选才计入，GOOD且新鲜、非未来，0/负值保留，缺测null、歧义不盲加。日计量/跨站历史/自给率尚未实现。告警仅在新鲜GOOD最新数值采样的同一事务中评估上下限，本引擎只恢复带numeric_threshold_v1标记的事件；确认不等于恢复，恢复且确认后才能手动关闭。
- 每个已实现或新增模块必须有中文说明：文件／模块职责、主要函数或类的用途、参数、返回值、必要异常及业务边界。接口参数和响应字段同步提供OpenAPI说明，写清单位、可空值、ID及状态含义；注释解释规则和原因，不逐行翻译语法。业务变更时同时更新注释，后续前端新增或修改模块也遵循这一要求。
- 正式启动只支持MySQL，main.py与启动器统一读取.env.mysql.local，不再接受demo/test作为环境配置。SQLite素材只在scripts/sample_assets.py及tests/support中供离线工具/测试使用，应用启动不建表、不导入、不回退。
- 不输出.env中的密码、前端Token或连接URL。主键响应为字符串；资产有效状态与运行在线状态分开。
- 已有Bearer认证、动作权限及站点范围，仍只供本机测试；启动绑定127.0.0.1并使用--no-proxy-headers。不自动开放局域网。
- 不在FastAPI启动时运行循环模拟采集；台账、场景绑定、监测读数职责分开。
- 后端改动后运行ruff检查、格式检查与pytest。SQLite测试不代表真实MySQL联调，需分别记录。
- 测试启动的临时后端验证完成后正常关闭，避免占用8000与用户PyCharm冲突。停止其他进程前核实归属，不按端口盲目终止。端口绑定失败和CORS分别排查。
- 创建的说明文档名称以C开头，维护docs镜像；桌面正式副本统一放C:/Users/xxu20/Desktop/智慧电力文档，旧文档不擅自搬动。
- 2026-10-16用户继续授权twin模块：私有场景按数据库对象/设备/测点绑定展示，草稿保存后显式发布；站点锁按site→scene顺序，MySQL版本号及当前发布场景使用锁定当前读。仅支持整场景GLB内置变换，不支持独立对象文件/JSON位姿覆盖。不连带启用alarms/dashboard，不自动执行SQL或模拟采集。
- 2026-10-15已按新指示补齐账号模块MySQL接入：scripts/run_backend_mysql.py使用.env.mysql.local，启动只读结构预检；sql/脚本供用户手动导入，应用不自动执行。其他模块仍不继续。
- 真实MySQL测试仅连接显式指定的隔离实例，禁止3306并验证@@datadir为.runtime/mysql-auth-integration；不读取用户.env。默认运行跳过隔离集成测试。不要把测试指向用户库。
- 用户最新明确要求sys_user网页登录密码明文保存。模型列现为password，后端直接比较/保存但不向查询API回显；JWT仍签名。旧password_hash已按授权迁移并备份，初始两账号密码/角色/范围/状态不变。已移除改密工具，后续用户可直接修改数据库password列。

- 大屏本轮收尾：C08权限脚本由用户手动执行，不修改账号/密码/站点范围。基础聚合已接前端，全国/省市/私有站点保留布局，公开方案不查私有汇总；私有站点不再使用固定功率示意。139项后端测试（12项隔离MySQL）、前端verify通过；后续优先台账维护与公司数据接入。

- 2026-10-18台账维护已启用（0.7.0）：四个写接口在assets/maintenance*.py，site:create仅为创建者新增本站范围，asset:manage只改授权范围；C09手动授权ADMIN/SIM_ADMIN。身份列code/type/system/isDemo不可编辑，父链同站防环，站点已有场景冻结规模；改坐标/来源清核验时刻，主路线不删除原关系。锁顺序site→devices/links；MySQL使用锁定当前读，避免RR旧快照导致父环。无硬删除或级联处置，站点停用不当采集停机命令。154项后端测试含13项隔离MySQL；后续区域/路线维护、批量导入、公司点表和场景创建UI待做。

- 2026-10-18场景创建已补齐（0.8.0）：twin/configuration.py提供模板对象目录、from-template新草稿、objects完整保存；旧POST scenes仍复制当前发布版。类型/规模相符、实际GLB键复核、同站设备，禁止绑定对象直接删除/换设备；同键保留ID，删除父配置解除子引用。站点锁+锁定当前读分配版本，审计同事务；19表及权限编码不变，C07仍手动注册。166测试通过含14项隔离MySQL，前端verify通过；测点配置UI/公司协议/批量导入等待做。

- 2026-10-18测点管理前端/admin/points补齐，复用monitoring现有三接口和monitor:read/configure。仅前端实现，后端源码/表结构/用户MySQL未改；周期ms、空阈值null与0/负值区分，身份单位类型固定、停用保留历史绑定告警。前端verify含check:point-management通过，关联后端39项回归通过；本轮不宣称重新跑了14项MySQL。后续公司采集协议、区域/路线与批量导入、计量配置待做。

- 2026-10-19站内关系维护0.9.0：assets/relations.py及relation_schemas.py，四个POST/PUT维护接口复用asset:manage/site:read/本站范围。区域树防环，站点锁+锁定当前读；路线主关联互斥，桩号米制Decimal(12,3)，无硬删除或公共字典写接口。RouteOut字段补齐，apply_primary保留同路线既有主方向。180测试通过含15项隔离MySQL（并发父环/主关联/审计回滚），前端verify通过。无新表或权限SQL，不自动操作用户库。后续批量导入、公司采集、计量、告警扩展与部署待做。
