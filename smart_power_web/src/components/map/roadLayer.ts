import {
  Cartesian2,
  Cartesian3,
  Color,
  CustomDataSource,
  DistanceDisplayCondition,
  LabelStyle,
  PolylineOutlineMaterialProperty,
} from 'cesium'
import { demoHighways } from '@/data/demo'
import type { RoadCollection } from '@/types/map'
import { matchesHighway } from '@/utils/directory'
import { getMapElevation } from '@/config/mapPresentation'
import { mapFont } from '@/config/typography'
import { mapPalette } from '@/config/mapPalette'

export async function createRoadLayer(cityCode?: number): Promise<{
  source: CustomDataSource
  count: number
  isDemo: boolean
  filter: (highway: string) => number
}> {
  const source = new CustomDataSource('henan-expressways')
  const elevation = getMapElevation('henan', !!cityCode)
  function filter(highway: string): number {
    let count = 0
    for (const entity of source.entities.values) {
      entity.show = matchesHighway(entity.properties?.routeRef?.getValue(), highway)
      if (entity.show && entity.polyline) count++
    }
    return count
  }
  try {
    const response = await fetch(
      cityCode ? `/maps/cities/${cityCode}-expressways.geojson` : '/maps/henan-expressways.geojson',
    )
    if (!response.ok) throw new Error('no road data')
    const data: RoadCollection = await response.json()
    if (data.type !== 'FeatureCollection' || !data.features.length)
      throw new Error('empty road data')
    const labels = new Set<string>()
    for (const [index, feature] of data.features.entries()) {
      if (feature.geometry.type !== 'LineString') continue
      const coordinates = feature.geometry.coordinates.flatMap(([lon, lat]) =>
        typeof lon === 'number' && typeof lat === 'number' ? [lon, lat] : [],
      )
      if (coordinates.length < 4) continue
      const ref = feature.properties.ref ?? ''
      const color = Color.fromCssColorString(
        ref.startsWith('G') ? mapPalette.roadNational : mapPalette.roadProvincial,
      )
      source.entities.add({
        id: `highway-segment-${index}`,
        properties: { routeRef: ref },
        polyline: {
          positions: Cartesian3.fromDegreesArrayHeights(
            coordinates.flatMap((value, i) =>
              i % 2 === 0 ? [value, coordinates[i + 1]!, elevation.road] : [],
            ),
          ),
          width: cityCode ? 4 : 3,
          material: new PolylineOutlineMaterialProperty({
            color,
            outlineColor: Color.fromCssColorString(mapPalette.roadEdge),
            outlineWidth: 0.65,
          }),
        },
      })
      if (ref && !labels.has(ref)) {
        labels.add(ref)
        const center =
          feature.geometry.coordinates[Math.floor(feature.geometry.coordinates.length / 2)]
        if (center && typeof center[0] === 'number' && typeof center[1] === 'number')
          source.entities.add({
            properties: { routeRef: ref },
            position: Cartesian3.fromDegrees(center[0], center[1], elevation.label),
            label: {
              text: ref,
              font: mapFont(12, 600),
              showBackground: true,
              backgroundColor: Color.fromCssColorString('#092c3b').withAlpha(0.9),
              backgroundPadding: new Cartesian2(5, 3),
              fillColor: Color.fromCssColorString('#a7f5f6'),
              style: LabelStyle.FILL_AND_OUTLINE,
              outlineColor: Color.fromCssColorString('#061622'),
              outlineWidth: 2,
              pixelOffset: new Cartesian2(0, 9),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
              distanceDisplayCondition: new DistanceDisplayCondition(0, cityCode ? 350000 : 700000),
            },
          })
      }
    }
    return { source, count: filter(''), isDemo: false, filter }
  } catch {
    if (cityCode) throw new Error('当前地市高速资源加载失败，请返回全省或刷新重试')
    for (const road of demoHighways)
      source.entities.add({
        properties: { routeRef: road.code },
        polyline: {
          positions: Cartesian3.fromDegreesArrayHeights(
            road.coordinates.flatMap((value, index) =>
              index % 2 === 0 ? [value, road.coordinates[index + 1]!, elevation.road] : [],
            ),
          ),
          width: 4,
          material: new PolylineOutlineMaterialProperty({
            color: Color.fromCssColorString(mapPalette.roadNational),
            outlineColor: Color.fromCssColorString(mapPalette.roadEdge),
            outlineWidth: 0.65,
          }),
        },
      })
    return { source, count: demoHighways.length, isDemo: true, filter }
  }
}
