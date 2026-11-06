/** 台账HTTP集中层：分页读取、白名单表单提交；不创建监测数据或修改三维发布场景。 */
import { request } from './http'
import type { Envelope } from '../types/auth'
import type {
  AssetArea,
  AssetRoute,
  AssetBody,
  AssetDevice,
  AssetPage,
  AssetSite,
  HighwayOption,
} from '../types/assets'
export const listAssetSites = (page = 1, q = '') =>
  request<AssetPage<AssetSite>>(
    `/api/v1/sites?${new URLSearchParams({ page: String(page), pageSize: '20', q })}`,
  )
export const listAssetDevices = (siteId: string, page = 1, q = '') =>
  request<AssetPage<AssetDevice>>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/devices?${new URLSearchParams({ page: String(page), pageSize: '20', q })}`,
  )
export const listAssetAreas = (siteId: string) =>
  request<Envelope<AssetArea[]>>(`/api/v1/sites/${encodeURIComponent(siteId)}/areas`)
/** 本站区域/路线关联写入；id为子记录ID，创建/编辑用不同方法，公共路线字典保持只读。 */
export const saveArea = (siteId: string, id: string | undefined, body: AssetBody) =>
  request<Envelope<AssetArea>>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/areas${id ? '/' + encodeURIComponent(id) : ''}`,
    { method: id ? 'PUT' : 'POST', body },
  )
export const saveRouteLink = (siteId: string, id: string | undefined, body: AssetBody) =>
  request<Envelope<AssetRoute>>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/routes${id ? '/' + encodeURIComponent(id) : ''}`,
    { method: id ? 'PUT' : 'POST', body },
  )
export const getAssetSite = (id: string) =>
  request<Envelope<AssetSite>>(`/api/v1/sites/${encodeURIComponent(id)}`)
export const getAssetDevice = (site: string, id: string) =>
  request<Envelope<AssetDevice>>(
    `/api/v1/sites/${encodeURIComponent(site)}/devices/${encodeURIComponent(id)}`,
  )
export const saveAssetSite = (id: string | undefined, body: AssetBody) =>
  request<Envelope<AssetSite>>(id ? `/api/v1/sites/${encodeURIComponent(id)}` : '/api/v1/sites', {
    method: id ? 'PUT' : 'POST',
    body,
  })
export const saveAssetDevice = (site: string, id: string | undefined, body: AssetBody) =>
  request<Envelope<AssetDevice>>(
    `/api/v1/sites/${encodeURIComponent(site)}/devices${id ? '/' + encodeURIComponent(id) : ''}`,
    { method: id ? 'PUT' : 'POST', body },
  )
/** 取完整授权台账供地图适配，空坐标在适配层明确排除，绝不补造位置。 */
export async function allAssetSites(): Promise<AssetSite[]> {
  const rows: AssetSite[] = []
  for (let page = 1; page <= 10000; page++) {
    const result = await request<AssetPage<AssetSite>>(`/api/v1/sites?page=${page}&pageSize=100`)
    rows.push(...result.data)
    if (!result.meta.hasNext) return rows
  }
  throw new Error('站点目录超过分页上限，请缩小管理范围')
}
export async function assetHighways(): Promise<HighwayOption[]> {
  const rows: HighwayOption[] = []
  for (let page = 1; page <= 10000; page++) {
    const result = await request<AssetPage<HighwayOption>>(
      `/api/v1/highways?page=${page}&pageSize=100`,
    )
    rows.push(...result.data)
    if (!result.meta.hasNext) return rows
  }
  throw new Error('路线目录超过分页上限')
}
