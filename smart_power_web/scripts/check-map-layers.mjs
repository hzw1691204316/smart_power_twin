import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { registerHooks } from 'node:module'
import {
  Camera,
  CameraEventType,
  Cartesian3,
  Color,
  ColorMaterialProperty,
  JulianDate,
  GeographicProjection,
  Math as CesiumMath,
  PolylineGlowMaterialProperty,
  PolylineOutlineMaterialProperty,
  SceneMode,
  ScreenSpaceEventType,
} from 'cesium'

// 运行真实图层构建与主题切换，不依赖浏览器或WebGL。
const root = new URL('../', import.meta.url)
const sourceRoot = new URL('src/', root)
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith('@/'))
      return nextResolve(new URL(`${specifier.slice(2)}.ts`, sourceRoot).href, context)
    if (
      specifier.startsWith('.') &&
      context.parentURL?.startsWith(sourceRoot.href) &&
      !/\.[a-z]+$/i.test(specifier)
    )
      return nextResolve(`${specifier}.ts`, context)
    return nextResolve(specifier, context)
  },
})
const originalFetch = globalThis.fetch
globalThis.fetch = async (path) => {
  assert.ok(
    typeof path === 'string' && path.startsWith('/maps/'),
    'Only local map fixtures are allowed',
  )
  return new Response(await readFile(new URL(`public${path}`, root)), {
    headers: { 'Content-Type': 'application/json' },
  })
}
try {
  const { createAdministrativeLayers } =
    await import('../src/components/map/administrativeLayer.ts')
  const { createRoadLayer } = await import('../src/components/map/roadLayer.ts')
  const { mapPalette, nationalMapPalette } = await import('../src/config/mapPalette.ts')
  const { configureMapWheelZoom } = await import('../src/components/map/mapWheelZoom.ts')
  const { flyToRegion } = await import('../src/components/map/cameraView.ts')
  // 验证全国、省域及市域展开/收起仅改变距离，不累积缩放或改变中心/俯仰。
  for (const [bounds, height, profile] of [
    [{ west: 73, south: 17, east: 136, north: 54 }, 32000, 'country'],
    [{ west: 110.2, south: 31.3, east: 116.8, north: 36.5 }, 3500, 'region'],
    [{ west: 113.875, south: 35.324, east: 114.874, north: 36.173 }, 450, 'region'],
    [{ west: 114.1, south: 22.1, east: 114.5, north: 22.6 }, 300, 'region'],
  ]) {
    for (const tilted of [true, false]) {
      for (const width of [540, 1600, 2000]) {
        let flight
        const viewer = {
          isDestroyed: () => false,
          canvas: { clientWidth: width, clientHeight: 900 },
          camera: {
            flyToBoundingSphere: (sphere, options) => {
              flight = { sphere, options }
            },
          },
        }
        flyToRegion(viewer, bounds, height, tilted, 0, profile)
        const standard = flight
        flyToRegion(viewer, bounds, height, tilted, 0, `${profile}-expanded`)
        assert.ok(flight.options.offset.range < standard.options.offset.range)
        assert.ok(flight.options.offset.range > standard.options.offset.range * 0.75)
        assert.ok(Cartesian3.equals(flight.sphere.center, standard.sphere.center))
        assert.equal(flight.options.offset.pitch, standard.options.offset.pitch)
        assert.equal(flight.options.offset.heading, standard.options.offset.heading)
        for (let i = 0; i < 4; i++) {
          flyToRegion(viewer, bounds, height, tilted, 0, profile)
          assert.equal(flight.options.offset.range, standard.options.offset.range)
          flyToRegion(viewer, bounds, height, tilted, 0, `${profile}-expanded`)
        }
      }
    }
  }
  // 使用真实Cesium Camera连续缩放，验证立体及俯视的角度和高度边界。
  for (const [scope, surface, pitch] of [
    ['china', 32000, -62],
    ['henan', 3500, -62],
    ['henan', 450, -90],
    ['province', 3500, -62],
  ]) {
    const controller = {
      enableInputs: true,
      enableZoom: true,
      minimumZoomDistance: surface + 500,
      maximumZoomDistance: Infinity,
      zoomEventTypes: [CameraEventType.RIGHT_DRAG, CameraEventType.WHEEL, CameraEventType.PINCH],
    }
    const scene = {
      drawingBufferWidth: 1600,
      drawingBufferHeight: 900,
      mapProjection: new GeographicProjection(),
      mode: SceneMode.SCENE3D,
      screenSpaceCameraController: controller,
      requestRender() {},
    }
    const camera = new Camera(scene)
    const viewer = { camera, scene, isDestroyed: () => false }
    camera.setView({
      destination: Cartesian3.fromDegrees(113, 34, surface + 600000),
      orientation: { heading: 0.3, pitch: CesiumMath.toRadians(pitch), roll: 0.02 },
    })
    const actions = new Map()
    const originalZoomEvents = controller.zoomEventTypes
    configureMapWheelZoom(
      viewer,
      { setInputAction: (fn, type) => actions.set(type, fn) },
      scope,
      surface,
    )
    if (scope === 'china') {
      assert.equal(
        controller.zoomEventTypes,
        originalZoomEvents,
        'National zoom must stay unchanged',
      )
      assert.equal(actions.size, 0)
      continue
    }
    assert.ok(!controller.zoomEventTypes.includes(CameraEventType.WHEEL))
    const wheel = actions.get(ScreenSpaceEventType.WHEEL)
    assert.ok(wheel)
    const orientation = [camera.heading, camera.pitch, camera.roll]
    const initialHeight = camera.positionCartographic.height
    wheel(120)
    assert.ok(camera.positionCartographic.height < initialHeight, 'Forward wheel must zoom in')
    wheel(-120)
    assert.ok(
      camera.positionCartographic.height > initialHeight * 0.99,
      'Reverse wheel must zoom out',
    )
    for (const delta of [120, -120])
      for (let i = 0; i < 140; i++) {
        wheel(delta)
        for (const [index, value] of [camera.heading, camera.pitch, camera.roll].entries())
          assert.ok(
            Math.abs(value - orientation[index]) < 1e-8,
            'Wheel must preserve map orientation',
          )
        const height = camera.positionCartographic.height
        assert.ok(height >= surface + 500 - 0.001 && height <= surface + 20000000 + 0.001)
      }
    const stoppedPosition = Cartesian3.clone(camera.positionWC)
    for (const delta of [0, NaN, Infinity]) wheel(delta)
    controller.enableInputs = false
    wheel(120)
    controller.enableInputs = true
    controller.enableZoom = false
    wheel(120)
    assert.ok(Cartesian3.equals(stoppedPosition, camera.positionWC))
  }
  const provinces = JSON.parse(
    await readFile(new URL('public/maps/province-index.json', root), 'utf8'),
  ).provinces
  const time = JulianDate.now()
  for (const [scope, city, province] of [
    ['china', false, undefined],
    ['henan', false, undefined],
    ['henan', true, undefined],
    ['province', false, provinces.find((item) => item.code === 370000)],
  ]) {
    const attached = []
    const viewer = {
      isDestroyed: () => false,
      scene: { requestRender() {} },
      dataSources: {
        async add(source) {
          attached.push(source)
          return source
        },
      },
    }
    const layer = await createAdministrativeLayers(viewer, scope, () => false, city, province)
    assert.ok(layer && attached.length === 2)
    assert.ok(layer.polygons.entities.values.some((entity) => entity.polygon))
    assert.ok(
      layer.polygons.entities.values.every((entity) => !entity.polygon?.extrudedHeight),
      'Top surfaces must not add a second extrusion',
    )
    assert.ok(
      layer.details.entities.values.every((entity) => !entity.polygon),
      'The base must not contain a horizontal polygon cap',
    )
    const walls = layer.details.entities.values.filter((entity) => entity.wall)
    assert.ok(walls.length > 0)
    for (const wall of walls)
      assert.ok(wall.wall.maximumHeights.getValue(time).every((height) => height > 0))
    layer.select(province?.code ?? 410000, 'blue')
    assert.ok(walls.every((entity) => entity.show))
    const outlines = layer.details.entities.values.filter((entity) => entity.polyline)
    assert.ok(outlines.length > 0)
    const expectedMaterial =
      scope === 'china' ? PolylineGlowMaterialProperty : ColorMaterialProperty
    assert.ok(
      outlines.every((entity) => entity.polyline.material instanceof expectedMaterial),
      'Only the national blue map uses glowing administrative boundaries',
    )
    for (const entity of layer.polygons.entities.values) {
      if (!entity.polygon || entity.properties?.adcode?.getValue(time) !== 410000) continue
      assert.ok(
        Color.equals(
          entity.polygon.material.getValue(time).color,
          Color.fromCssColorString(
            scope === 'china' ? nationalMapPalette.selectedSurface : mapPalette.selectedSurface,
          ),
        ),
        'National selection colors must not replace province/city colors',
      )
    }
    layer.select(province?.code ?? 410000, 'satellite')
    assert.ok(
      walls.every((entity) => !entity.show),
      'Satellite mode must hide side walls',
    )
    assert.ok(
      outlines.every((entity) => entity.polyline.material instanceof ColorMaterialProperty),
      'Satellite boundary styling must remain unchanged',
    )
    layer.select(province?.code ?? 410000, 'blue')
    assert.ok(
      walls.every((entity) => entity.show),
      'Blue theme must restore side walls',
    )
    assert.ok(outlines.every((entity) => entity.polyline.material instanceof expectedMaterial))
  }
  for (const cityCode of [undefined, 410600]) {
    const road = await createRoadLayer(cityCode)
    assert.equal(road.isDemo, false)
    assert.ok(
      road.source.entities.values
        .filter((entity) => entity.polyline)
        .every((entity) => entity.polyline.material instanceof PolylineOutlineMaterialProperty),
    )
    assert.ok(road.filter(cityCode ? 'S26' : 'G4') > 0)
  }
  console.log(
    'Passed: real Camera wheel zoom with fixed province pitch and unchanged national controls; map layers, cap-free walls, theme switches and highway filters.',
  )
} finally {
  globalThis.fetch = originalFetch
  hook.deregister()
}
