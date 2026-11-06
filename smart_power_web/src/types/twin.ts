/** 场景数据库协议。站点、场景版本、对象、设备、测点ID全部独立且为字符串。 */
import type { BackendDevice } from './monitoring'
export interface TwinDevice extends BackendDevice {
  systemType: string
  assetStatus: string
}
export interface TwinObject {
  id: string
  parentId: string | null
  objectKey: string
  name: string
  deviceId: string | null
  device: TwinDevice | null
  areaId: string | null
  isDemo: boolean
  transform: unknown
}
export interface TwinBinding {
  id: string
  objectId: string
  deviceId: string
  pointId: string
  propertyCode: string
  pointCode: string
  pointName: string
  unit: string
  enabled: boolean
  mappingConfig: Record<string, unknown> | null
}
export interface BindingInput {
  objectId: string
  pointId: string
  propertyCode: string
  mappingConfig: Record<string, unknown> | null
}
export interface SceneSummary {
  id: string
  siteId: string
  templateId: string
  version: number
  status: 'DRAFT' | 'PUBLISHED' | 'ARCHIVED'
  isDemo: boolean
  publishedAt: string | null
  modelUrl: string | null
}
export interface TwinSceneData extends SceneSummary {
  objects: TwinObject[]
  bindings: TwinBinding[]
}

/** 模板版本与对象编辑白名单；设备ID由本站台账选择，不从GLB命名推测。 */
export interface SceneTemplate {
  id: string
  code: string
  siteType: string
  scaleLevel: string
  version: number
  status: string
  modelUrl: string | null
}
export interface ObjectInput {
  objectKey: string
  name: string
  deviceId: string | null
}
