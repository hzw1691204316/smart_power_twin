import {
  CameraEventType,
  Cartesian3,
  Cartographic,
  Math as CesiumMath,
  ScreenSpaceEventType,
  type ScreenSpaceEventHandler,
  type Viewer,
} from 'cesium'

/** 以画面中心方向缩放，显式保留当地朝向，避免Cesium追随鼠标位置旋转镜头。 */
export function zoomWithFixedPitch(viewer: Viewer, delta: number, surface: number) {
  if (viewer.isDestroyed() || !Number.isFinite(delta) || delta === 0) return
  const controller = viewer.scene.screenSpaceCameraController
  if (!controller.enableInputs || !controller.enableZoom) return
  const camera = viewer.camera
  camera.cancelFlight()
  const orientation = { heading: camera.heading, pitch: camera.pitch, roll: camera.roll }
  const downward = -Math.sin(orientation.pitch)
  if (downward < 0.1) return
  const height = camera.positionCartographic.height
  const minimum = Math.max(surface + 500, controller.minimumZoomDistance)
  const maximum = Math.max(minimum, Math.min(surface + 20000000, controller.maximumZoomDistance))
  const factor = Math.exp(-CesiumMath.clamp(delta, -240, 240) * 0.0015)
  const targetHeight = CesiumMath.clamp(surface + (height - surface) * factor, minimum, maximum)
  if (Math.abs(targetHeight - height) < 0.001) return
  const movement = Cartesian3.multiplyByScalar(
    camera.directionWC,
    (height - targetHeight) / downward,
    new Cartesian3(),
  )
  const destination = Cartesian3.add(camera.positionWC, movement, new Cartesian3())
  // 球面移动会产生少量高度误差，再次限高防止连续滚轮穿过抬高的地图表面。
  const point = Cartographic.fromCartesian(destination)
  point.height = CesiumMath.clamp(point.height, minimum, maximum)
  camera.setView({
    destination: Cartesian3.fromRadians(point.longitude, point.latitude, point.height),
    orientation,
  })
  viewer.scene.requestRender()
}

export function configureMapWheelZoom(
  viewer: Viewer,
  handler: ScreenSpaceEventHandler,
  scope: 'china' | 'henan' | 'province',
  surface: number,
) {
  if (scope === 'china') return
  // 只替换省市图的滚轮，右键缩放与触屏双指操作保持Cesium原行为。
  viewer.scene.screenSpaceCameraController.zoomEventTypes = [
    CameraEventType.RIGHT_DRAG,
    CameraEventType.PINCH,
  ]
  handler.setInputAction(
    (delta: number) => zoomWithFixedPitch(viewer, delta, surface),
    ScreenSpaceEventType.WHEEL,
  )
}
