# 智慧电力数字孪生后端

当前正式后端只使用MySQL，统一读取.env.mysql.local。登录、开户和授权持久保存；按用户要求，网页登录密码明文存于sys_user.password。旧demo启动分支和改密工具已移除。

当前启用账号权限、台账查询与维护、电力监测、三维绑定、告警处置、大屏汇总六个基础模块，共19表。最新说明：[大屏汇总模块](docs/C大屏汇总模块_实现与测试指南.md)。原ADMIN/VIEWER可手动导入sql/C08大屏汇总模块_权限初始化.sql后重新登录；模拟账号本来已有dashboard:read。默认查看现场设备，可切模拟来源，缺测不补0。桌面正式副本在C:/Users/xxu20/Desktop/智慧电力文档。

## 启动

在项目根目录选择一种后端启动方式，不能重复占用8000：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_backend_mysql
```

也可使用`python -m uvicorn main:app --host 127.0.0.1 --port 8000 --no-proxy-headers`，main.py同样默认MySQL。前端在smart_power_web中执行npm.cmd run dev。

打开http://127.0.0.1:5173/login。mysql_admin、mysql_viewer初始密码见桌面C账号模块_MySQL初始账号.md；临时密码提示已移除。新模拟账号见全模块导入说明。数据库连接密码和JWT密钥只填本地配置，不是网页账号密码。

缺少MySQL连接/表结构时明确报错，不自动建表、迁移或导入，不回退内存模式。启动前可使用`python -m scripts.run_backend_mysql --check-only`只读预检。

## 修改网页密码

直接在MySQL修改sys_user.password列。密码修改不影响角色/站点范围；查询API与审计不回显密码。明文模式仅供本机学习；JWT仍使用签名，当前没有全端令牌撤销机制。

## 检查

```powershell
.\.venv\Scripts\python.exe -m ruff check app tests scripts main.py
.\.venv\Scripts\python.exe -m ruff format --check app tests scripts main.py
.\.venv\Scripts\python.exe -m pytest -q
```

SQLite仅供tests/support及离线SQL工具使用，不是可启动的应用模式。真实MySQL集成测试需要独立实例，默认跳过，不得指向用户3306数据库。2026-10-19启用隔离实例时180项测试通过，其中15项为真实MySQL。

## 初始化资料

sql/中的C00（仅缺表）、C01（初始数据）、C02（只读核验）供手动导入。当前用户数据库已完成密码列迁移和登录验收，无需重新导入。C01含明文初始密码，已忽略提交，不公开分享。

当前启动只读预检共19表，告警模块使用既有alarm_event；仅缺表时执行C00告警模块脚本，已有全模块19表无需重复建表。原ADMIN/VIEWER角色需手动执行C06告警权限补丁后重新登录；sim_*已有告警权限。此前C03/C04/C05继续用于监测/三维权限，不包含告警。应用启动不会执行SQL或生成采样。采样写入在同事务评估新鲜GOOD最新值的数值阈值；确认不代表恢复，恢复+确认后才能关闭。受限数据库账号还需要alarm_event的SELECT/INSERT/UPDATE及既有采样与审计写权限。

原账号提示没有三维场景权限时，可手动执行 `sql/C05管理员与观察员_模块权限修复.sql` 后退出重新登录。C05显式补回ADMIN/VIEWER角色的台账、监测和三维缺失权限，不受旧补丁首次标记限制；保留密码、角色、站点范围及其他授权。详见 `docs/C管理员与观察员_三维权限修复说明.md`。

## 站点与设备维护（0.7.0）

右上角用户名菜单→站点与设备台账（/admin/assets）。管理员手动导入sql/C09站点设备台账维护_权限初始化.sql并重新登录，后端写开关和数据库写权限须就绪。新站只授权创建者；身份字段固定，台账停用保留历史。新建有WGS84坐标的站点可进入地图，没有发布场景时不套用其他站点。详见[台账维护指南](docs/C站点与设备台账维护_实现与测试指南.md)。

## 三维场景创建与配置（0.8.0）

用户名菜单→三维场景配置（/admin/scenes），或从台账页进入本站配置。支持没有旧场景的新站从匹配模板创建草稿、编辑对象与设备关系、配置测点绑定及显式发布。复用19表和twin:read/twin:publish权限；大型服务区模板仍由用户手动导入C07注册。详见[场景配置指南](docs/C三维场景创建与配置_实现与测试指南.md)。前端新增check:scene-config并纳入verify，既有地图、模型、会话和台账保留。

## 设备测点管理页面（2026-10-18）

用户名菜单→设备测点管理（/admin/points），台账具体设备也可直接跳转。支持新增定义、周期/启停/阈值配置，复用已有monitoring接口及权限，无需新增表或SQL；观察员只读。与场景配置页衔接，详见[测点管理指南](docs/C测点管理页面_实现与测试指南.md)。check:point-management已纳入verify；本轮前端完整检查及39项后端关联回归通过，未修改后端源码或用户数据库。

## 站内区域与高速关联（0.9.0，2026-10-19）

用户名菜单→站内区域与高速关联（/admin/site-relations），台账本站也可进入。支持新增/编辑区域父树、方向/区域/米制桩号/接入方式/主关联，复用asset:manage与19表，无新建表SQL或自动导入。普通站点保存保留同一路线原主方向。完整后端180项通过含15项隔离MySQL，前端verify含check:site-relations通过；详见[区域与关联指南](docs/C区域与高速关联维护_实现与测试指南.md)。
