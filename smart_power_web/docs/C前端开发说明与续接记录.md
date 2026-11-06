# 智慧电力前端：开发说明与续接记录

> 地图已在后续一轮升级：当前地图功能、公开省域路网与设施数据、验证限制和下一步以[地图科技大屏改进与续接](C地图科技大屏_改进与续接.md)为准。下文保留首轮建设记录。

更新时间：2026-10-13。前端目录：D:/study_software/PythonProject/smart_power_twin/smart_power_web。

## 1. 必须保留的用户要求

- 只修改smart_power_web前端目录，不修改其同级或其他后端项目，不创建或迁移数据库。
- 中国地图与省级地图采用Cesium；省级先实现河南。
- 页面分层、布局拆分、组件化；不把地图、模型与业务集中到单一组件。
- Cesium AccessToken由用户填写，不能把真实Token提交到仓库或打印日志。
- 收费站模型使用桌面C收费站三维模型_第四版_拟真中的C中型收费站.glb；服务区使用C服务区三维模型_第四版_拟真中的C中型服务区.glb。已确认与前端副本SHA256相同。
- 关注账户额度，临近上限时先更新这份文档，下一次从记录继续。

## 2. 本次完成内容

路由：全国概览/overview → 河南路网/province/henan → 站点孪生/sites/:siteId；未知页面有404引导。

全国页面：Cesium二维中国范围视野、河南入口、演示统计与能源观察。

河南页面：G4/G30演示折线、6个演示站点、名称/城市/编码搜索、类型和路线筛选、地图与站点卡片选中、视野复位、图层开关、站点摘要与3D入口。

站点页面：已复用第四版GLB；Three.js提供旋转缩放、复位、模型拾取与选中框；列表可选储能柜、变压器、光伏和充电桩，展示演示电力指标。离线样例不展示当前读数。图表是明确标注的形态示意。

Cesium采用SCENE2D，未设置Token时加载随Cesium依赖提供的本地NaturalEarthII低分辨率底图，失败时用网格兜底；配置Token后请求Cesium ion在线影像。未启用在线地形或OSM建筑。版权署名保持显示，没有隐藏Cesium credits。

资源：Vite配置复制Workers、ThirdParty、Assets、Widgets到cesiumStatic；CESIUM_BASE_URL通过编译常量指定。生产部署当前默认站点根路径，如需子目录需同步调整Cesium和模型资源路径。

## 3. 用户如何启动与填写Token

依赖已安装，无需再次创建Vue工程。在自己的PowerShell执行：

```powershell
Set-Location 'D:\study_software\PythonProject\smart_power_twin\smart_power_web'
npm.cmd run dev
```

打开终端显示的http://127.0.0.1:5173。端口设置为strictPort，已占用时会报错而不是自动换端口。此前原型可能也运行在5173，遇到占用先停止自己已有服务，不强制结束不明进程。

前端根目录有.env.example。在根目录新建或编辑.env.local：

```dotenv
VITE_CESIUM_ION_TOKEN=在这里填你的CesiumToken
```

不要把整段说明或引号外额外文字写成Token。保存后停止并重启Vite。*.local已被.gitignore忽略。VITE_变量会进入浏览器构建，Token并非后端秘密；在Cesium ion中限制用途、资源和允许来源，允许你实际使用的localhost/127.0.0.1地址。仅需能读取所选影像资源的Token，不需要写入权限。

无Token时低清底图无法提供省级清晰道路细节，这是预期。在线图像也不自动提供站点台账、准确高速中心线或河南行政区轮廓；这些需要独立数据资源。

## 4. 目录职责

```text
src/
  layouts/AppLayout.vue          统一页头、导航、时间、页脚
  views/                        全国、河南、站点、404页面
  components/
    common/                     指标卡、内容面板
    map/CesiumMap.vue            Cesium初始化、视野、图层、点击与销毁
    sites/                      站点搜索筛选、列表卡片
    dashboard/EnergyTrend.vue   形态示意曲线
    twin/                       GLB场景交互、设备详情
  config/map.ts                 Token读取、全国与河南视野范围
  data/demo.ts                  站点、路线、设备演示数据
  services/siteService.ts       站点数据入口，后续换API
  stores/sites.ts               Pinia站点加载与统计
  types/domain.ts               Site、Device、Highway等类型
  styles/global.css             公共设计变量、布局、响应式样式
public/models/                  第四版收费站与服务区GLB副本
docs/                           本文档
```

新增依赖：cesium 1.146.0、three 0.186.1；开发依赖vite-plugin-static-copy 4.1.1、@types/three 0.186.0。原有Vue、Router、Pinia继续使用，真实解析版本以package-lock.json为准。Cesium与Three.js通过页面路由按需加载，避免所有引擎都在全国页初始化。

