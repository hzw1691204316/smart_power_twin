/** 同源 /api 请求适配。认证store负责标签页会话恢复，本模块只持有当前内存令牌。 */
let accessToken = ''
let expiredHandler: (() => void) | undefined

export class HttpError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}
/** 登录/退出时更新内存凭据；handler由认证store注册，避免http反向依赖store。 */
export function configureSession(token: string, handler?: () => void) {
  accessToken = token
  if (handler) expiredHandler = handler
}
/** path为/api开头的固定业务路径；body为JSON；public请求不携带Bearer令牌。 */
export async function request<T>(
  path: string,
  options: {
    method?: 'GET' | 'POST' | 'PUT'
    body?: unknown
    public?: boolean
  } = {},
): Promise<T> {
  const token = options.public ? '' : accessToken
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 10000)
  try {
    const response = await fetch(path, {
      method: options.method ?? 'GET',
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      // 旧请求迟到的401不能清除用户随后登录的新会话。
      if (response.status === 401 && token && token === accessToken) expiredHandler?.()
      throw new HttpError(
        response.status,
        payload?.error?.code ?? 'HTTP_ERROR',
        payload?.error?.message ?? `接口请求失败（${response.status}），请检查后端是否启动`,
      )
    }
    if (payload === null) throw new Error('后端没有返回JSON，请检查 /api 代理配置')
    return payload as T
  } catch (error) {
    if (error instanceof HttpError) throw error
    if (
      error instanceof TypeError ||
      (error instanceof DOMException && error.name === 'AbortError')
    )
      throw new Error('后端连接失败或超时，请先启动本机8000端口的后端')
    throw error
  } finally {
    clearTimeout(timeout)
  }
}
