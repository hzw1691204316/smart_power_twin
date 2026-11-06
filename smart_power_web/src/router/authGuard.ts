/** 路由认证边界：恢复会话后再决定去向；动作权限仍由后端强制校验。 */
import type { Router } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { safeRedirect } from '@/utils/authRedirect'

/** router为实际或测试用路由器；注册一次异步守卫，确保刷新后的首次导航等待身份核验。 */
export function registerAuthGuard(router: Router) {
  router.beforeEach(async (to) => {
    const auth = useAuthStore()
    const restored = await auth.restoreSession()
    if (to.meta.public) return auth.authenticated ? safeRedirect(to.query.redirect) : true
    if (!auth.authenticated) return { name: 'login', query: { redirect: to.fullPath } }
    try {
      if (!restored) await auth.refreshIdentity()
    } catch {
      // 401已由请求层注销；临时断网不能直接删除仍有效的登录会话。
      auth.notice = '身份服务暂时不可用，请检查后端连接'
    }
    if (!auth.authenticated) return { name: 'login', query: { redirect: to.fullPath } }
    const permissions = (to.meta.permissions ?? []) as string[]
    if (!permissions.every(auth.can)) return { name: 'forbidden' }
  })
}
