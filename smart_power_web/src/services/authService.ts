/** 账号接口集中层：组件不直接拼接鉴权头，也不在页面内保存密码。 */
import { request } from './http'
import type { AccountInput, AssetOption, AuthUser, Envelope, Role } from '@/types/auth'

export const login = (username: string, password: string) =>
  request<Envelope<{ accessToken: string; expiresIn: number; user: AuthUser }>>(
    '/api/v1/auth/login',
    {
      method: 'POST',
      body: { username, password },
      public: true,
    },
  )
export const currentUser = () => request<Envelope<AuthUser>>('/api/v1/auth/me')
export const health = () => request<{ dataSource: 'mysql' }>('/api/v1/health', { public: true })
export const roles = () => request<Envelope<Role[]>>('/api/v1/roles')
export const users = (page = 1) =>
  request<Envelope<{ items: AuthUser[]; total: number; page: number; pageSize: number }>>(
    `/api/v1/users?page=${page}&pageSize=20`,
  )
export const createUser = (body: AccountInput) =>
  request<Envelope<AuthUser>>('/api/v1/users', { method: 'POST', body })
export const setSites = (id: string, siteIds: string[]) =>
  request<Envelope<AuthUser>>(`/api/v1/users/${encodeURIComponent(id)}/sites`, {
    method: 'PUT',
    body: { siteIds },
  })
export const setStatus = (id: string, status: AuthUser['status']) =>
  request<Envelope<AuthUser>>(`/api/v1/users/${encodeURIComponent(id)}/status`, {
    method: 'PUT',
    body: { status },
  })

/** 拉取当前用户授权站点全集，供账号授权及演示场景过滤；不绕过后端范围。 */
export async function authorizedSites(): Promise<AssetOption[]> {
  const items: AssetOption[] = []
  for (let page = 1; ; page++) {
    const result = await request<Envelope<AssetOption[]>>(`/api/v1/sites?page=${page}&pageSize=100`)
    items.push(...result.data)
    if (!result.meta.hasNext) return items
  }
}
