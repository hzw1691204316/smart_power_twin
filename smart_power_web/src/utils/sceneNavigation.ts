import type { RouteLocationRaw } from 'vue-router'
import type { PublicFacility } from '@/types/map'

export function siteSceneTarget(siteId: string, cityCode?: number): RouteLocationRaw {
  return {
    name: 'site',
    params: { siteId },
    query: { origin: cityCode ? String(cityCode) : 'henan' },
  }
}

export function facilitySceneTarget(facility: PublicFacility, cityCode?: number): RouteLocationRaw {
  return facility.boundSiteId
    ? siteSceneTarget(facility.boundSiteId, cityCode)
    : {
        name: 'facility',
        params: { facilityId: facility.id },
        query: { origin: cityCode ? String(cityCode) : 'henan' },
      }
}

export function mapReturnPath(
  query: { origin?: unknown; cityCode?: unknown },
  siteCityCode?: number,
): string {
  if (query.origin === 'henan') return '/province/henan'
  // 河南包含410xxx、411xxx及济源419001，不能只按410前缀判断。
  const validCity = (value: unknown): value is string =>
    typeof value === 'string' && /^(?:41(?:0[1-9]|1[0-7])00|419001)$/.test(value)
  const code = validCity(query.origin)
    ? query.origin
    : validCity(query.cityCode)
      ? query.cityCode
      : siteCityCode
        ? String(siteCityCode)
        : ''
  return validCity(code) ? `/province/henan/cities/${code}` : '/province/henan'
}
