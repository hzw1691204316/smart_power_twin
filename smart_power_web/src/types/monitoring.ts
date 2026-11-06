/** 电力监测协议：数据库ID/源序号用字符串，缺测用null，质量与陈旧状态分开。 */
export interface BackendDevice {
  id: string
  code: string
  name: string
  isDemo: boolean
}
export interface PointDefinition {
  id: string
  code: string
  name: string
  unit: string
  valueType: 'NUMERIC' | 'BOOLEAN' | 'TEXT'
  aggregationType: 'INSTANT' | 'COUNTER' | 'STATE'
  sampleIntervalMs: number
  staleAfterMs: number
  enabled: boolean
}
/** 管理页完整定义；周期与阈值是配置，不能当作设备采样读数。 */
export interface ManagedPoint extends PointDefinition {
  siteId: string
  deviceId: string
  alarmLow: number | null
  alarmHigh: number | null
  directionConvention: string | null
}
/** 编辑接口仅允许这些字段；单位/编码/类型创建后固定。周期单位始终为毫秒。 */
export interface PointConfigInput {
  sampleIntervalMs: number
  staleAfterMs: number
  enabled: boolean
  alarmLow: number | null
  alarmHigh: number | null
}
export interface PointCreateInput extends PointConfigInput {
  code: string
  name: string
  unit: string
  valueType: PointDefinition['valueType']
  aggregationType: PointDefinition['aggregationType']
  directionConvention: string | null
}
export interface LatestReading {
  pointId: string
  code: string
  name: string
  unit: string
  valueType: PointDefinition['valueType']
  valueNumeric: number | null
  valueText: string | null
  sampledAt: string | null
  quality: string | null
  isStale: boolean
  enabled: boolean
  source: 'SIMULATED' | 'FIELD'
}
export interface HistoryItem {
  sampledAt: string
  valueNumeric: number | null
  valueText: string | null
  quality: string
  sourceSequence?: string | null
}
export interface PointHistory {
  pointId: string
  unit: string
  grain: string
  aggregation: string
  items: HistoryItem[]
  hasMore: boolean
  note: string
}
