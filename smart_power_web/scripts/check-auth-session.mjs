/** 用真实Pinia、路由守卫和HTTP适配模拟刷新；只使用虚拟令牌，不访问用户库或凭据。 */
import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

const sourceRoot = new URL('../src/', import.meta.url)
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith('@/'))
      return nextResolve(new URL(`${specifier.slice(2)}.ts`, sourceRoot).href, context)
    if (
      specifier.startsWith('.') &&
      context.parentURL?.startsWith(sourceRoot.href) &&
      !/\.[a-z]+$/i.test(specifier)
    )
      return nextResolve(`${specifier}.ts`, context)
    return nextResolve(specifier, context)
  },
})
const original = {
  fetch: globalThis.fetch,
  window: globalThis.window,
  now: Date.now,
  setTimeout: globalThis.setTimeout,
  clearTimeout: globalThis.clearTimeout,
}
const values = new Map()
const timers = new Map()
let sequence = 0
let now = Date.now()
globalThis.window = {
  sessionStorage: {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  },
}
Date.now = () => now
globalThis.setTimeout = (fn, delay) => {
  timers.set(++sequence, { fn, delay })
  return sequence
}
globalThis.clearTimeout = (id) => timers.delete(id)
const response = (status, data) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
const user = {
  id: '17',
  username: 'fixture',
  displayName: '测试账号',
  status: 'ACTIVE',
  roleId: '2',
  roleCode: 'VIEWER',
  permissions: ['site:read'],
  siteIds: ['101'],
}
const envelope = (data) => ({ data, meta: { dataSource: 'mysql', notice: '' } })
try {
  const { useAuthStore } = await import('../src/stores/auth.ts')
  const { configureSession } = await import('../src/services/http.ts')
  const { LOGIN_SESSION_KEY, readLoginSession } = await import('../src/services/authSession.ts')
  const { registerAuthGuard } = await import('../src/router/authGuard.ts')
  const { safeRedirect } = await import('../src/utils/authRedirect.ts')
  const reload = () => {
    timers.clear() // 模拟刷新时销毁旧JS上下文，sessionStorage保留。
    configureSession('')
    setActivePinia(createPinia())
    return useAuthStore()
  }
  const makeRouter = () => {
    const component = { render: () => null }
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/login', name: 'login', component, meta: { public: true } },
        { path: '/overview', name: 'overview', component },
        { path: '/province/henan', name: 'henan', component },
        { path: '/sites/:siteId', name: 'site', component },
        {
          path: '/admin/users',
          name: 'accounts',
          component,
          meta: { permissions: ['user:manage'] },
        },
        { path: '/forbidden', name: 'forbidden', component },
      ],
    })
    registerAuthGuard(router)
    return router
  }
  const loginResponse = () =>
    response(200, envelope({ accessToken: 'fixture-token', expiresIn: 1800, user }))
  // 与登录页相同的signIn + router.replace流程：回到原目标，默认才是全国概览。
  // 这里只验证实际store/守卫/路由，不声称模拟了浏览器新标签页行为。
  for (const [entry, target] of [
    ['/province/henan', '/province/henan'],
    ['/sites/henan-service-01', '/sites/henan-service-01'],
    ['/login', '/overview'],
  ]) {
    values.delete(LOGIN_SESSION_KEY)
    const loginAuth = reload()
    const loginRouter = makeRouter()
    await loginRouter.push(entry)
    assert.equal(loginRouter.currentRoute.value.name, 'login')
    const destination = safeRedirect(loginRouter.currentRoute.value.query.redirect)
    globalThis.fetch = async (url) =>
      url === '/api/v1/auth/login' ? loginResponse() : response(200, envelope(user))
    assert.equal(await loginAuth.signIn('fixture', 'fixture-password'), true)
    await loginRouter.replace(destination)
    assert.equal(loginRouter.currentRoute.value.fullPath, target)
    // 登录后再次进入登录路由时，由守卫在当前路由器重定向到指定站内页面。
    await loginRouter.push({ name: 'login', query: { redirect: target } })
    assert.equal(loginRouter.currentRoute.value.fullPath, target)
    loginAuth.logout()
  }
  let auth = reload()
  globalThis.fetch = async () => loginResponse()
  assert.equal(await auth.signIn('fixture', 'fixture-password'), true)
  const saved = JSON.parse(values.get(LOGIN_SESSION_KEY))
  assert.deepEqual(Object.keys(saved).sort(), ['accessToken', 'expiresAt', 'version'])
  assert.ok(!values.get(LOGIN_SESSION_KEY).includes('fixture-password'))
  assert.equal(saved.expiresAt, now + 1800000)
  values.set('unrelated-app', 'keep')

  // 真实路由首次进入省域/站点页：只发/me，核验成功保持原路径，不跳登录页。
  for (const path of ['/province/henan?city=410600', '/sites/henan-service-01']) {
    now += 1000
    auth = reload()
    let calls = 0
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/api/v1/auth/me')
      assert.equal(options.headers.Authorization, 'Bearer fixture-token')
      calls++
      return response(200, envelope(user))
    }
    const router = makeRouter()
    await router.push(path)
    assert.equal(router.currentRoute.value.fullPath, path)
    assert.equal(auth.authenticated, true)
    assert.equal(calls, 1)
    assert.equal(JSON.parse(values.get(LOGIN_SESSION_KEY)).expiresAt, saved.expiresAt)
    assert.ok([...timers.values()].some((timer) => timer.delay === saved.expiresAt - now))
  }
  // 权限由新/me响应决定，不能靠旧页面权限重新进入管理员页。
  auth = reload()
  globalThis.fetch = async () => response(200, envelope(user))
  const adminRouter = makeRouter()
  await adminRouter.push('/admin/users')
  assert.equal(adminRouter.currentRoute.value.name, 'forbidden')
  assert.equal(auth.can('user:manage'), false)

  // 短暂断网不清会话；恢复后可不用账号密码重试。
  auth = reload()
  globalThis.fetch = async () => {
    throw new TypeError('offline')
  }
  const offlineRouter = makeRouter()
  await offlineRouter.push('/province/henan')
  assert.equal(offlineRouter.currentRoute.value.name, 'login')
  assert.equal(offlineRouter.currentRoute.value.query.redirect, '/province/henan')
  assert.equal(auth.canRestore, true)
  assert.ok(values.has(LOGIN_SESSION_KEY))
  globalThis.fetch = async () => response(503, { error: { message: '数据库暂时不可用' } })
  assert.equal(await auth.restoreSession(true), false)
  assert.ok(values.has(LOGIN_SESSION_KEY))
  globalThis.fetch = async () => response(200, envelope({ ...user, siteIds: ['102'] }))
  assert.equal(await auth.restoreSession(true), true)
  assert.deepEqual(auth.user.siteIds, ['102'])

  // 并发恢复只请求一次；退出后的迟到响应不能恢复账号。
  auth = reload()
  let finish
  let calls = 0
  globalThis.fetch = () => {
    calls++
    return new Promise((resolve) => {
      finish = resolve
    })
  }
  const first = auth.restoreSession()
  const second = auth.restoreSession()
  assert.equal(calls, 1)
  auth.logout()
  finish(response(200, envelope(user)))
  assert.deepEqual(await Promise.all([first, second]), [false, false])
  assert.equal(auth.authenticated, false)
  assert.equal(values.has(LOGIN_SESSION_KEY), false)
  assert.equal(values.get('unrelated-app'), 'keep')

  // 无效/被锁定账号返回401，清除标签页令牌，而不是循环重试。
  values.set(LOGIN_SESSION_KEY, JSON.stringify(saved))
  auth = reload()
  globalThis.fetch = async () =>
    response(401, { error: { code: 'UNAUTHENTICATED', message: '账号已锁定' } })
  assert.equal(await auth.restoreSession(), false)
  assert.equal(auth.canRestore, false)
  assert.equal(values.has(LOGIN_SESSION_KEY), false)

  // 过期或损坏记录本地拒绝；登录定时器到期同样清存储。
  for (const raw of [
    '{broken',
    JSON.stringify({ ...saved, expiresAt: now }),
    JSON.stringify({ ...saved, expiresAt: now + 999999999 }),
  ]) {
    values.set(LOGIN_SESSION_KEY, raw)
    assert.equal(readLoginSession(), null)
    assert.equal(values.has(LOGIN_SESSION_KEY), false)
  }
  auth = reload()
  globalThis.fetch = async () => loginResponse()
  await auth.signIn('fixture', 'fixture-password')
  const expire = [...timers.values()].find((timer) => timer.delay === 1800000)
  assert.ok(expire)
  now += 1800000
  expire.fn()
  assert.equal(auth.authenticated, false)
  assert.equal(values.has(LOGIN_SESSION_KEY), false)

  // 存储被浏览器禁用时，普通登录仍可用，不让SecurityError令页面崩溃。
  globalThis.window = {
    get sessionStorage() {
      throw new Error('Storage unavailable')
    },
  }
  auth = reload()
  globalThis.fetch = async () => loginResponse()
  assert.equal(await auth.signIn('fixture', 'fixture-password'), true)
  assert.match(auth.notice, /浏览器禁止/)
  auth.logout()
  console.log(
    'Passed: login return paths/default landing, real store/router reload recovery, unchanged expiry, live permissions, logout, 401, offline retry, concurrent restore and disabled storage.',
  )
} finally {
  hook.deregister()
  globalThis.fetch = original.fetch
  if (original.window === undefined) delete globalThis.window
  else globalThis.window = original.window
  Date.now = original.now
  globalThis.setTimeout = original.setTimeout
  globalThis.clearTimeout = original.clearTimeout
}
