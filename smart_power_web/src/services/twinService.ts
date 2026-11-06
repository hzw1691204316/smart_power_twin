/** 三维接口集中层。只按授权业务code解析站点ID，不再维护模型键→设备编码的固定表。 */
import { authorizedSites } from './authService'
import { request } from './http'
import type { Envelope } from '../types/auth'
import type {
  BindingInput,
  ObjectInput,
  SceneSummary,
  SceneTemplate,
  TwinSceneData,
} from '../types/twin'

export async function getPublishedScene(siteCode: string): Promise<TwinSceneData> {
  const site = (await authorizedSites()).find((s) => s.code === siteCode)
  if (!site) throw new Error('站点未获授权或台账尚未导入')
  const result = await request<Envelope<TwinSceneData>>(
    `/api/v1/sites/${encodeURIComponent(site.id)}/scene`,
  )
  if (result.data.siteId !== site.id || result.data.status !== 'PUBLISHED')
    throw new Error('返回场景不是本站当前发布版本')
  return result.data
}
export async function getSceneVersions(siteId: string) {
  const rows: SceneSummary[] = []
  for (let page = 1; ; page++) {
    const result = await request<Envelope<SceneSummary[]>>(
      `/api/v1/sites/${encodeURIComponent(siteId)}/scenes?page=${page}&pageSize=100`,
    )
    rows.push(...result.data)
    if (!result.meta.hasNext) return rows
  }
}
export const getScene = (id: string) =>
  request<Envelope<TwinSceneData>>(`/api/v1/scenes/${encodeURIComponent(id)}`)
export const cloneScene = (siteId: string) =>
  request<Envelope<TwinSceneData>>(`/api/v1/sites/${encodeURIComponent(siteId)}/scenes`, {
    method: 'POST',
    body: {},
  })
export const saveBindings = (id: string, bindings: BindingInput[]) =>
  request<Envelope<TwinSceneData>>(`/api/v1/scenes/${encodeURIComponent(id)}/bindings`, {
    method: 'PUT',
    body: { bindings },
  })
export const publishScene = (id: string) =>
  request<Envelope<TwinSceneData>>(`/api/v1/scenes/${encodeURIComponent(id)}/publish`, {
    method: 'POST',
  })

/** 从零创建草稿使用独立接口；旧cloneScene仍只复制当前发布版本。 */
export const getSceneTemplates = () => request<Envelope<SceneTemplate[]>>('/api/v1/scene-templates')
export const getTemplateObjects = (id: string) =>
  request<Envelope<{ templateId: string; objectKeys: string[] }>>(
    `/api/v1/scene-templates/${encodeURIComponent(id)}/objects`,
  )
export const createScene = (siteId: string, templateId: string, objects: ObjectInput[]) =>
  request<Envelope<TwinSceneData>>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/scenes/from-template`,
    {
      method: 'POST',
      body: { templateId, objects },
    },
  )
export const saveObjects = (sceneId: string, objects: ObjectInput[]) =>
  request<Envelope<TwinSceneData>>(`/api/v1/scenes/${encodeURIComponent(sceneId)}/objects`, {
    method: 'PUT',
    body: { objects },
  })
