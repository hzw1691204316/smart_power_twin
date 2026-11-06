/** 台账身份协议：数据库ID使用字符串；资产状态与实时监测状态分开。 */
export interface AssetRoute {
  id: string
  siteId: string
  linkCode: string
  areaId: string | null
  routeId: string
  routeCode: string
  name: string
  isPrimary: boolean
  directionLabel: string | null
  directionCode: 'UP' | 'DOWN' | 'BOTH' | 'UNKNOWN'
  chainageM: number | null
  accessType: 'DIRECT' | 'INTERCHANGE' | 'OTHER'
}
export interface AssetSite {
  id: string
  code: string
  name: string
  siteType: 'SERVICE' | 'TOLL'
  scaleLevel: 'S' | 'M' | 'L'
  provinceCode: string
  cityName: string | null
  longitude: number | null
  latitude: number | null
  coordinateSystem: string
  locationSource: string | null
  complexCode: string | null
  isDemo: boolean
  assetStatus: 'ACTIVE' | 'INACTIVE' | 'RETIRED'
  routes: AssetRoute[]
}
export interface AssetDevice {
  id: string
  siteId: string
  code: string
  name: string
  deviceType: string
  systemType: string
  assetStatus: 'ACTIVE' | 'MAINTENANCE' | 'INACTIVE' | 'RETIRED'
  isDemo: boolean
  areaId: string | null
  parentDeviceId: string | null
  ratedPowerKw: number | null
  ratedEnergyKwh: number | null
  ratedCapacityKva: number | null
  manufacturer: string | null
  modelCode: string | null
}
export interface AssetPage<T> {
  data: T[]
  meta: { total: number; hasNext: boolean }
}
export interface AssetArea {
  id: string
  siteId: string
  parentId: string | null
  code: string
  areaType: string
  name: string
}
export interface HighwayOption {
  id: string
  routeCode: string
  name: string
  status: string
}
export type AssetBody = Record<string, string | boolean | null>
