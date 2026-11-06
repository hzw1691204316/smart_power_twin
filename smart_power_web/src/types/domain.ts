export type SiteType = 'TOLL' | 'SERVICE'
export type ScaleLevel = 'S' | 'M' | 'L'
export type DeviceStatus = 'normal' | 'warning' | 'offline'
export interface Device {
  id: string
  objectKey: string
  name: string
  category: string
  status: DeviceStatus
  powerKw: number
  description: string
  metrics: { label: string; value: string; unit: string }[]
}
/** 场景交互目录仅含对象身份；unknown不冒充监测已在线，也不编造功率0。 */
export type SceneDevice = Pick<Device, 'id' | 'objectKey' | 'name' | 'category'> & {
  status: DeviceStatus | 'unknown'
}
export interface Site {
  id: string
  code: string
  name: string
  city: string
  /** 新台账尚未接入运行数据，页面不得显示占位功率0或正常在线。 */
  dataPending?: boolean
  assetStatus?: string
  provinceCode?: string
  cityCode?: number
  complexCode?: string
  publicFacilityId?: string
  locationSource?: string
  locationNote?: string
  type: SiteType
  scale: ScaleLevel
  highway: string
  direction: string
  longitude: number
  latitude: number
  status: DeviceStatus
  powerKw: number
  pvKw: number
  dailyEnergyKwh: number
  modelUrl: string
  devices: Device[]
  /** 独立公开方案仅提供模型对象，不继承通用模板的模拟电力读数或设备状态。 */
  publicModel?: {
    devices: SceneDevice[]
    pvPanelCount: number
    description: string
  }
}
export interface Highway {
  code: string
  name: string
  color: string
  coordinates: number[]
}
