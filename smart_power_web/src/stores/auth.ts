/** 认证状态：刷新从当前标签页恢复短期会话，并向后端核验身份；不保存密码或缓存权限。 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as api from '@/services/authService'
import { configureSession, HttpError } from '@/services/http'
import { clearLoginSession, readLoginSession, saveLoginSession } from '@/services/authSession'
import type { AuthUser } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref('')
  const user = ref<AuthUser | null>(null)
  const notice = ref('')
  const source = ref<'mysql'>('mysql')
  let timer: ReturnType<typeof setTimeout> | undefined
  let expiresAt = 0
  let generation = 0
  let initialized = false
  let restoring: Promise<boolean> | undefined
  const authenticated = computed(() => Boolean(token.value && user.value))
  const canRestore = computed(() => Boolean(token.value && !user.value))
  const scopeKey = computed(() => `${user.value?.id ?? ''}:${user.value?.siteIds.join(',') ?? ''}`)
  const can = (permission: string) => user.value?.permissions.includes(permission) ?? false
  /** 注销本标签页：清内存、存储和计时；generation阻止迟到的身份响应恢复旧账号。 */
  function logout(message = '') {
    generation++
    initialized = true
    clearTimeout(timer)
    expiresAt = 0
    token.value = ''
    user.value = null
    notice.value = message
    clearLoginSession()
    configureSession('')
  }
  /** 按绝对期限恢复计时，不把刷新后的剩余期限重新算成完整30分钟。 */
  function armExpiry() {
    clearTimeout(timer)
    const remaining = expiresAt - Date.now()
    if (remaining <= 0) {
      logout('登录已到期，请重新登录')
      return
    }
    timer = setTimeout(() => logout('登录已到期，请重新登录'), remaining)
  }
  /** 参数为表单账号/密码；成功仅存令牌与期限，密码由调用页面立即清空。 */
  async function signIn(username: string, password: string) {
    const current = ++generation
    const result = await api.login(username, password)
    if (current !== generation) return false
    initialized = true
    token.value = result.data.accessToken
    expiresAt = Date.now() + result.data.expiresIn * 1000
    configureSession(token.value, () => logout('登录已失效，请重新登录'))
    user.value = result.data.user
    source.value = result.meta.dataSource
    notice.value = saveLoginSession({ accessToken: token.value, expiresAt })
      ? ''
      : '浏览器禁止保存标签页会话，刷新后可能需要重新登录'
    armExpiry()
    return authenticated.value
  }
  /** 重查状态与权限。401由请求层清会话；临时断网/503不等于账号失效。 */
  async function refreshIdentity() {
    const original = token.value
    const current = generation
    if (!original) return
    if (expiresAt <= Date.now()) {
      logout('登录已到期，请重新登录')
      return
    }
    const result = await api.currentUser()
    if (original === token.value && current === generation) {
      user.value = result.data
      source.value = result.meta.dataSource
      notice.value = ''
    }
  }
  /** 首次路由跳转前恢复会话；retry=true供断网恢复按钮重试，并发调用共用一次/me。
   * 返回true表示本次完成核验，供路由避免重复查询。保存的令牌不代表已获授权。
   */
  function restoreSession(retry = false): Promise<boolean> {
    if (restoring) return restoring
    if (initialized && !retry) return Promise.resolve(false)
    initialized = true
    const saved = readLoginSession()
    if (!saved) return Promise.resolve(false)
    const current = generation
    token.value = saved.accessToken
    expiresAt = saved.expiresAt
    configureSession(token.value, () => logout('登录已失效，请重新登录'))
    armExpiry()
    restoring = (async () => {
      try {
        await refreshIdentity()
        return current === generation && authenticated.value
      } catch (error) {
        if (current === generation && !(error instanceof HttpError && error.status === 401))
          notice.value = '暂时无法核验登录状态，请恢复后端连接后点击“重新验证登录状态”'
        return false
      } finally {
        restoring = undefined
      }
    })()
    return restoring
  }
  return {
    token,
    user,
    notice,
    source,
    authenticated,
    canRestore,
    scopeKey,
    can,
    logout,
    signIn,
    refreshIdentity,
    restoreSession,
  }
})
