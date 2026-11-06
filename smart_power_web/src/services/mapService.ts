import type { PublicFacility, CityRegion, RoadCollection, ProvinceRegion } from '@/types/map'
import { routeCodes } from '@/utils/directory'
import { demoSites } from '@/data/demo'

export async function getProvinceRegions(): Promise<ProvinceRegion[]> {
  const response = await fetch('/maps/province-index.json')
  if (!response.ok) throw new Error('省域目录加载失败')
  const data: { provinces: ProvinceRegion[] } = await response.json()
  if (!Array.isArray(data.provinces)) throw new Error('省域目录格式不正确')
  return data.provinces
}

export async function getHighwayOptions(cityCode?: number): Promise<string[]> {
  const response = await fetch(
    cityCode ? `/maps/cities/${cityCode}-expressways.geojson` : '/maps/henan-expressways.geojson',
  )
  if (!response.ok) throw new Error('路线目录加载失败')
  const data: RoadCollection = await response.json()
  return [...new Set(data.features.flatMap((feature) => routeCodes(feature.properties.ref)))].sort(
    (a, b) => a.localeCompare(b, 'en', { numeric: true }),
  )
}

export async function getCityRegions(): Promise<CityRegion[]> {
  const response = await fetch('/maps/henan-city-index.json')
  if (!response.ok) throw new Error('地市目录加载失败')
  const data: { cities: CityRegion[] } = await response.json()
  return data.cities
}

export async function getPublicFacilities(): Promise<PublicFacility[]> {
  const response = await fetch('/maps/henan-facilities.json')
  if (!response.ok) throw new Error('设施位置数据暂时不可用')
  const data: { facilities: PublicFacility[] } = await response.json()
  if (!Array.isArray(data.facilities)) throw new Error('设施数据格式错误')
  return data.facilities.map((facility) => {
    const bound = demoSites.find((site) => site.publicFacilityId === facility.id)
    return bound
      ? { ...facility, name: bound.name, ref: bound.highway, boundSiteId: bound.id }
      : facility
  })
}
