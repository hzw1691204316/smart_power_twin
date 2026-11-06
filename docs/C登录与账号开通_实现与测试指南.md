# 智慧电力系统：登录与账号开通模块实现与测试指南

> 最新状态：已统一MySQL并按用户要求改为明文password列，旧demo启动和改密工具已移除。请以[CMySQL统一运行与明文密码说明.md](CMySQL统一运行与明文密码说明.md)为准；下文保留为前一阶段记录，不再照旧工具或哈希字段操作。

> 后续更新：MySQL接入、导入顺序、新初始账号和专用启动命令见[C账号模块_MySQL接入与导入说明.md](C账号模块_MySQL接入与导入说明.md)。本文件保留demo阶段测试步骤；真实MySQL已在独立实例通过联调，但尚未连接用户数据库。

更新日期：2026-10-15。

**本轮完成登录、管理员开户、站点授权和账号状态管理的前后端接入，随后暂停，不继续其他模块。当前供本机演示测试使用，未连接或修改真实MySQL。**

项目根目录：`D:/study_software/PythonProject/smart_power_twin`。

正式阅读副本：`C:/Users/xxu20/Desktop/智慧电力文档`。此后新文档均放此目录、文件名以C开头；旧桌面文档未搬动。

## 1. 已实现哪些功能

| 功能 | 本轮行为 |
|---|---|
| 登录页 `/login` | JSON提交账号密码，显示错误、提交状态；保持海蓝色和圆角样式 |
| 身份查询 | `/auth/me`返回当前用户、角色、动作权限、授权站点；不返回密码或哈希 |
| 页面保护 | 未登录进入登录页；登录后回到原站内路径；不允许外部URL跳转 |
| 账号管理 `/admin/users` | 管理员查看分页账号、创建账号、完整替换站点授权、锁定和恢复账号 |
| 无权限页面 | 已登录但没有管理动作权限时显示访问受限，不反复要求登录 |
| 共用账号菜单 | 地图页、正常三维页点击用户名，可进入管理页或退出 |
| 台账权限 | 原站点、设备、区域、路线查询均纳入认证和站点范围检查 |
| 审计 | 开户、授权、状态变更同事务记录脱敏摘要，不记录密码或JWT |
| 会话过期 | 默认30分钟；退出、过期、接口401后清理内存凭据、站点缓存和检索状态 |

这里的“账号开通”由管理员操作，**没有公众注册接口**。忘记密码、重置密码、修改密码、刷新令牌、全端退出、企业单点登录、MFA均未实现，正式使用前另行补齐。

## 2. 怎样启动并测试

### 2.1 后端

在项目根目录打开PowerShell。如已有PyCharm后端正在运行，先在原运行窗口正常停止，再启动一次，避免重复占用8000。

```powershell
Set-Location D:\study_software\PythonProject\smart_power_twin
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

现有环境已安装新增的`PyJWT==2.15.1`和`pwdlib[argon2]==0.3.1`；上述安装命令方便以后重建环境。

默认demo模式使用新内存SQLite：两站、8台设备、6个区域，以及账号权限数据。**本轮不需要执行新的SQL，也不用改现有MySQL。** 后端每次重启，新增账号和授权修改都会丢失并恢复初始演示状态。

健康检查：`http://127.0.0.1:8000/api/v1/health`，应看到`dataSource=demo`、`module=assets-system`、`authenticationImplemented=true`。

如果本地已有`.env`覆盖默认模式，先在本地确认`SPT_DATA_SOURCE=demo`；密码或签名密钥不必发到聊天中。

WinError10013/10048属于端口绑定问题，与账号错误或浏览器CORS不是同一问题。可以使用原`scripts/start_backend.ps1`检查端口；脚本不会自动停止其他程序。若改后端端口，要同步修改前端`vite.config.ts`里的API代理目标。

### 2.2 前端

在另一个PowerShell窗口：

```powershell
Set-Location D:\study_software\PythonProject\smart_power_twin\smart_power_web
npm.cmd run dev
```

打开`http://127.0.0.1:5173/login`。原Vite服务如未自动重载配置，请正常重启一次。

前端请求自己的`/api/v1/...`，Vite转发到`127.0.0.1:8000`；两个服务都需要启动。只启动前端会显示连接失败，不能登录。Cesium AccessToken仍使用原本地配置，**不是系统登录JWT**，本轮未读取或改写真实Token。

