# 智慧电力数字孪生系统

面向高速公路服务区和收费站的智慧电力原型，提供中国省级地图、河南高速路网、站点三维场景，以及设备、测点、监测数据和告警展示。项目由 Vue 前端、FastAPI 后端与 MySQL 数据库组成。

目前适合**本机开发和学习演示**：地图公开位置、通用模型与模拟电力数据不等同于现场测绘或实时采集；企业现场采集、完整能耗计量及生产部署仍待建设与验证。网页登录密码按当前项目约定明文保存在 `sys_user.password`，请仅用于隔离的本机练习，不要将本示例直接开放到公网。真实密码、密钥和 Token 不得提交到 GitHub。

## 功能与结构

- 全国省份选择、河南省市高速路网、服务区与收费设施定位。
- 登录、账号和权限；站点、设备、站内区域及高速关联维护。
- 三维场景模板、对象与测点绑定；设备监测、历史查询、告警及大屏汇总。
- 本地公开地图数据和 GLB 模型；具体站点是否有可用场景取决于数据库中的发布和绑定配置。

```text
smart_power_twin/
├── smart_power_web/       Vue 3 前端、地图数据与 GLB 模型
├── app/                   FastAPI 业务代码：system、assets、monitoring、twin、alarms、dashboard
├── main.py                后端入口
├── scripts/               启动与辅助脚本
├── sql/                   手动执行的建表、模拟数据、核验与权限脚本
├── tests/                 自动化测试
├── docs/                  模块说明，部分旧说明记录的是历史状态
├── requirements.txt       后端运行依赖
├── requirements-dev.txt   后端开发与测试依赖
└── .env.mysql.example     后端本地配置模板
```

技术栈：Vue 3、TypeScript、Pinia、Vue Router、Vite、Cesium、Three.js；Python、FastAPI、SQLAlchemy、PyMySQL；MySQL 8。三维资源与数据来源说明见 [地图数据来源与使用说明](smart_power_web/public/maps/C地图数据来源与使用说明.md)；正式发布前仍需核实相关地图与模型授权。

## 运行前准备

| 软件 | 要求与用途 |
| --- | --- |
| Git | 用于克隆和版本管理；项目未声明最低版本 |
| Node.js | `^22.18.0` 或 `>=24.12.0`；同时需要 npm，以 `package.json` 的 `engines` 为准 |
| Python | 建议 Python 3.10；项目 Ruff 目标版本为 3.10，其他版本请自行验证 |
| MySQL | 8.0.16 或以上的 MySQL 8；建表脚本使用 MySQL 8 的排序规则和功能，旧模块说明记录过 8.0.33 测试 |
| 浏览器 | 支持 WebGL 的现代浏览器，用于 Cesium 和 Three.js |

在终端确认软件可用：

```text
git --version
node --version
npm --version
mysql --version
```

Windows 可用 `py -3.10 --version`；Ubuntu 可用 `python3.10 --version`。Ubuntu 如缺少对应 Python 或 `venv` 组件，需要通过系统包管理器或其他可信方式自行安装。以上是版本检查命令，不会创建数据库。

## 1. 克隆代码

Windows PowerShell 与 Ubuntu 终端均可使用：

```bash
git clone https://github.com/hzw1691204316/smart_power_twin.git
cd smart_power_twin
```

私有仓库需要先获得访问权限并按 GitHub 提示认证。已有本地仓库不必重复克隆。以下步骤都以克隆后的**项目根目录**为起点，前后端在不同终端启动。

## 2. 创建独立 MySQL 练习库并导入数据

**以下 SQL 由使用者手动执行。**先确认连接的是新电脑上的独立练习 MySQL，不是生产库或已有业务库；默认脚本固定使用库名 `smart_power_twin`。如果该库名已存在，先停止并检查，不能直接复用或覆盖。应用不会自动建表、导入或修复旧表。

Windows 或 Ubuntu 在项目根目录运行：

```bash
mysql -u root -p
```

按提示输入本地 MySQL 管理员密码，输入时不显示；不要把密码写到命令行、聊天或仓库中。成功进入 `mysql>` 后，在**确认该库不存在且是独立练习环境**的前提下，手动执行：

```sql
CREATE DATABASE smart_power_twin CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
```

上述语句若提示数据库已存在，请停止，不要忽略错误继续。创建数据库需要管理员权限；C00 不创建数据库。接下来使用具备必要权限的账号，在项目根目录执行 `mysql` 命令进入的客户端内依次运行（使用支持 `DELIMITER` 的 MySQL 客户端；路径相对于启动客户端时的当前目录）：

```sql
SOURCE sql/C00全模块_建表_仅缺表时使用.sql;
SOURCE sql/C01全模块_模拟数据.sql;
SOURCE sql/C02全模块_模拟数据核验.sql;
```