设备绑定目前是前端样例。GLB中主体名称和有限子部件通过明确规则映射objectKey；例如储能柜本体、door/vent等已列明子部件。处理了Blender数字后缀与Three.js名称规范化。后续应由数据库twin_object/twin_binding返回稳定标识，不继续扩充模糊前缀规则。

## 5. 缺少的数据与用户可补充内容

1. Cesium Token：由用户填写.env.local。
2. 真实站点台账：名称、唯一编码、坐标及坐标系、站型、规模、方向、路线归属。
3. 河南高速中心线与行政区边界：经过来源、授权与坐标核验的GeoJSON。当前路线只是稀疏演示折线，未绘制伪造行政边界。
4. 后端API约定：站点列表、当前发布场景、对象与测点绑定、最新值、历史、告警。当前前端不调用后端，也没有改后端。
5. 设备点表：object_key、设备编码、测点编码、单位、值类型、正负约定、刷新周期与陈旧阈值。
6. 页面视觉反馈：用户打开浏览器后核验地图与模型大小、文字可读性、性能，并提出调整。

所有站点名称、位置、指标、日用电和趋势均为演示，不能用来认定真实地理位置、实际装机容量或现场告警。多个站点暂复用同一中型模型，是模板展示，不是实测建筑复刻。

## 6. 检查结果与明确限制

- 首轮npm run build成功，包含vue-tsc类型检查与Vite生产构建。
- npm run lint成功，包含Oxlint与ESLint；Prettier已格式化代码。
- 本地NaturalEarthII资源存在，Cesium静态资源已在构建时复制。
- 两个前端GLB与用户指定桌面第四版GLB的SHA256完全一致。
- npm audit --omit=dev：0个生产依赖漏洞。完整audit报告6个high，链路涉及开发工具的braces/micromatch/chokidar等；未运行可能造成破坏性降级的audit fix --force。后续依据供应方修复版本评估升级。
- Cesium构建分块约4.2MB未压缩/1.12MB gzip，体积提示为已知项。已采用页面懒加载，但仍需实测首次加载与核显设备性能；不通过提高警告阈值宣称优化完成。
- 浏览器预览访问权限被拒绝，未实际检查WebGL画面、设备点击、缩放或Token在线影像。不能把编译通过描述为浏览器验收通过；不要绕过拒绝使用其他浏览器控制工具。用户主动授权后再进行浏览器验收。
- 当前未实现真实数据接入、登录、后台CRUD、历史采样查询与告警确认。无后端变更、无SQL执行。

## 7. 明天从哪里继续

先让用户运行页面并填写Token，检查全国影像与河南视野、筛选、站点选择、收费站/服务区模型加载。若用户明确授权浏览器验证，再操作浏览器。

之后按以下顺序推进：

1. 根据实际画面修复Cesium与Three.js运行期问题，验证连续切换页面不会泄漏WebGL上下文或事件。
2. 导入核验后的河南路网及行政边界资源，替换演示折线；核对坐标系。
3. 和用户确认后端接口响应结构，仅改前端services层适配；保持后端目录不动。
4. 用真实对象绑定替换demo.ts设备规则，接入最新值、历史曲线与质量/陈旧显示。
5. 增加权限与管理页面的前端部分；需要后端配合的事项先说明，不跨目录修改。
6. 基于实际笔记本的帧率、内存和加载时间进行模型与渲染优化。

每次继续先读取本文、package.json和相关组件，不必重做脚手架或重新复制模型。后续变更后执行npm.cmd run build与npm.cmd run lint，并更新本文检查日期和结果。

## 8. 额度记录

本轮开始时账户5小时窗口已用54%，周窗口已用8%；中段检查5小时已用60%，周已用9%。这是账户共享窗口，不是“每天固定额度”。接近上限时先保存当前改动与续接说明，不消耗免费重置。具体剩余以继续工作时的账户工具查询为准。

## 9. 本轮最终检查补充

最终一次npm.cmd run lint和npm.cmd run build均成功。生产目录Cesium四类静态资源及两个GLB均存在；修复了vite-plugin-static-copy新版保留node_modules层级导致资源路径不匹配的问题，配置rename.stripBase=4，输出路径与CESIUM_BASE_URL一致。

GLB 2.0头、总长度、JSON块及storage_01、transformer_01、pv_canopy、charger_01对象键已核对；收费站模型201个节点、服务区模型233个节点。两份模型哈希仍与桌面指定第四版文件一致。

根目录.env.local已创建，Token为空，用户直接填写即可。在线影像、地图点击、模型拾取和响应式画面仍需浏览器验收。当前未运行前端开发服务；用户按启动命令运行即可。

最终额度快照：5小时窗口已用63%（约余37%），周窗口已用10%（约余90%）。此为当时账户共享额度，不代表下一次会话的实时余量。
