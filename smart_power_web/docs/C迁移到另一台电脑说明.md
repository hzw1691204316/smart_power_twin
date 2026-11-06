# 迁移到另一台电脑说明

本文说明把本项目拷贝到另一台电脑时要带什么、不要带什么，以及新电脑上如何跑起来。
最小可行方案：只携带约 13 MB 的源码与数据，`node_modules`（341.5 MB）等机器相关产物在新电脑重新生成——这是唯一跨平台都安全的做法。
如果另一台电脑也是 **Windows x64**，可以把 `node_modules` 一起拷以省去重新安装，前提条件和命令见第五节。

## 一、必须拷贝

| 内容 | 说明 |
| --- | --- |
| `src/` | 全部前端源码（Vue/TS）。 |
| `public/` | 地图数据与模型，约 12 MB。`public/maps/**`（全国与省市 geojson、河南高速路网、设施点位、南海小图）和 `public/models/*.glb`（两个约 5 MB 的第四版模型）是仓库内文件，不拷就没有地图和三维模型。 |
| `scripts/` | `check-directory.mjs`、`check-map-layers.mjs`、`prepare-province-outlines.mjs`，`npm run verify` 依赖前两个。脚本内全部使用相对路径，换目录不影响。 |
| `package.json`、`package-lock.json` | 依赖清单与锁定版本，两个都要拷，才能在新电脑装出同一套依赖。 |
| 根目录配置 | `vite.config.ts`、`index.html`、`tsconfig.json`、`tsconfig.app.json`、`tsconfig.node.json`、`env.d.ts`、`eslint.config.ts`、`.oxlintrc.json`、`.prettierrc.json`、`.editorconfig`、`.gitattributes`。 |
| `.env.local` | 只有一项 `VITE_CESIUM_ION_TOKEN`。**必须单独确认它跟着走了**：`.gitignore` 里的 `*.local` 会忽略它，用 git 或编辑器整体拷目录时最容易漏。缺它不会崩，但地图退回本地低清底图。 |
| `docs/`、`README.md`、`AGENTS.md` | 续接记录与开发约定，换电脑后继续开发要靠它们对齐。 |

## 二、不要拷贝

| 内容 | 原因 |
| --- | --- |
| `node_modules/`（341.5 MB / 13819 个文件） | 含平台相关原生二进制，当前只装了 Windows x64 版本：`@oxlint/binding-win32-x64-msvc`、`@rolldown/binding-win32-x64-msvc`、`lightningcss-win32-x64-msvc`。拷到 macOS、Linux 或 Windows ARM64 上必然启动失败。**若另一台也是 Windows x64，可以整目录拷，见第五节**；否则在新电脑执行 `npm install` 重建。 |
| `dist/`（23.7 MB） | 旧构建产物，其中 `dist/cesiumStatic/` 是从 `node_modules/cesium` 复制来的，新电脑重新 `npm run build` 即可生成。 |
| `.eslintcache` | 本机 lint 缓存，删掉无影响，保留反而可能命中旧路径。 |
| `*.tsbuildinfo` | TypeScript 增量构建信息，同上是本机缓存。 |
| `.vscode/`、`.idea/` | 本机 IDE 设置。可拷（体积可忽略），但不是运行必需。 |
| 上级目录的 `.venv/`（28.3 MB） | Python 虚拟环境把解释器路径写死在内部（`.idea/workspace.xml` 也记录了 `$PROJECT_DIR$/.venv/Scripts/python.exe`）。**绝对不能跨机拷贝**，只能在新电脑用 `python -m venv .venv` 重建。 |
| `_dsh-acl-recovery/`（上级目录） | 仅本机排查权限时生成的报告，与项目无关。 |

## 三、新电脑上的步骤

1. 安装 Node.js，版本要满足 `package.json` 的 `engines`：`^22.18.0 || >=24.12.0`。当前开发机是 Node v24.21.0 / npm 11.19.0。
2. 把拷来的目录放到任意路径（路径里有中文或空格也可以，项目内无绝对路径依赖），进入该目录后执行：
   ```sh
   npm install
   ```
   若另一台也是 Windows x64 且已按第五节连 `node_modules` 一起拷，可跳过这步直接进第 3 步；跑一次 `npm install` 仍是最稳的自检方式。
3. 确认根目录有 `.env.local`，且其中 `VITE_CESIUM_ION_TOKEN=` 后是与本机一致的 Cesium ion Token；没有就从 `.env.example` 复制一份再填。填好后重启 Vite 才会生效。
4. 启动开发服务器：
   ```sh
   npm run dev
   ```
   访问 http://127.0.0.1:5173 。`vite.config.ts` 里写的是 `host: 127.0.0.1`、`port: 5173`、`strictPort: true`，所以：① 只监听本机，局域网其他机器访问不到，这与防火墙无关；② 5173 被别的程序占用时 Vite 会直接报错退出，不会自动换端口。
5. 想验证环境是否完整，执行：
   ```sh
   npm run verify
   ```
   它依次跑 `lint` → `check:regression` → `check:map-layers` → `build`，能同时验证依赖、地图数据和构建链是否正常。

## 四、其他会影响运行的点