1. C00 创建缺失的 19 张表；它不会迁移已有同名表或修复旧字段。
2. C01 导入**模拟**角色、账号、站点、设备及监测数据；脚本使用存储过程和事务，需有相应建表、读写和过程权限。导入失败时停止并先检查错误，不要盲目重复操作。
3. C02 查询核验结果，不修改业务记录；对照文件内的预期数量与说明判断。C01 的时间是模拟快照，导入后读数可能过期，不应当作现场实时数据。

`SOURCE` 是 MySQL 命令行客户端命令，不是 PowerShell 或 Bash 命令。若图形化工具不支持 `DELIMITER`，请使用 MySQL 命令行或选择支持执行完整脚本的工具。文件名含中文，在 Linux 上需确保文件系统和客户端按 UTF-8 正确处理；该平台的完整导入流程**尚待新机验证**。

C01 包含固定的模拟网页账号和明文测试密码，账号信息位于脚本及 [模拟数据导入说明](docs/C全模块模拟数据_导入与测试说明.md)；仅用于隔离练习，不要复用到其他系统或对外部署。该说明含旧版本状态和本机路径，以本 README 与实际代码为准。实际使用时应自行为练习库设置本地账号密码；不要把修改后包含个人密码的 SQL 保存到被 Git 跟踪的文件中。**MySQL 连接账号与网页登录账号是两类不同账号。**

建议为应用建立仅用于该练习库的独立 MySQL 账号，并依实际需要分配权限：启动预检和查询需要访问数据库及表结构的权限；账号管理、数据维护等写操作还需要对应业务表和审计表的写权限。精确最小授权清单尚未形成，需在隔离环境验证。学习阶段可由本机管理员根据用途设置，避免将管理员账号与密码提交到仓库。导入完成后输入 `EXIT;` 退出 MySQL 客户端。

## 3. 创建后端本地配置并安装依赖

### Windows PowerShell

以下命令在项目根目录运行：

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.mysql.example .env.mysql.local
```

### Ubuntu Bash

以下命令在项目根目录运行：

```bash
python3.10 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
cp .env.mysql.example .env.mysql.local
```

如果目标文件已存在，请先检查并保留原配置，**不要覆盖已有密码和密钥**。在文本编辑器中打开根目录 `.env.mysql.local`，根据本机练习库填写。下面是字段示意，尖括号内容必须替换为自行设置的值；不要复制任何人的真实凭据：

```dotenv
SPT_DATA_SOURCE=mysql
SPT_MYSQL_HOST=127.0.0.1
SPT_MYSQL_PORT=3306
SPT_MYSQL_DATABASE=smart_power_twin
SPT_MYSQL_USER=<本地练习数据库账号>
SPT_MYSQL_PASSWORD=<本地练习数据库密码>
SPT_MYSQL_ALLOW_WRITES=false
SPT_TOKEN_SECRET=<自行生成的至少32字符随机签名密钥>
SPT_TOKEN_MINUTES=30
```

`SPT_MYSQL_ALLOW_WRITES=false` 是默认的写入保护；如果需要进行账号开通或台账维护等写操作，须先确认使用独立练习库及数据库账号权限，再在本地显式改为 `true`。写入开关不代替数据库权限或应用角色权限。`SPT_TOKEN_SECRET` 应为每个环境单独生成的随机值，例如在本机使用 Python 的 `secrets` 模块生成；不要将生成结果发送给他人。

`.env.mysql.local` 是被忽略的本地文件。环境变量可能覆盖文件配置；不要将真实值写入 `.env.mysql.example`、源码、日志、SQL、截图或 Git 历史。应用会验证 MySQL 密码非空和签名密钥长度；启动时只读检查表结构，不代表账号与业务数据已配置完成。

## 4. 启动后端

在项目根目录另开一个终端。先按对应系统执行以下**只读数据库结构预检**；预检会连接上面配置的练习库，但不会导入或修改数据。其终端提示中的表数量文字可能滞后，实际校验列表以 `app/db/validation.py` 为准。

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_backend_mysql --check-only
.\.venv\Scripts\python.exe -m scripts.run_backend_mysql
```

Ubuntu Bash：

```bash
./.venv/bin/python -m scripts.run_backend_mysql --check-only
./.venv/bin/python -m scripts.run_backend_mysql
```

仅当预检通过后运行第二条。服务默认监听本机 `127.0.0.1:8000`，不要同时启动另一个后端占用同一端口。保持该终端运行。

## 5. 配置并启动前端

再开一个终端，从项目根目录进入前端并安装锁定依赖：

```bash
cd smart_power_web
npm ci
```