### 2.3 演示账号

| 身份 | 账号 | 密码 | 可访问范围 |
|---|---|---|---|
| 管理员 | `demo_admin` | `DemoAdmin!2026` | 朝歌服务区、朝歌收费站；开户、授权、账号状态与审计接口 |
| 观察员 | `demo_viewer` | `DemoViewer!2026` | 只读朝歌服务区；没有账号管理权限 |

这些是本机演示凭据，不能用于正式部署。登录页只在后端健康接口明确为demo时显示演示账号提示。

## 3. 建议按这个顺序验收

1. **未登录访问**：打开全国或河南业务页，应跳登录；登录后回到原页面。
2. **管理员登录**：全国→河南→鹤壁，朝歌服务区和收费站可以进入对应第四版三维场景。
3. **开通新账号**：点击用户名→账号管理，填写账号、显示名、至少10字符初始密码，选择VIEWER和朝歌服务区，创建成功。
4. **切换账号**：退出，再用新账号登录；只显示授权的业务样板。初始密码输入框提交后清空，列表不会展示密码。
5. **越权检查**：观察员直接进入`/admin/users`应看到无权限页面；直接请求未授权站点接口返回404。不能靠猜ID绕过后端范围。
6. **授权变化**：管理员将新账号范围换为收费站，用新账号下一次访问接口立即按新范围检查。前端下次路由跳转重新查询`/auth/me`并清理旧缓存；当前页面没有实时推送，修改后可重新登录查看最新UI。
7. **撤销授权**：站点全部取消后保存；空数组表示没有任何站点权限，绝不是全部站点。
8. **锁定与恢复**：管理员锁定新账号，其已有令牌下一次请求返回401，新登录也失败；恢复后可重新登录。禁止锁定自己。
9. **刷新和退出**：刷新浏览器需重新登录，这是当前内存令牌设计；退出后返回登录，不应继续保留上一账号站点检索结果。
10. **原功能检查**：全国地图发光、省市路网、左右半透明侧栏、收起面板、地市下钻、绿色/黄色点进入三维、省市固定朝向滚轮、朝歌配对切换。

双账号测试用两个浏览器会话/窗口更方便；只复制同一标签不会把内存登录状态自动带过去。

## 4. 为什么三维样板数量变成2或1

原前端有6个本地样板，后端当前仅有两座已建演示台账。接入登录后，`siteService.ts`先从后端取**当前账号授权的站点**，再按稳定业务编码`code`与本地场景匹配。

- 管理员显示2个业务样板，观察员显示1个；统计、配对入口与示例总量按这一列表变化。
- 其余4个原本地样板仍保留在素材文件中，没有删除；尚未导入后端并授权，所以不会假装成当前账号的业务台账。
- 前端路由ID如`henan-service-01`与数据库主键`1`并不是一回事；当前通过`HEBI_CHAOGE_SERVICE_DEMO`等业务编码连接两者。
- GLB、功率、设备面板、曲线和演示告警仍是本地样例，**本轮不是监测/告警业务接入**，不能据此判断现场状态。
- 河南公开位置与高速路网依旧展示。未绑定台账的位置可进入同类型通用模型，明确标注模板；已绑定台账的站点不能绕过授权改走公开模板入口。

真实业务数据以后不能放进`src/data/demo.ts`或`public`目录来“保护”：这些是可下载的前端演示素材；登录保护的是业务API和页面流程，不会让静态资源变成私密文件。

## 5. 前后端代码分别在哪里

### 前端

| 文件 | 修改时主要看什么 |
|---|---|
| `src/views/LoginView.vue` | 登录表单、明文显示开关、错误与加载状态；不保留提交后的密码 |
| `src/views/AccountsView.vue` | 开户、选择角色/站点、分页列表、授权和锁定交互 |
| `src/views/ForbiddenView.vue` | 已登录但动作权限不足的提示 |
| `src/components/common/UserMenu.vue` | 两类布局共用的当前用户菜单与退出 |
| `src/stores/auth.ts` | 用户、内存JWT、30分钟到期计时、清会话、重新确认身份 |
| `src/services/http.ts` | Bearer头、JSON错误、10秒超时、401与403处理；旧请求401不能注销新账号 |
| `src/services/authService.ts` | 登录、当前用户、角色、用户、授权、状态等接口 |
| `src/types/auth.ts` | TypeScript协议；ID统一字符串 |
| `src/utils/authRedirect.ts` | 登录后的站内安全返回路径 |
| `src/router/index.ts`、`src/App.vue` | 页面访问控制、独立登录布局 |
| `src/main.ts`、`src/stores/sites.ts`、`src/stores/directory.ts` | 换账号/授权变化时清理旧数据；丢弃旧请求迟到结果 |
| `src/services/siteService.ts` | 按后端授权业务编码过滤原演示场景 |
| `src/styles/auth.css` | 账号相关海蓝样式、键盘焦点与响应式调整 |
| `vite.config.ts` | `/api`到8000端口的代理；生产部署须另配同源网关 |

