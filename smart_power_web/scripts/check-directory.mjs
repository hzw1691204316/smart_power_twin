import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createPinia, setActivePinia } from 'pinia'
import { matchesHighway, matchesQuery, routeCodes } from '../src/utils/directory.ts'
import { useDirectoryStore } from '../src/stores/directory.ts'
import { demoSites } from '../src/data/demo.ts'
import { createFacilityScene } from '../src/services/facilityScene.ts'
import { largeServiceModel } from '../src/data/serviceModelCatalog.ts'
import { matchSceneObject } from '../src/utils/twinPresentation.ts'
import { getMapElevation } from '../src/config/mapPresentation.ts'
import { regionSphere, comfortableRange } from '../src/components/map/cameraView.ts'
import { provincePath } from '../src/utils/provinceCatalog.ts'
import { mapPalette } from '../src/config/mapPalette.ts'
import { createRegionSideWall } from '../src/components/map/regionSideWall.ts'
import { Cartesian3, Cartographic, Color, JulianDate, WallGeometry } from 'cesium'
import {
  siteSceneTarget,
  facilitySceneTarget,
  mapReturnPath,
} from '../src/utils/sceneNavigation.ts'

assert.equal(matchesHighway('G40', 'G4'), false)
assert.equal(matchesHighway('G0421', 'G4'), false)
assert.equal(matchesHighway('G4;AH1', 'G4'), true)
assert.equal(matchesHighway('G1516;S32', 'S32'), true)
assert.equal(matchesHighway('', 'S26'), false)
assert.deepEqual(routeCodes('g4;G4;AH1 S26'), ['G4', 'S26'])
assert.equal(matchesQuery(' 鹤壁 朝歌 ', '朝歌服务区', '鹤壁市'), true)
assert.equal(matchesQuery('鹤壁 朝歌', '洛阳服务区', '洛阳市'), false)

// 对实际Cesium几何检查：所有侧壁三角形均跨越上下高度，不存在水平顶盖。
for (const height of [120, 450, 3500, 32000]) {
  const original = Cartesian3.fromDegreesArray([113, 34, 114, 34, 114, 35, 113, 35])
  const wall = createRegionSideWall(original, height, Color.fromCssColorString(mapPalette.sideWall))
  assert.ok(wall)
  const time = JulianDate.now()
  const positions = wall.positions.getValue(time)
  assert.equal(original.length, 4, 'input boundary must not be mutated')
  assert.ok(Cartesian3.equals(positions[0], positions.at(-1)))
  const geometry = WallGeometry.createGeometry(
    new WallGeometry({
      positions,
      minimumHeights: wall.minimumHeights.getValue(time),
      maximumHeights: wall.maximumHeights.getValue(time),
    }),
  )
  assert.ok(geometry && geometry.indices.length > 0)
  const vertices = geometry.attributes.position.values
  for (let i = 0; i < geometry.indices.length; i += 3) {
    const heights = geometry.indices
      .slice(i, i + 3)
      .map((index) => Cartographic.fromCartesian(Cartesian3.fromArray(vertices, index * 3)).height)
    assert.ok(
      Math.max(...heights) - Math.min(...heights) > height * 0.9,
      'horizontal cap would overlap the top map',
    )
  }
}
assert.equal(createRegionSideWall([], 3500, Color.BLACK), undefined)

// 业务线路与行政底图须有足够配色对比，避免再次混成同亮度线网。
const luminance = (hex) => {
  const rgb = [1, 3, 5].map((index) => {
    const value = Number.parseInt(hex.slice(index, index + 2), 16) / 255
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  })
  return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722
}
for (const road of [mapPalette.roadNational, mapPalette.roadProvincial]) {
  for (const background of [mapPalette.surface, mapPalette.selectedSurface, mapPalette.boundary]) {
    assert.ok(
      (luminance(road) + 0.05) / (luminance(background) + 0.05) >= 3,
      'Roads must remain distinct from map surfaces and boundaries',
    )
  }
}

setActivePinia(createPinia())
const directory = useDirectoryStore()
Object.assign(directory.scope('henan'), { query: '朝歌', selectedId: 'henan-service-01' })
directory.scope('410600').query = '收费站'
assert.equal(directory.scope('henan').query, '朝歌')
assert.equal(directory.scope('henan').selectedId, 'henan-service-01')
assert.equal(directory.scope('410600').query, '收费站')