如果需要在线卫星影像，创建前端本地配置文件；已有文件时先保留，不要覆盖。

Windows PowerShell：

```powershell
Copy-Item .env.example .env.local
```

Ubuntu Bash：

```bash
cp .env.example .env.local
```

编辑 `smart_power_web/.env.local`：

```dotenv
VITE_CESIUM_ION_TOKEN=<自行申请并配置的Cesium ion Token>
```

Token 可留空；它会出现在浏览器使用的前端配置中，应在服务提供方侧按可用能力限制权限或来源，不能把前端 Token 当作服务器秘密。不要提交实际 Token。修改 `.env.local` 后需重启 Vite。

Windows 和 Ubuntu 在 `smart_power_web` 目录均执行：

```bash
npm run dev
```

前端默认监听 `127.0.0.1:5173`，开发服务器将 `/api` 转发到 `127.0.0.1:8000`；因此两个服务必须同时运行。保持前端终端运行。

## 6. 访问与检查

1. 浏览器打开 <http://127.0.0.1:5173/login>，使用刚导入的**模拟网页账号**登录；不要使用 MySQL 连接账号代替网页账号。
2. 在后端终端观察是否启动成功；本机浏览器访问 <http://127.0.0.1:8000/> 可检查根接口是否响应，访问 <http://127.0.0.1:8000/docs> 查看接口文档。访问 <http://127.0.0.1:8000/api/v1/health> 会对已配置数据库执行只读连接查询；成功响应说明当时连接可查询，不代表业务数据正确或设备在线。
3. 如需再次确认库结构，在后端停止后或另开终端执行上面的 `--check-only`。该检查需要连接本地练习库并具备读取元数据的权限，不会自动修复结构。
4. 登录后进入全国地图、河南路网、服务区或收费站场景。公开位置可能使用通用模型；私有站点三维显示取决于模板、场景和设备绑定。缺失或过期监测值不应当作真实零值。
5. 初始模拟数据中的模拟账号、站点和权限可按 C02 的查询结果核对；查看日志时不要分享密码、Token 或完整连接信息。

本地科技蓝图、省市边界、河南路网数据与随仓库提供的 GLB 模型从项目静态资源加载。安装 Python/npm 依赖需要网络；选择卫星影像且配置有效 Cesium ion Token 时会请求在线影像，网络或资源权限异常时可能回退到本地低清影像。实际显示效果还受浏览器、WebGL 和设备性能影响。

## 常见问题

- **`mysql` 命令不存在**：确认 MySQL 客户端已安装、可执行文件在 PATH 中，并确认 MySQL 服务已启动。
- **后端提示配置缺失或签名密钥过短**：检查根目录 `.env.mysql.local` 的数据库密码、端口和至少 32 字符的签名密钥；不要输出实际值。
- **MySQL 连接或结构读取失败**：检查是否连接到独立练习库、服务端口、账号权限和建表是否成功。已有旧表不会被 C00 自动迁移。
- **网页登录账号或密码错误**：确认已导入 C01，使用模拟网页账号而非数据库连接账号；若此前修改过模拟密码，重跑脚本不会自动重置已有账号。
- **写入被禁止或没有权限**：检查本地写入开关、MySQL 表权限、登录角色和站点范围；只读用户不能执行管理操作。
- **端口被占用或 `WinError 10013`**：先确认是否已有服务、端口限制或绑定权限问题。端口绑定错误不是浏览器跨域错误；不要盲目终止其他进程。
- **页面请求后端失败**：确认前后端均在运行，前端从 5173 访问且 Vite 代理指向 8000；修改端口时需要同步核对代理与后端访问限制。
- **地图影像或模型不显示**：检查浏览器 WebGL、网络、Token 权限、开发者工具报错及 `smart_power_web/public/` 中的资源；在线影像不可用时科技蓝图和本地低清影像与在线影像的表现不同。
- **`npm ci` 或 pip 安装失败**：检查版本、网络及安装错误；`npm ci` 使用锁文件，不能用来证明另一台电脑已经验证成功。

## Docker 与验证状态

仓库可能含 Docker 练习文件，但截至本 README 编写时，它们在当前工作区尚未跟踪，且没有完成目标 Ubuntu 虚拟机的全流程构建和验收；克隆后的版本**不保证包含这些文件**。即使存在，也不能视为已经跑通；应在独立虚拟机、独立数据库中分别验证构建、SQL 导入、登录、地图及模型展示。当前推荐先按上面的本机流程理解项目。

2026-11-07：本 README 根据当前源码、配置模板和 SQL 文件静态核对编写；**本次没有在全新电脑或 Ubuntu 虚拟机执行克隆、安装、SQL 导入及运行验收**。历史测试记录只表示当时的测试范围，不等同于本次新机验证。
