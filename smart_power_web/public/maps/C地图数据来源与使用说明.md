# 地图资源来源与覆盖说明

下载与处理日期：2026-10-13。

## 行政区

- 中国省级区域：阿里云DataV.GeoAtlas，https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json 。包含34个有名称的省级区域及南海相关附加几何。
- 河南市级区域：https://geo.datav.aliyun.com/areas_v3/bound/410000_full.json ，18个市级区域。
- 入口：https://datav.aliyun.com/portal/school/atlas/area_selector 。保留原数据几何，未把矩形或手画多边形当作行政界线。
- 这些资源用于原型展示；行政区时效、坐标依据、公开发布所需的资源使用条件仍应在正式发布前向数据提供者核实。

## 河南高速与设施

- 数据来源：OpenStreetMap contributors，经Geo2Day提供的河南省域PBF快照提取，https://geo2day.com/asia/china/henan.html ，下载地址https://geo2day.com/asia/china/henan.pbf 。
- 数据许可：ODbL 1.0，https://www.openstreetmap.org/copyright 。地图保持OSM署名。发布派生数据库时按该许可履行相应义务。
- 提取highway=motorway主线，共30,232个原始路段；不含motorway_link匝道。按相同ref和name且连接度为2的端点合并，并进行约50米容差的展示简化，得到419条展示折线。419不是419条命名高速，不能当作路线数量统计。
- 公开设施：highway=services为服务区，barrier=toll_booth为收费设施。对约700米内的同类点做展示归并，最终214处服务区、630处收费设施。数量不代表官方设施总数，归并可能把邻近双侧设施合并，需台账核验。
- 面设施位置以几何节点平均位置表示，仅用于区域定位，不代表实际入口。未命名设施保留“未命名服务区”或“收费设施”，不编造名称。
- OSM坐标为WGS84。公开数据可能缺失、过期或存在分类差异；不保证交通部门最新全量、通车状态或精确测绘用途。
- henan-expressways.geojson为派生路网；henan-facilities.json为派生设施数据。元数据保留来源、下载日期、筛选和简化说明。

## 业务演示数据

6座可进入三维的样板来自src/data/demo.ts，明确带“演示”名称。与公开设施小点分开表示，不把公开位置当成已经绑定电力设备、模型和采集数据的真实资产。

## 2026-10-14：34个省级区域独立视图

province-index.json及provinces/*.geojson由现有china-provinces.geojson按adcode拆分，未新增外部地理数据。原几何保留；镜头对离散远海几何优先采用主体范围定位，不改变边界坐标。全国视图继续保留南海位置示意。

可运行 `node scripts/prepare-province-outlines.mjs` 重新生成。其他省级区域当前仅展示省域轮廓，不包含地市细分、高速路线、设施台账或电力数据。河南原有市级边界、高速路网及公开设施仍使用原资源。