### 后端

| 文件 | 职责 |
|---|---|
| `app/core/security.py` | Argon2密码哈希、校验；HS256 JWT签发、用途/签名/到期检查 |
| `app/api/dependencies.py` | 请求会话、当前用户、动作权限校验、台账范围注入 |
| `app/modules/system/models.py` | 六张账号权限表的SQLAlchemy映射 |
| `app/modules/system/schemas.py` | 请求协议、字段长度、角色/站点ID；拒绝未知字段 |
| `app/modules/system/repository.py` | 从数据库查询账号、角色动作、授权站点 |
| `app/modules/system/service.py` | 登录、开户、完整替换范围、状态变更、审计事务 |
| `app/modules/system/router.py` | 接口路径、参数说明、依赖和HTTP状态 |
| `app/modules/system/demo.py` | 仅供新内存SQLite初始化两账号；真实MySQL不执行 |
| `app/modules/assets/repository.py` | 列表及详情在数据库查询层限制授权站点 |
| `app/application.py` | CORS、只允许本机、随机演示密钥、生命周期及API禁止缓存 |

新增模块均有中文职责说明和关键函数注释，参数、错误及业务边界见源文件。应用没有全局默认管理员绕过：管理员也只管理自己被授予的站点及动作。

## 6. 六张账号表怎么配合

```text
sys_role 1 ─── N sys_user 1 ─── N user_site_scope N ─── 1 site
    │
    1
    │
    N
role_permission N ─── 1 sys_permission

sys_user 1 ─── N audit_log N ─── 0或1 site
```

- `sys_user`：账号、显示名、密码哈希、角色ID和状态；首期一个账号对应一个角色。
- `sys_role`：如ADMIN、VIEWER；角色名不是直接的后门，实际检查权限码。
- `sys_permission`：五个已启用动作码：`site:read`、`device:read`、`system:read`、`user:manage`、`audit:read`。
- `role_permission`：角色拥有哪些动作。动作权限是“能做什么”。
- `user_site_scope`：用户与站点的多对多关系；范围是“能对哪些站点做”。
- `audit_log`：谁在何时维护了哪个账号及授权摘要。全局账号操作记录的`site_id`可空；当前审计接口只向原操作者返回本人全局账号操作。

开户、授权、锁定均校验目标动作和站点不得超出操作者权限。同一事务写账号/范围/审计，失败回滚，不留下半个账号或半条授权。

## 7. 接口速查

统一前缀`/api/v1`。除健康与登录等基础入口，以下业务均需`Authorization: Bearer <accessToken>`。

| 方法与路径 | 输入/权限 | 返回/规则 |
|---|---|---|
| `POST /auth/login` | `{username,password}` | `data.accessToken`、`expiresIn`秒、`user`；错误401，失败次数过多429 |
| `GET /auth/me` | 当前Bearer令牌 | 当前身份、动作及授权范围 |
| `GET /roles` | `system:read` | 角色数组；没有编辑角色接口 |
| `GET /users?page=1&pageSize=20` | `system:read` | `data.items/total/page/pageSize`；仅操作者站点范围内的账号 |
| `POST /users` | `user:manage`；username/displayName/password/roleId/siteIds | 成功201；重复409，越权403；roleId和siteIds元素均为字符串 |
| `PUT /users/{id}/sites` | `user:manage`；`{siteIds:["1"]}` | 完整替换，不是追加；空数组撤销全部范围 |
| `PUT /users/{id}/status` | `user:manage`；`{status:"LOCKED"}` | ACTIVE/LOCKED/INACTIVE；本人状态禁止修改 |
| `GET /audit-logs?page=1&pageSize=20` | `audit:read` | 当前页审计数组；此接口尚不返回总数 |

