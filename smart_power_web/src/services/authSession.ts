/** 当前标签页的登录会话存储：只保存短期令牌和绝对到期时间，不保存密码、用户详情或权限。 */
export const LOGIN_SESSION_KEY = 'smart-power-twin.login-session.v1'

export interface LoginSession {
  accessToken: string
  expiresAt: number
}

/** 读取同源sessionStorage；无痕限制或存储禁用时返回null，不阻断页面启动。 */
function storage(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

/** 删除本系统会话键，不清空浏览器其他应用的数据；存储不可用时仍可退出内存会话。 */
export function clearLoginSession() {
  try {
    storage()?.removeItem(LOGIN_SESSION_KEY)
  } catch {
    /* 浏览器禁止访问时忽略存储清理异常。 */
  }
}

/** now为当前毫秒时间，便于测试过期边界。损坏/过期数据立即清除，不向后端发送。 */
export function readLoginSession(now = Date.now()): LoginSession | null {
  try {
    const raw = storage()?.getItem(LOGIN_SESSION_KEY)
    if (!raw) return null
    const item = JSON.parse(raw)
    if (
      item?.version !== 1 ||
      typeof item.accessToken !== 'string' ||
      !item.accessToken.trim() ||
      item.accessToken.length > 8192 ||
      !Number.isSafeInteger(item.expiresAt) ||
      item.expiresAt <= now ||
      item.expiresAt > now + 240 * 60 * 1000
    ) {
      clearLoginSession()
      return null
    }
    return { accessToken: item.accessToken, expiresAt: item.expiresAt }
  } catch {
    clearLoginSession()
    return null
  }
}

/** session由登录响应产生；绝对到期时间只写一次，刷新不会延长有效期。返回是否写入成功。 */
export function saveLoginSession(session: LoginSession): boolean {
  try {
    const target = storage()
    if (!target) return false
    target.setItem(LOGIN_SESSION_KEY, JSON.stringify({ version: 1, ...session }))
    return true
  } catch {
    clearLoginSession()
    return false
  }
}
