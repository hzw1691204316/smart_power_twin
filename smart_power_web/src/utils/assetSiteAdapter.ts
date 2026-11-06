/** 数据库台账到地图身份适配：完整WGS84坐标才落点，新增站点不编造功率或设备。 */
import type { AssetSite } from '../types/assets'
import type { Site } from '../types/domain'
export function assetSiteToMap(row: AssetSite, known?: Site): Site | undefined {
  if (
    row.coordinateSystem !== 'WGS84' ||
    row.longitude === null ||
    row.latitude === null ||
    !Number.isFinite(row.longitude) ||
    !Number.isFinite(row.latitude) ||
    Math.abs(row.longitude) > 180 ||
    Math.abs(row.latitude) > 90
  )
    return undefined
  const illustrative = !!known && row.isDemo && row.assetStatus === 'ACTIVE'
  const primary = row.routes.find((route) => route.isPrimary) ?? row.routes[0]
  return {
    ...known,
    id: known?.id ?? `db-site-${row.id}`,
    code: row.code,
    name: row.name,
    city: row.cityName?.replace(/市$/, '') ?? '城市未填',
    provinceCode: row.provinceCode,
    cityCode: known?.cityCode,
    complexCode: row.complexCode ?? undefined,
    type: row.siteType,
    scale: row.scaleLevel,
    longitude: row.longitude,
    latitude: row.latitude,
    highway: primary?.routeCode ?? '路线待核验',
    direction: primary?.directionLabel ?? '方向待核验',
    locationSource: row.locationSource ?? '业务台账坐标（待核验）',
    locationNote: row.locationSource ?? '业务台账，无发布场景时不自动使用通用模型。',
    status: illustrative ? known!.status : 'normal',
    dataPending: !illustrative,
    assetStatus: row.assetStatus,
    powerKw: illustrative ? known!.powerKw : 0,
    pvKw: illustrative ? known!.pvKw : 0,
    dailyEnergyKwh: illustrative ? known!.dailyEnergyKwh : 0,
    devices: illustrative ? known!.devices : [],
    modelUrl: known?.modelUrl ?? '',
  }
}