- **Cesium 静态资源来自 `node_modules`**：`vite.config.ts` 用 `viteStaticCopy` 把 `node_modules/cesium/Build/Cesium` 下的 `Workers`、`ThirdParty`、`Assets`、`Widgets` 复制到 `dist/cesiumStatic/`。所以不先 `npm install` 就没有 Cesium，构建也会失败。
- **需要联网**：Cesium ion 在线影像、以及 `scripts/prepare-province-outlines.mjs` 里引用的阿里云 DataV 边界数据（`https://geo.datav.aliyun.com/...`）都依赖网络。前者还要 Token 有效且允许来源匹配。
- **后端不在本项目范围内**：上级目录的 `main.py` 只是一个 FastAPI 示例（`/` 与 `/hello/{name}` 两个路由），前端目前不调用它，`src/` 内没有任何 `localhost` / `http://` 后端地址。要跑后端需在新电脑重建 Python 环境；不跑后端不影响前端页面。
- **Token 属于浏览器可见凭据**：它会打进前端产物，`.env.example` 里也已经写着一个同格式的 Token。分享项目目录或 zip 前想清楚要不要带上它，并尽量在 Cesium ion 侧限制允许来源。
- **数据署名与在线底图**：卫星影像为 Cesium ion，路网/边界数据署名见 `public/maps/C地图数据来源与使用说明.md`，换机器后这些署名仍须可见。

## 五、另一台也是 Windows x64 时：可以把 `node_modules` 一起拷

本节针对 **Windows x64 → Windows x64**。已实测本机 `node_modules` 具备整体搬移的条件：

- **没有软链接/联接点**：`node_modules` 下重解析点数量为 0；`node_modules/.bin` 里是 `vite`、`vite.cmd`、`vite.ps1` 普通文件，`.cmd` 用 `%~dp0` 定位自身，能跟着目录走。所以之前"`.bin` 软链会失效"的顾虑在 Windows 上不成立（npm 在 Windows 装的是 `.cmd`/`.ps1` 包装脚本，不是软链）。
- **原生二进制是 N-API 预编译产物**，与 Node 的 ABI 版本无关，只与平台绑定：
  - `@oxlint/binding-win32-x64-msvc/oxlint.win32-x64-msvc.node`（13.2 MB）
  - `@rolldown/binding-win32-x64-msvc/rolldown-binding.win32-x64-msvc.node`（20.4 MB）
  - `lightningcss-win32-x64-msvc/lightningcss.win32-x64-msvc.node`（9.0 MB）

  目录里没有任何 `win32-ia32`、`win32-arm64`、`darwin`、`linux` 版本，也没有 `@esbuild` —— 平台是唯一的硬约束。
- **依赖优化缓存没有写死路径**：`node_modules/.vite` 里检索本机绝对路径为 0 处。

只要同时满足下面四条，直接拷 `node_modules`（13819 个文件 / 341.5 MB）比重新下载安装更快：

1. 目标机是 **Windows x64**。Windows on ARM（骁龙本）虽然能跑 x64 模拟，但不要冒这个险，直接 `npm install`。
2. 目标机 Node 版本满足 `^22.18.0 || >=24.12.0`。
3. **目标路径要短**：`node_modules` 内最长相对路径 117 字符（本机根目录 64 字符 + 117 = 最长绝对路径 181 字符）。Windows 默认 260 字符上限，所以目标根目录建议控制在约 140 字符以内；`D:\project\smart_power_web` 这类完全没问题，但不要塞进很深的目录树。
4. 拷贝时**没有 node / vite / npm 进程在运行**，并用 robocopy 而不是资源管理器拖拽（保留空目录、13k 小文件速度差距明显）。

在源机执行（`<目标>` 换成 U 盘、移动硬盘或共享路径）：

```powershell
robocopy "D:\study_software\PythonProject\smart_power_twin\smart_power_web" "<目标>\smart_power_web" /E /XD dist .portable-stage /XF .eslintcache /MT:16 /R:1 /W:1
```

到新电脑后先清掉本机缓存，再启动（建议顺带跑一次 `npm install` 自检，依赖齐全时很快）：

```powershell
Remove-Item node_modules\.vite, node_modules\.vite-temp, node_modules\.vue-global-types -Recurse -Force -ErrorAction SilentlyContinue
npm.cmd install
npm.cmd run dev
```

新电脑完全没有网络时可跳过 `npm install` 直接 `npm.cmd run dev`。若仍失败，把有网机器的 npm 缓存（本机在 `C:\Users\xxu20\AppData\Local\npm-cache`）拷过去，执行 `npm.cmd ci --offline` 修复。

`dist/`（23.7 MB 纯静态产物，不含原生二进制）在 Windows 同平台下同样能拷，但没必要，重新 `npm run build` 更干净。

## 六、本次未验证项

- 未在第二台电脑上实际执行 `npm install` 与 `npm run dev`，因此 Node 版本差异、网络代理、磁盘权限等因素的实际影响未经验证。
- 第五节"Windows x64 连 `node_modules` 一起拷"只验证了搬移前提（无软链、N-API 预编译、无写死路径、路径长度 181/260），**没有真的在第二台 Windows 上解压运行过**。
- 未在 macOS / Linux 上试装依赖，跨平台兼容性只能从"原生二进制按平台分发"这一机制推断。
- 上级目录的 Python 后端未在本轮启动或验证。
