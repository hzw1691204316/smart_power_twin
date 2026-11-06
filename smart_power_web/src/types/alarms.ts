/** 告警事件协议：生命周期独立于确认；关联ID为数据库字符串，不能当作GLB对象ID。 */
export type AlarmStatus = 'ACTIVE' | 'RECOVERED' | 'CLOSED'
export type AlarmSeverity = 'INFO' | 'MINOR' | 'MAJOR' | 'CRITICAL'
export interface AlarmEvent {
  id: string
  siteId: string
  siteName: string
  deviceId: string | null
  deviceName: string | null
  pointId: string | null
  pointName: string | null
  unit: string | null
  status: AlarmStatus
  severity: AlarmSeverity
  message: string
  raisedAt: string
  recoveredAt: string | null
  acknowledgedAt: string | null
  acknowledgedBy: string | null
  acknowledgedByName: string | null
  handlingNote: string | null
  triggerSnapshot: Record<string, unknown> | unknown[] | null
  isDemo: boolean
  source: 'SIMULATED' | 'FIELD' | 'UNKNOWN'
}
export interface AlarmPage {
  data: AlarmEvent[]
  meta: { total: number; page: number; pageSize: number; hasNext: boolean }
}
export interface AlarmFilters {
  page: number
  status: AlarmStatus | ''
  severity: AlarmSeverity | ''
  acknowledged: '' | 'true' | 'false'
}
