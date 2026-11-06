/** 账号接口协议。主键始终为字符串；权限和站点范围由后端实时校验。 */
export interface AuthUser {
  id: string
  username: string
  displayName: string
  status: 'ACTIVE' | 'LOCKED' | 'INACTIVE'
  roleId: string
  roleCode: string
  permissions: string[]
  siteIds: string[]
}
export interface Role {
  id: string
  code: string
  name: string
  permissions: string[]
}
export interface AccountInput {
  username: string
  displayName: string
  password: string
  roleId: string
  siteIds: string[]
}
export interface AssetOption {
  id: string
  code: string
  name: string
}
export interface Envelope<T> {
  data: T
  meta: { dataSource: 'mysql'; notice: string; hasNext?: boolean }
}