const root = new URL('../', import.meta.url)
// 保留两类地图页已确认的紧凑布局，防止只改河南页而漏掉全国页。
for (const page of ['OverviewView', 'ProvinceView']) {
  const source = await readFile(new URL(`src/views/${page}.vue`, root), 'utf8')
  assert.ok(!source.includes('class="page-title"'), `${page}: duplicate heading row`)
  assert.ok(!source.includes('class="metrics-grid"'), `${page}: full-width statistics row returned`)
  assert.equal((source.match(/class="sidebar-metrics"/g) ?? []).length, 2)
}
for (const [scope, city] of [
  ['china', false],
  ['henan', false],
  ['henan', true],
]) {
  const elevation = getMapElevation(scope, city)
  assert.ok(elevation.surface > 0)
  assert.ok(elevation.road > elevation.surface)
  assert.ok(elevation.marker > elevation.road)
  assert.ok(elevation.label > elevation.surface)
}
const json = async (path) => JSON.parse(await readFile(new URL(path, root), 'utf8'))
const provinceIndex = (await json('public/maps/province-index.json')).provinces
assert.equal(provinceIndex.length, 34)
assert.equal(new Set(provinceIndex.map((item) => item.code)).size, 34)
assert.equal(provincePath(410000), '/province/henan')
assert.equal(provincePath(370000), '/province/370000')
for (const province of provinceIndex) {
  const outline = await json(`public${province.boundaryUrl}`)
  assert.equal(Number(outline.features[0].properties.adcode), province.code)
  assert.ok(
    province.bounds.east > province.bounds.west && province.bounds.north > province.bounds.south,
  )
  const span = Math.max(
    province.bounds.east - province.bounds.west,
    province.bounds.north - province.bounds.south,
  )
  const height = getMapElevation('province', false, span).surface
  for (const aspect of [0.6, 1.78, 2.22]) {
    const wide = comfortableRange(province.bounds, height, true, aspect, Math.PI / 4, 0.86)
    assert.ok(Number.isFinite(wide) && wide > 0, `${province.name} camera range`)
    assert.ok(comfortableRange(province.bounds, height, true, aspect, Math.PI / 4, 0.95) <= wide)
  }
}
const roads = await json('public/maps/henan-expressways.geojson')
const cities = (await json('public/maps/henan-city-index.json')).cities
const facilities = (await json('public/maps/henan-facilities.json')).facilities
assert.deepEqual(siteSceneTarget('henan-service-01'), {
  name: 'site',
  params: { siteId: 'henan-service-01' },
  query: { origin: 'henan' },
})
for (const city of cities) {
  const target = facilitySceneTarget(facilities[0], city.code)
  assert.equal(mapReturnPath(target.query), `/province/henan/cities/${city.code}`)
}
assert.equal(mapReturnPath({ origin: 'henan' }, 410600), '/province/henan')
assert.equal(mapReturnPath({ origin: ['410600'] }, 410600), '/province/henan/cities/410600')
assert.equal(mapReturnPath({ origin: 'broken' }), '/province/henan')
assert.equal(mapReturnPath({ origin: '410000' }), '/province/henan')
assert.equal(mapReturnPath({ cityCode: '419001' }), '/province/henan/cities/419001')
assert.deepEqual(
  facilitySceneTarget({ ...facilities[0], boundSiteId: 'henan-toll-01' }, 410600),
  siteSceneTarget('henan-toll-01', 410600),
)
const deviceIds = new Set()
for (const facility of facilities) {
  const template = demoSites.find((site) => site.type === facility.type)
  const scene = createFacilityScene(facility, template, '测试地市')
  assert.equal(scene.id, facility.id)
  assert.equal(scene.name, facility.name)
  assert.equal(scene.longitude, facility.longitude)
  assert.equal(scene.latitude, facility.latitude)
  assert.equal(
    scene.modelUrl,
    facility.modelScale === 'L'
      ? largeServiceModel.modelUrl
      : facility.type === 'SERVICE'
        ? '/models/service_medium.glb'
        : '/models/toll_medium.glb',
  )
  assert.equal(scene.complexCode, undefined)
  assert.match(
    scene.locationNote,
    facility.modelScale === 'L' ? /大型双侧服务区能源设施方案/ : /通用模型预览/,
  )
  for (const device of scene.devices) {
    assert.ok(!deviceIds.has(device.id), `duplicate device ${device.id}`)
    deviceIds.add(device.id)
  }
}
// 公开预览按模型规模统一选用大型模板，多个实例ID必须独立，且不能继承模拟读数。
const zhengzhou = facilities.find((f) => f.id === 'osm-1317836742')
assert.equal(zhengzhou.name, '郑州服务区')
assert.equal(zhengzhou.cityCode, 410100)
const serviceTemplate = demoSites.find((s) => s.type === 'SERVICE')
const assignedScene = createFacilityScene(zhengzhou, serviceTemplate, '郑州市')
assert.equal(assignedScene.devices.length, 0)
assert.equal(assignedScene.publicModel.devices.length, 34)
assert.equal(assignedScene.publicModel.pvPanelCount, 154)
assert.ok(assignedScene.publicModel.devices.every((d) => d.status === 'unknown'))
assert.equal(assignedScene.powerKw, 0)
assert.equal(assignedScene.pvKw, 0)
assert.equal(assignedScene.dailyEnergyKwh, 0)
const assignedFile = await readFile(new URL(`public${assignedScene.modelUrl}`, root))
assert.equal(assignedFile.toString('ascii', 0, 4), 'glTF')
assert.equal(assignedFile.readUInt32LE(4), 2)
assert.equal(assignedFile.readUInt32LE(8), assignedFile.length)
const assignedModel = JSON.parse(
  assignedFile.toString('utf8', 20, 20 + assignedFile.readUInt32LE(12)).trim(),
)
for (const device of assignedScene.publicModel.devices) {
  const node = assignedModel.nodes.find((n) => n.name === device.objectKey)
  assert.ok(node?.children?.length, `${device.objectKey}: missing GLB parent/geometry`)
  assert.equal(matchSceneObject(node.name, assignedScene.publicModel.devices)?.id, device.id)
}
const otherFacility = createFacilityScene(
  { ...zhengzhou, id: 'other-id', modelScale: 'M' },
  serviceTemplate,
)
assert.equal(otherFacility.modelUrl, '/models/service_medium.glb')
assert.equal(otherFacility.publicModel, undefined)
// 大型模板可用于任意地市的服务区，与郑州名称或ID无关。
for (const city of [410100, 410300, 410600]) {
  const facility = { ...zhengzhou, id: `large-${city}`, name: '其他大型服务区', cityCode: city }
  const large = createFacilityScene(facility, serviceTemplate, '测试地市', 'L')
  assert.equal(large.modelUrl, largeServiceModel.modelUrl)
  assert.equal(large.scale, 'L')
  assert.equal(large.publicModel.devices.length, 34)
  assert.ok(large.publicModel.devices.every((d) => d.id.startsWith(`large-${city}-`)))
  const medium = createFacilityScene(facility, serviceTemplate, '测试地市', 'M')
  assert.equal(medium.scale, 'M')
  assert.equal(medium.modelUrl, '/models/service_medium.glb')
  assert.equal(medium.publicModel, undefined)
}
const tollTemplate = demoSites.find((s) => s.type === 'TOLL')
const toll = createFacilityScene({ ...zhengzhou, type: 'TOLL', modelScale: 'L' }, tollTemplate)
assert.equal(toll.modelUrl, '/models/toll_medium.glb')
for (const page of ['OverviewView', 'ProvinceView']) {
  const view = await readFile(new URL(`src/views/${page}.vue`, root), 'utf8')
  assert.ok(view.includes("name: 'service-template'"), `${page}: missing model entry`)
}
const router = await readFile(new URL('src/router/index.ts', root), 'utf8')
assert.ok(router.includes("path: '/templates/service-large'"))

