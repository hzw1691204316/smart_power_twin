import type { BoundaryFeature } from '@/types/map'

export function provincePath(code: number): string {
  return code === 410000 ? '/province/henan' : `/province/${code}`
}

export function provinceBounds(feature: BoundaryFeature) {
  const polygons =
    feature.geometry.type === 'Polygon'
      ? [feature.geometry.coordinates]
      : feature.geometry.coordinates
  if (!Array.isArray(polygons)) throw new Error('省域几何格式不正确')
  const rings: number[][][] = polygons.flatMap((polygon) => {
    const ring = Array.isArray(polygon) ? polygon[0] : undefined
    return Array.isArray(ring)
      ? [
          ring.filter(
            (point) =>
              Array.isArray(point) && typeof point[0] === 'number' && typeof point[1] === 'number',
          ),
        ]
      : []
  })
  if (!rings.length) throw new Error('省域没有可定位的边界')
  const area = (ring: number[][]) =>
    Math.abs(
      ring.reduce((sum, point, i) => {
        const next = ring[(i + 1) % ring.length]!
        return sum + point[0]! * next[1]! - next[0]! * point[1]!
      }, 0),
    )
  const bounds = (points: number[][]) => ({
    west: Math.min(...points.map((point) => point[0]!)),
    south: Math.min(...points.map((point) => point[1]!)),
    east: Math.max(...points.map((point) => point[0]!)),
    north: Math.max(...points.map((point) => point[1]!)),
  })
  const all = bounds(rings.flat())
  const main = bounds([...rings].sort((a, b) => area(b) - area(a))[0]!)
  // 远海附属几何仍保留在数据中，初始镜头优先主体，避免将陆地区域缩成小点。
  const chosen =
    all.east - all.west > (main.east - main.west) * 2.5 ||
    all.north - all.south > (main.north - main.south) * 2.5
      ? main
      : all
  const x = Math.max(0.03, (chosen.east - chosen.west) * 0.03)
  const y = Math.max(0.03, (chosen.north - chosen.south) * 0.03)
  return {
    west: chosen.west - x,
    south: chosen.south - y,
    east: chosen.east + x,
    north: chosen.north + y,
  }
}
