# 智慧电力数字孪生前端

后端已统一为MySQL，前端登录入口为http://127.0.0.1:5173/login。旧demo账号入口已清理，mysql_admin/mysql_viewer初始密码见桌面说明与本机临时提示。

账号、授权和状态持久保存；按用户要求密码明文存于sys_user.password，前端正常提交密码，不做哈希。改密工具已移除，可直接在数据库修改password列。地图、GLB和明确标注的电力样例仍保留。刷新浏览器仍需重新登录。

最新状态见[统一运行与明文密码](../docs/CMySQL统一运行与明文密码说明.md)。修改前运行npm.cmd run check:regression，修改后运行npm.cmd run verify。其他模块保持暂停。

省市地图滚轮缩放现保留相机俯仰角与朝向，避免放大时越变越斜；全国地图滚轮保持原行为。详见[省份地图滚轮修复](docs/C省份地图滚轮缩放修复说明.md)。

全国地图按最新参考图恢复深蓝块面、青蓝发光省界和河南高亮，仅对全国蓝图生效；省市路网、卫星主题、现有布局和三维入口不变。见[全国地图发光风格调整](docs/C中国地图发光风格调整说明.md)。

最新修复：地图底座改为无顶盖的垂直侧壁，移除与地图表面重叠的Polygon盖面，处理三角斑纹。见[三角斑纹修复说明](docs/C地图三角斑纹修复说明.md)。

地图立体效果现采用平整顶面与深色实体底座，取消重复底部亮线；省市路网图的行政边界与高速分别使用细暗线、明亮实线。见[立体地图与路网分层改进](docs/C立体地图底座与路网分层改进.md)。

全国图支持34个省级入口，镜头按区域与窗口自动适配。河南保留高速业务页，其他省级区域先展示独立轮廓地图；说明见[全国视野与34个省级入口](docs/C全国地图视野与34个省级入口_续接记录.md)。

地图现铺满页头下方工作区，左右面板半透明悬浮，支持收起；地图设置在左侧，图例在右侧，原页面说明底栏已移除。最新记录见[悬浮地图与侧栏布局](docs/C悬浮地图与侧栏布局_续接记录.md)。

字体与数字排版已统一。修改前运行 `npm.cmd run check:regression`，修改后运行 `npm.cmd run verify`；检查流程和当前视觉验收限制见[字体排版与回归检查说明](docs/C字体排版与回归检查说明.md)。后续开发约定记录在根目录AGENTS.md。

全国页与河南省市页现已统一紧凑页头，四项统计集成到左右侧栏。地图新增区域厚度、倾斜视角与俯视切换；最新记录见[全国页布局与立体地图续接](docs/C全国页紧凑布局与立体地图_续接记录.md)。

当前采用统一海蓝主题和圆角卡片界面。地图服务区/收费设施标记支持单击进入三维：已绑定朝歌实例使用绑定场景，其他公开位置按类型打开通用模板，保留名称和坐标并明确标注演示数据。说明见[海蓝主题与三维入口改进](docs/C海蓝主题与三维入口改进说明.md)。

站点三维页现采用全幅场景、蓝色半透明侧面板和底部功能栏。可直接查看`/sites/henan-service-01`或`/sites/henan-toll-01`；布局与下一步见[三维数字大屏续接记录](docs/C三维数字大屏_参考布局改进与续接.md)。

Vue 3 + TypeScript + Pinia + Cesium立体地图（可切换俯视）+ Three.js站点模型。

2026-10-14：已增加公开位置检索、动态路线筛选、省市导航状态保留和朝歌配对实例快捷入口。当前评审、实施范围与下阶段任务见[系统评审与改进方案](docs/C系统评审与改进实施方案_2026-10-14.md)。可在本目录运行 `node scripts/check-directory.mjs` 核对检索规则、地图数据和GLB设备锚点。

## 本项目启动与配置

依赖已安装。在本目录执行`npm.cmd run dev`，打开http://127.0.0.1:5173。

换电脑或把项目拷到另一台机器时，带什么、不带什么以及新机启动步骤见[迁移到另一台电脑说明](docs/C迁移到另一台电脑说明.md)（含 Windows x64 连`node_modules`一起拷的前提条件与命令）。

编辑根目录`.env.local`中的`VITE_CESIUM_ION_TOKEN=`，填入你的Cesium Token并重启Vite。未填写时使用本地低清底图，填写后加载在线影像。前端Token可见，请限制允许来源与资源权限。

页面流程：全国概览 → 河南路网 → 选择站点 → 三维模型 → 设备电力信息。

全国页已支持蓝色省域地图与省份选择，河南页接入公开高速路网与设施位置。电力指标、曲线、告警和6座已绑定样板为演示；模型使用用户指定桌面第四版拟真GLB。当前无需启动后端。

地图默认科技蓝图，可切换卫星影像。青绿色点为服务区，橙色点为收费设施。公开位置可通过列表或地图检索定位；朝歌服务区与收费站绑定通用三维样板，其余公开位置尚未绑定设备。数据源与覆盖见public/maps/C地图数据来源与使用说明.md。

目录说明、待补数据、检查结果和明天任务见[开发说明与续接记录](docs/C前端开发说明与续接记录.md)。

## 脚手架参考

This template should help get you started developing with Vue 3 in Vite.

## Recommended IDE Setup

[VS Code](https://code.visualstudio.com/) + [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Recommended Browser Setup

- Chromium-based browsers (Chrome, Edge, Brave, etc.):
  - [Vue.js devtools](https://chromewebstore.google.com/detail/vuejs-devtools/nhdogjmejiglipccpnnnanhbledajbpd)
  - [Turn on Custom Object Formatter in Chrome DevTools](http://bit.ly/object-formatters)
- Firefox:
  - [Vue.js devtools](https://addons.mozilla.org/en-US/firefox/addon/vue-js-devtools/)
  - [Turn on Custom Object Formatter in Firefox DevTools](https://fxdx.dev/firefox-devtools-custom-object-formatters/)

## Type Support for `.vue` Imports in TS

TypeScript cannot handle type information for `.vue` imports by default, so we replace the `tsc` CLI with `vue-tsc` for type checking. In editors, we need [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) to make the TypeScript language service aware of `.vue` types.

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## Project Setup

```sh
npm install
```

### Compile and Hot-Reload for Development

```sh
npm run dev
```

### Type-Check, Compile and Minify for Production

```sh
npm run build
```

### Lint with [ESLint](https://eslint.org/)

```sh
npm run lint
```
