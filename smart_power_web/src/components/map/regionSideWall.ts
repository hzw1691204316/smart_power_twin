import { Cartesian3, WallGraphics, type Color } from 'cesium'

/** 只生成沿边界的垂直侧壁，不生成与地图顶面争抢深度的水平盖面。 */
export function createRegionSideWall(
  positions: Cartesian3[],
  height: number,
  material: Color,
): WallGraphics | undefined {
  if (positions.length < 3 || !Number.isFinite(height) || height <= 0) return undefined
  const ring = [...positions]
  if (!Cartesian3.equals(ring[0], ring[ring.length - 1])) ring.push(ring[0]!)
  return new WallGraphics({
    positions: ring,
    minimumHeights: ring.map(() => 0),
    maximumHeights: ring.map(() => height),
    material,
    outline: false,
  })
}
