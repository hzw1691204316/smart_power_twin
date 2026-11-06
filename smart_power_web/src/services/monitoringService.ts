/** 监测请求集中层。只查授权台账，不用前端场景ID猜数据库ID，不缓存跨账号数据。 */
import type { Envelope } from '../types/auth'
import type {
  LatestReading,
  ManagedPoint,
  PointConfigInput,
  PointCreateInput,
  PointHistory,
} from '../types/monitoring'
import { request } from './http'

export const getPoints = (deviceId: string) =>
  request<Envelope<ManagedPoint[]>>(`/api/v1/devices/${encodeURIComponent(deviceId)}/points`)
export const getLatest = (deviceId: string) =>
  request<Envelope<LatestReading[]>>(`/api/v1/devices/${encodeURIComponent(deviceId)}/latest`)

/** 新增定义不生成最新值、历史或模型绑定；冲突由后端按设备内编码唯一性处理。 */
export const createPoint = (deviceId: string, body: PointCreateInput) =>
  request<Envelope<ManagedPoint>>(`/api/v1/devices/${encodeURIComponent(deviceId)}/points`, {
    method: 'POST',
    body,
  })
/** 完整替换允许编辑的配置；不提交只读身份，不在前端直接改MySQL。 */
export const configurePoint = (pointId: string, body: PointConfigInput) =>
  request<Envelope<ManagedPoint>>(`/api/v1/points/${encodeURIComponent(pointId)}/config`, {
    method: 'PUT',
    body,
  })

/** 带时区的[start,end)窗口；最多2000个原始点，hasMore由后端说明截断。 */
export const getHistory = (pointId: string, start: string, end: string) => {
  const query = new URLSearchParams({ startTime: start, endTime: end, grain: 'raw', limit: '2000' })
  return request<Envelope<PointHistory>>(
    `/api/v1/points/${encodeURIComponent(pointId)}/history?${query}`,
  )
}