assert.equal(
  mapReturnPath(facilitySceneTarget(zhengzhou, 410100).query),
  '/province/henan/cities/410100',
)
assert.throws(
  () =>
    createFacilityScene(
      { ...facilities[0], type: 'SERVICE' },
      demoSites.find((site) => site.type === 'TOLL'),
    ),
  /类型不匹配/,
)
assert.equal(roads.features.length, 416)
assert.equal(cities.length, 18)
for (const city of cities) {
  const data = await json(`public/maps/cities/${city.code}-expressways.geojson`)
  assert.ok(data.features.length > 0, `${city.name} has no routes`)
  const sphere = regionSphere(city.bounds, getMapElevation('henan', true).surface)
  assert.ok(
    Number.isFinite(sphere.radius) && sphere.radius >= 700,
    `${city.name}: invalid camera range`,
  )
}
const hebiRoads = await json('public/maps/cities/410600-expressways.geojson')
assert.ok(hebiRoads.features.some((road) => matchesHighway(road.properties.ref, 'S26')))
const pair = demoSites.filter((site) => site.complexCode === 'HEBI_CHAOGE_COMPLEX')
assert.equal(pair.length, 2)
assert.deepEqual(new Set(pair.map((site) => site.type)), new Set(['SERVICE', 'TOLL']))
for (const site of pair) {
  const facility = facilities.find((item) => item.id === site.publicFacilityId)
  assert.ok(facility, `${site.name} missing public facility`)
  assert.equal(facility.cityCode, 410600)
  assert.equal(facility.type, site.type)
  assert.equal(site.longitude, facility.longitude)
  assert.equal(site.latitude, facility.latitude)
  const file = await readFile(new URL(`public${site.modelUrl}`, root))
  assert.equal(file.toString('ascii', 0, 4), 'glTF')
  const model = JSON.parse(file.toString('utf8', 20, 20 + file.readUInt32LE(12)).trim())
  const meshNames = model.nodes.filter((node) => node.mesh !== undefined).map((node) => node.name)
  for (const device of site.devices) {
    assert.ok(
      meshNames.some((name) => name === device.objectKey),
      `${site.name}: ${device.objectKey} missing model anchor`,
    )
  }
}
const offline = demoSites.find((site) => site.status === 'offline')
assert.ok(offline.devices.every((device) => device.status === 'offline' && !device.metrics.length))
console.log(
  'Passed: cap-free side walls, compact national/province layouts, map elevations, route matching, combined search, scene navigation and return paths for 18 cities, public templates, Chaoge GLB anchors and offline data.',
)
