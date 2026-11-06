/** 大屏查询协议：站点数是授权台账；设备/事件/功率只含选定来源；null不等于0。 */
export type DashboardSource = 'FIELD' | 'SIMULATED'
export interface DashboardScope {
  provinceCode?: string
  cityName?: string
  siteCode?: string
}
export interface PowerCoverage {
  valueKw: number | null
  contributingSites: number
  ambiguousSites: number
  missingSites: number
  eligibleSites: number
  isPartial: boolean
  oldestSampledAt: string | null
  newestSampledAt: string | null
}
export interface DashboardSummary {
  asOf: string
  source: DashboardSource
  siteCount: number
  demoSiteCount: number
  activeSiteCount: number
  serviceCount: number
  tollCount: number
  deviceCount: number
  deviceStates: { normal: number; warning: number; offline: number; unknown: number }
  activeAlarmCount: number
  unacknowledgedAlarmCount: number
  power: Record<'GRID' | 'PV' | 'ESS' | 'CHARGING', PowerCoverage>
  dailyEnergyKwh: number | null
  note: string
}