登录JSON示例：

```json
{"username":"demo_admin","password":"DemoAdmin!2026"}
```

开户JSON示例：

```json
{"username":"hebi_viewer","displayName":"鹤壁观察员","password":"MyDemoPass!2026","roleId":"2","siteIds":["1"]}
```

`/docs`调试：先执行登录，复制`data.accessToken`，点击Authorize粘贴令牌本身（HTTPBearer组件会添加Bearer），再测试台账或开户。直接用浏览器地址栏打开受保护接口没有Authorization头，会返回401，属正常行为。Swagger记住的旧令牌在后端重启后也可能失效。

## 8. 配置、安全边界和MySQL

- demo不填`SPT_TOKEN_SECRET`时每次启动生成随机密钥；已有JWT重启失效。默认有效期`SPT_TOKEN_MINUTES=30`，允许1—240。
- 密码仅存Argon2哈希，每次独立随机盐。响应、验证错误、审计不回显密码。
- JWT校验固定算法、签名、issuer、audience和必须的到期等声明；用户状态、角色和站点每次从数据库重查。
- 登录失败限制是同进程内同IP+账号5分钟10次；当前不是多实例集中限流或生产防暴力系统。
- API返回`Cache-Control: no-store`。前端令牌只存内存，不写localStorage/sessionStorage或URL；刷新后重新登录。
- 退出只清本浏览器凭据；复制出去的JWT在到期前仍可能有效。锁定/停用账号会阻止下一次请求，当前没有令牌撤销列表或全端退出。
- 依旧只允许本机请求，不自动开放局域网；启动使用`127.0.0.1`与`--no-proxy-headers`。
- MySQL默认`SPT_MYSQL_ALLOW_WRITES=false`，开户/改授权/状态返回409，不会悄悄执行写入。
- 切到MySQL须先核验表结构，准备合适数据库权限、至少32字符本地签名密钥及受控初始管理员；当前没有自动生成真实管理员。数据库口令和密钥只在后端配置。
- 本轮MySQL无连接、无迁移、无导入、无写入。SQLite测试通过不代表MySQL真实联调完成。生产的HTTPS、会话撤销、密码生命周期及部署评审尚未完成。

## 9. 检查结果与未验收项

后端执行：

```powershell
.\.venv\Scripts\python.exe -m ruff check app tests main.py
.\.venv\Scripts\python.exe -m ruff format --check app tests main.py
.\.venv\Scripts\python.exe -m pytest -q
```

前端执行`npm.cmd run verify`，包括lint、既有布局/检索/GLB回归、真实Cesium Camera滚轮与图层几何检查、认证请求层回归、TypeScript和生产构建。

最终后端**63项测试通过**，Ruff检查和60个文件格式检查通过；前端`npm.cmd run verify`全项通过。后端ASGI测试覆盖登录、过期/错误JWT、密码哈希、查看人员越权、管理员开户、范围替换和撤销、锁定、禁止自锁、受限管理员不得提权、审计脱敏、MySQL写入保护及48个并发认证请求。前端请求层覆盖安全返回、Bearer头、401/403及迟到旧401隔离。完整结果见[C账号模块完成与暂停_续接记录.md](C账号模块完成与暂停_续接记录.md)。

**尚未进行本轮浏览器实际视觉/点击验收**，沿用当前浏览器访问限制，没有绕过。构建及代码回归不等于真实画面验收；请按第3节实际测试。已保留已有地图样式与模型，只有账号入口、授权数据来源、动态计数等本模块必要接入。

现有提示：Starlette/httpx弃用提示、Cesium/Three.js构建包体提示不阻断本轮测试；没有为隐藏提示而扩大升级范围。

## 10. 本轮结束位置

活动接口只包含`assets`和`system`；正常启动注册11张表（5张台账+6张账号）用于内存演示。原19表SQL未精简或改写。

`monitoring`、`alarms`、`twin`、`dashboard`已保留部分草稿，以及未调用的`app/demo.py`；它们**未注册业务路由、未纳入本轮交付、没有宣称完成**。本轮没有循环模拟采集、实时监测、告警处置或场景发布。下一次用户明确要求继续时，再先审阅这些草稿及接口约定。

**按要求，完成账号模块后暂停。**
