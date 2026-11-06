/** 告警HTTP集中层：按授权站点code解析真实ID；不缓存跨账号数据，不退回静态演示事件。 */
import { authorizedSites } from './authService'
import { request } from './http'
import type { Envelope } from '../types/auth'
import type { AlarmEvent, AlarmFilters, AlarmPage } from '../types/alarms'

export async function getAlarms(siteCode: string, filters: AlarmFilters): Promise<AlarmPage> {
  const site = (await authorizedSites()).find((s) => s.code === siteCode)
  if (!site) throw new Error('站点未获授权或台账尚未导入')
  const params = new URLSearchParams({
    siteId: site.id,
    page: String(filters.page),
    pageSize: '10',
  })
  for (const key of ['status', 'severity', 'acknowledged'] as const)
    if (filters[key]) params.set(key, filters[key])
  return request<AlarmPage>(`/api/v1/alarms?${params}`)
}
export const getAlarm = (id: string) =>
  request<Envelope<AlarmEvent>>(`/api/v1/alarms/${encodeURIComponent(id)}`)
export const actOnAlarm = (id: string, action: 'acknowledge' | 'close', handlingNote: string) =>
  request<Envelope<AlarmEvent>>(`/api/v1/alarms/${encodeURIComponent(id)}/${action}`, {
    method: 'POST',
    body: { handlingNote },
  })
