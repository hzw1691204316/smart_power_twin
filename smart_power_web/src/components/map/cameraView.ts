import {
  BoundingSphere,
  Cartesian3,
  HeadingPitchRange,
  Math as CesiumMath,
  Matrix4,
  Transforms,
  PerspectiveFrustum,
  type Viewer,
} from 'cesium'

export interface MapBounds {
  west: number
  south: number
  east: number
  north: number
}

/** 按画布视场及倾斜投影计算距离，避免全国图被保守包围球缩得过小。 */
export function comfortableRange(
  bounds: MapBounds,
  height: number,
  tilted: boolean,
  aspect: number,
  fovY: number,
  fill = 0.88,
): number {
  const center = regionSphere(bounds, height).center
  const inverse = Matrix4.inverseTransformation(
    Transforms.eastNorthUpToFixedFrame(center),
    new Matrix4(),
  )
  const pitch = CesiumMath.toRadians(tilted ? 62 : 90)
  const sin = Math.sin(pitch)
  const cos = Math.cos(pitch)
  const tan = Math.tan(fovY / 2)
  let range = 1000
  for (let x = 0; x <= 4; x++)
    for (let y = 0; y <= 4; y++) {
      const point = Cartesian3.fromDegrees(
        bounds.west + ((bounds.east - bounds.west) * x) / 4,
        bounds.south + ((bounds.north - bounds.south) * y) / 4,
        height,
      )
      const local = Matrix4.multiplyByPoint(inverse, point, new Cartesian3())
      const screenY = local.y * sin + local.z * cos
      const depth = local.y * cos - local.z * sin
      range = Math.max(
        range,
        Math.abs(local.x) / (tan * aspect * fill) - depth,
        Math.abs(screenY) / (tan * fill) - depth,
      )
    }
  return range
}

/** 用目标中心与包围球定向，倾斜后仍保持区域居中，兼顾不同画布宽高比。 */
export function regionSphere(bounds: MapBounds, height: number): BoundingSphere {
  const center = Cartesian3.fromDegrees(
    (bounds.west + bounds.east) / 2,
    (bounds.south + bounds.north) / 2,
    height,
  )
  const radius = Math.max(
    ...[
      [bounds.west, bounds.south],
      [bounds.west, bounds.north],
      [bounds.east, bounds.south],
      [bounds.east, bounds.north],
    ].map(([lon, lat]) => Cartesian3.distance(center, Cartesian3.fromDegrees(lon!, lat!, height))),
  )
  return new BoundingSphere(center, Math.max(radius * 1.08, 700))
}

export function flyToRegion(
  viewer: Viewer,
  bounds: MapBounds,
  height: number,
  tilted: boolean,
  duration: number,
  profile: 'country' | 'country-expanded' | 'region' | 'region-expanded' = 'region',
) {
  if (viewer.isDestroyed()) return
  const aspect = Math.max(0.3, viewer.canvas.clientWidth / Math.max(1, viewer.canvas.clientHeight))
  const fovY =
    viewer.camera.frustum instanceof PerspectiveFrustum
      ? (viewer.camera.frustum.fovy ?? CesiumMath.toRadians(40))
      : CesiumMath.toRadians(40)
  const range = comfortableRange(
    bounds,
    height,
    tilted,
    aspect,
    fovY,
    // 收起面板后适度扩大当前区域占比；省市多留一点边距，便于保留路网边缘。
    profile === 'country-expanded'
      ? 1.02
      : profile === 'country'
        ? 0.9
        : profile === 'region-expanded'
          ? 0.98
          : 0.86,
  )
  viewer.camera.flyToBoundingSphere(regionSphere(bounds, height), {
    offset: new HeadingPitchRange(0, CesiumMath.toRadians(tilted ? -62 : -90), range),
    duration,
  })
}
