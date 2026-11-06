/** 请求层回归：真实Response解析、认证头、401/403语义、跨会话迟到响应；不冒充浏览器视觉验收。 */
import assert from 'node:assert/strict'
import { configureSession, HttpError, request } from '../src/services/http.ts'
import { safeRedirect } from '../src/utils/authRedirect.ts'

for (const bad of [
  undefined,
  ['//evil.test'],
  '//evil.test',
  'https://evil.test',
  '/\\evil.test',
  '/login',
  '/LOGIN?redirect=/login',
  '/a\nfoo',
])
  assert.equal(safeRedirect(bad), '/overview')
assert.equal(safeRedirect('/province/henan?city=410600'), '/province/henan?city=410600')

const originalFetch = globalThis.fetch
let expired = 0
const response = (status, data) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
try {
  configureSession('first', () => expired++)
  globalThis.fetch = async (_path, options) => {
    assert.equal(options.headers.Authorization, 'Bearer first')
    return response(200, { data: { id: '18446744073709551615' } })
  }
  assert.equal((await request('/api/v1/auth/me')).data.id, '18446744073709551615')
  globalThis.fetch = async (_path, options) => {
    assert.equal(options.headers.Authorization, undefined)
    assert.equal(JSON.parse(options.body).username, 'demo')
    return response(401, { error: { code: 'UNAUTHENTICATED', message: '登录失败' } })
  }
  await assert.rejects(
    request('/api/v1/auth/login', { public: true, method: 'POST', body: { username: 'demo' } }),
    (error) => error instanceof HttpError && error.status === 401,
  )
  assert.equal(expired, 0, 'login errors must not clear another session')
  globalThis.fetch = async () => response(403, { error: { code: 'FORBIDDEN', message: '无权限' } })
  await assert.rejects(request('/api/v1/users'), (error) => error.status === 403)
  assert.equal(expired, 0, 'forbidden actions must not trigger a login loop')

  let completeOld
  globalThis.fetch = () =>
    new Promise((resolve) => {
      completeOld = resolve
    })
  const stale = request('/api/v1/sites')
  configureSession('second')
  completeOld(response(401, { error: { message: '旧令牌过期' } }))
  await assert.rejects(stale)
  assert.equal(expired, 0, 'a late old 401 must not log out the new user')
  globalThis.fetch = async () => response(401, { error: { message: '当前令牌过期' } })
  await assert.rejects(request('/api/v1/auth/me'))
  assert.equal(expired, 1)
  configureSession('')
  globalThis.fetch = async () => {
    throw new TypeError('Failed to fetch')
  }
  await assert.rejects(request('/api/v1/health', { public: true }), /后端连接失败/)
} finally {
  globalThis.fetch = originalFetch
  configureSession('')
}
console.log(
  'Passed: safe login redirects, Bearer headers, login failures, forbidden actions, stale 401 isolation and network errors.',
)
