import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { provinceBounds } from '../src/utils/provinceCatalog.ts'
const root = new URL('../public/maps/', import.meta.url)
const data = JSON.parse(await readFile(new URL('china-provinces.geojson', root), 'utf8'))
const provinces = []
await mkdir(new URL('provinces/', root), { recursive: true })
for (const feature of data.features) {
  const code = Number(feature.properties.adcode)
  if (!feature.properties.name || !Number.isFinite(code) || code % 10000 !== 0) continue
  const boundaryUrl = `/maps/provinces/${code}.geojson`
  await writeFile(
    new URL(`provinces/${code}.geojson`, root),
    JSON.stringify({ type: 'FeatureCollection', features: [feature] }),
  )
  provinces.push({
    code,
    name: feature.properties.name,
    bounds: provinceBounds(feature),
    boundaryUrl,
  })
}
await writeFile(
  new URL('province-index.json', root),
  JSON.stringify(
    {
      source: '阿里云DataV.GeoAtlas，按现有中国省级边界拆分',
      sourceUrl: 'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json',
      preparedAt: '2026-10-14',
      provinces,
    },
    null,
    2,
  ),
)
console.log(`Prepared ${provinces.length} province outlines from existing local boundaries.`)
