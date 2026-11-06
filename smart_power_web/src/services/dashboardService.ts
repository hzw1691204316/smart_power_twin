/** 大屏HTTP：只查询汇总接口；本站按授权code解析数据库ID，不缓存跨账号ID。 */
import { authorizedSites } from './authService'
import { request } from './http'
import type { Envelope } from '../types/auth'
import type { DashboardScope, DashboardSource, DashboardSummary } from '../types/dashboard'
export async function getDashboardSummary(
  scope: DashboardScope,
  source: DashboardSource,
): Promise<DashboardSummary> {
  const params = new URLSearchParams({ source })
  if (scope.provinceCode) params.set('provinceCode', scope.provinceCode)
  if (scope.cityName) params.set('cityName', scope.cityName)
  if (scope.siteCode !== undefined) {
    const site = (await authorizedSites()).find((s) => s.code === scope.siteCode)
    if (!site) throw new Error('本站未获授权或尚未录入业务台账')
    params.set('siteId', site.id)
  }
  return (await request<Envelope<DashboardSummary>>(`/api/v1/dashboard/summary?${params}`)).data
}
