import {
  Cartesian2,
  Cartesian3,
  Color,
  ColorMaterialProperty,
  Cartographic,
  ConstantProperty,
  CustomDataSource,
  GeoJsonDataSource,
  HeightReference,
  JulianDate,
  LabelStyle,
  PolygonHierarchy,
  PolylineGlowMaterialProperty,
  type Viewer,
} from 'cesium'
import type { BoundaryCollection, ProvinceRegion } from '@/types/map'
import { getMapElevation } from '@/config/mapPresentation'
import { mapFont } from '@/config/typography'
import { mapPalette, nationalMapPalette } from '@/config/mapPalette'
import { createRegionSideWall } from './regionSideWall'

export interface AdministrativeLayers {
  polygons: GeoJsonDataSource
  details: CustomDataSource
  select: (code: number, theme: 'blue' | 'satellite') => void
}

export async function createAdministrativeLayers(
  viewer: Viewer,
  scope: 'china' | 'henan' | 'province',
  isDisposed: () => boolean,
  city = false,
  province?: ProvinceRegion,
): Promise<AdministrativeLayers | undefined> {
  const response = await fetch(
    scope === 'china'
      ? '/maps/china-provinces.geojson'
      : (province?.boundaryUrl ?? '/maps/henan-cities.geojson'),
  )
  if (!response.ok) throw new Error('行政区资源暂时不可用')
  const geojson: BoundaryCollection = await response.json()
  if (geojson.type !== 'FeatureCollection' || !Array.isArray(geojson.features))
    throw new Error('行政区数据格式不正确')
  const polygons = await GeoJsonDataSource.load(geojson, {
    stroke: Color.fromCssColorString('#2b789e'),
    fill: Color.fromCssColorString('#104671'),
    strokeWidth: 1,
    credit: '行政区数据：阿里云 DataV.GeoAtlas',
  })
  if (isDisposed() || viewer.isDestroyed()) return
  const details = new CustomDataSource('administrative-labels-and-outlines')
  const elevation = getMapElevation(
    scope,
    city,
    province &&
      Math.max(
        province.bounds.east - province.bounds.west,
        province.bounds.north - province.bounds.south,
      ),
  )
  function elevated(positions: Cartesian3[], height: number) {
    return positions.map((position) => {
      const point = Cartographic.fromCartesian(position)
      return Cartesian3.fromRadians(point.longitude, point.latitude, height)
    })
  }
  const outlines: { entityId: string; code: number }[] = []
  for (const entity of polygons.entities.values) {
    if (!entity.polygon) continue
    entity.polygon.outline = new ConstantProperty(false)
    entity.polygon.heightReference = new ConstantProperty(HeightReference.NONE)
    entity.polygon.height = new ConstantProperty(elevation.surface)
    // 保留唯一顶面；底座仅绘制侧壁，避免水平盖面重叠造成三角斑纹。
    entity.polygon.extrudedHeight = undefined
    const code = Number(entity.properties?.adcode?.getValue())
    const hierarchy = entity.polygon.hierarchy?.getValue(JulianDate.now()) as
      PolygonHierarchy | undefined
    if (!hierarchy?.positions.length) continue
    const outline = details.entities.add({
      id: `boundary-${entity.id}`,
      properties: { adcode: code, name: entity.properties?.name?.getValue() ?? '' },
      polyline: {
        positions: elevated(hierarchy.positions, elevation.surface + 80),
        width: 0.8,
        material: Color.fromCssColorString(mapPalette.boundary),
      },
    })
    outlines.push({ entityId: outline.id, code })
    details.entities.add({
      id: `solid-base-${entity.id}`,
      properties: { adcode: code, name: entity.properties?.name?.getValue() ?? '' },
      wall: createRegionSideWall(
        hierarchy.positions,
        elevation.surface,
        Color.fromCssColorString(mapPalette.sideWall),
      ),
    })
  }
  for (const feature of geojson.features) {
    const point = feature.properties.centroid ?? feature.properties.center
    const name = feature.properties.name
    const code = Number(feature.properties.adcode)
    if (
      !name ||
      !point ||
      typeof point[0] !== 'number' ||
      typeof point[1] !== 'number' ||
      !Number.isFinite(code)
    )
      continue
    const shortName = name.replace(
      /壮族自治区|回族自治区|维吾尔自治区|自治区|特别行政区|省|市/g,
      '',
    )
    // 京津沪港澳的标注移交放大视野，减少全国初始视野的文字重叠。
    if (scope === 'china' && [110000, 120000, 310000, 810000, 820000].includes(code)) continue
    details.entities.add({
      id: `region-label-${code}`,
      position: Cartesian3.fromDegrees(point[0], point[1], elevation.label),
      properties: { adcode: code, name },
      label: {
        text: shortName,
        font: mapFont(14),
        fillColor: Color.fromCssColorString('#9acbe2'),
        outlineColor: Color.fromCssColorString('#071a2a'),
        outlineWidth: 4,
        style: LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new Cartesian2(0, scope === 'henan' && code === 410100 ? 22 : 0),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    })
  }
  await viewer.dataSources.add(polygons)
  await viewer.dataSources.add(details)
  if (isDisposed() || viewer.isDestroyed()) return
  function select(code: number, theme: 'blue' | 'satellite') {
    const alpha = theme === 'blue' ? 1 : 0.18
    const nationalBlue = scope === 'china' && theme === 'blue'
    for (const entity of polygons.entities.values) {
      if (!entity.polygon) continue
      const entityCode = Number(entity.properties?.adcode?.getValue())
      const selected = entityCode === code
      const henan = entityCode === 410000
      const color = Color.fromCssColorString(
        nationalBlue
          ? selected
            ? nationalMapPalette.selectedSurface
            : henan
              ? nationalMapPalette.henanSurface
              : nationalMapPalette.surface
          : selected
            ? mapPalette.selectedSurface
            : henan
              ? '#194e72'
              : mapPalette.surface,
      )
      // 小幅区域明暗变化，保留省市形状层次。
      if (!selected && Number.isFinite(entityCode)) color.blue += (entityCode % 5) * 0.004
      entity.polygon.material = new ColorMaterialProperty(color.withAlpha(alpha))
    }
    for (const outline of outlines) {
      const entity = details.entities.getById(outline.entityId)
      if (!entity?.polyline) continue
      const selected = outline.code === code
      entity.polyline.width = new ConstantProperty(
        nationalBlue ? (selected ? 3.5 : 1.6) : selected ? 1.3 : 0.8,
      )
      entity.polyline.material = nationalBlue
        ? new PolylineGlowMaterialProperty({
            color: Color.fromCssColorString(
              selected ? nationalMapPalette.selectedBoundary : nationalMapPalette.boundary,
            ).withAlpha(selected ? 1 : 0.8),
            glowPower: selected ? 0.25 : 0.18,
            taperPower: 1,
          })
        : new ColorMaterialProperty(
            Color.fromCssColorString(
              selected ? mapPalette.selectedBoundary : mapPalette.boundary,
            ).withAlpha(theme === 'blue' ? 0.85 : 0.65),
          )
    }
    for (const entity of details.entities.values) {
      if (entity.id.startsWith('solid-base-')) entity.show = theme === 'blue'
      if (!entity.label) continue
      const selected = Number(entity.properties?.adcode?.getValue()) === code
      entity.label.fillColor = new ConstantProperty(
        Color.fromCssColorString(selected ? '#e5fbff' : '#85b7d0'),
      )
      entity.label.font = new ConstantProperty(selected ? mapFont(16, 600) : mapFont(14))
    }
    viewer.scene.requestRender()
  }
  return { polygons, details, select }
}
