/** 大屏交互验收：真实composable的范围/来源/权限竞态，以及真实展示组件的0/null和空态。 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { compileScript, parse } from '@vue/compiler-sfc'
import { createRenderer, createSSRApp, h, nextTick, reactive, ref } from 'vue'
import { renderToString } from '@vue/server-renderer'
const auth = reactive({
  scopeKey: 'A:1',
  permissions: ['dashboard:read'],
  can: (code) => auth.permissions.includes(code),
})
const pending = []
globalThis.__dashboardAuth = auth
globalThis.__dashboardApi = {
  getDashboardSummary: (scope, source) =>
    new Promise((resolve, reject) => pending.push({ scope, source, resolve, reject })),
}
const url = (source) => `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
const authUrl = url('export const useAuthStore=()=>globalThis.__dashboardAuth')
const apiUrl = url(
  'export const getDashboardSummary=(...args)=>globalThis.__dashboardApi.getDashboardSummary(...args)',
)
function compile(source) {
  return ts
    .transpileModule(source, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    })
    .outputText.replace(/from (['"])vue\1/g, `from ${JSON.stringify(import.meta.resolve('vue'))}`)
    .replace(/from (['"])@\/stores\/auth\1/g, `from ${JSON.stringify(authUrl)}`)
    .replace(/from (['"])@\/services\/dashboardService\1/g, `from ${JSON.stringify(apiUrl)}`)
}
const { useDashboardSummary } = await import(
  url(
    compile(
      readFileSync(new URL('../src/composables/useDashboardSummary.ts', import.meta.url), 'utf8'),
    ),
  )
)
const renderer = createRenderer({
  patchProp() {},
  insert() {},
  remove() {},
  createElement: () => ({}),
  createText: () => ({}),
  createComment: () => ({}),
  setText() {},
  setElementText() {},
  parentNode: () => null,
  nextSibling: () => null,
})
const flush = async () => {
  for (let i = 0; i < 6; i++) {
    await Promise.resolve()
    await nextTick()
  }
}
const scope = ref({ provinceCode: '410000' }),
  enabled = ref(true)
let state
const app = renderer.createApp({
  setup() {
    state = useDashboardSummary(scope, enabled)
    return () => h('div')
  },
})
app.mount({})
try {
  assert.equal(pending[0].source, 'FIELD')
  scope.value = { provinceCode: '410000', cityName: '鹤壁市' }
  assert.equal(state.data.value, undefined)
  pending[0].resolve({ siteCount: 999 })
  await flush()
  assert.equal(state.data.value, undefined)
  pending.at(-1).resolve({ siteCount: 2 })
  await flush()
  assert.equal(state.data.value.siteCount, 2)
  state.source.value = 'SIMULATED'
  assert.equal(state.data.value, undefined)
  assert.equal(pending.at(-1).source, 'SIMULATED')
  const previous = pending.at(-1)
  auth.scopeKey = 'B:2'
  previous.resolve({ siteCount: 888 })
  await flush()
  assert.equal(state.data.value, undefined)
  pending.at(-1).resolve({ siteCount: 1 })
  await flush()
  assert.equal(state.data.value.siteCount, 1)
  auth.permissions = []
  assert.equal(state.data.value, undefined)
  assert.match(state.error.value, /权限/)
  const count = pending.length
  await state.reload()
  assert.equal(pending.length, count)
  auth.permissions = ['dashboard:read']
  const waiting = pending.at(-1)
  enabled.value = false
  assert.equal(state.data.value, undefined)
  waiting.resolve({ siteCount: 777 })
  await flush()
  assert.equal(state.data.value, undefined)
  await state.reload()
  assert.equal(pending.at(-1), waiting)
  enabled.value = true
  pending.at(-1).reject(new Error('offline'))
  await flush()
  assert.equal(state.data.value, undefined)
  assert.equal(state.error.value, 'offline')
  {
    const task = state.reload()
    pending.at(-1).resolve({ siteCount: 3 })
    await task
    assert.equal(state.data.value.siteCount, 3)
  }
  const task = state.reload()
  app.unmount()
  pending.at(-1).resolve({ siteCount: 555 })
  await task
  assert.equal(state.data.value, undefined)
} finally {
  app.unmount()
}
const { descriptor } = parse(
  readFileSync(
    new URL('../src/components/dashboard/DashboardSummaryPanel.vue', import.meta.url),
    'utf8',
  ),
)
const compiled = compileScript(descriptor, { id: 'dashboard-summary-test', inlineTemplate: true })
const Panel = (await import(url(compile(compiled.content)))).default
const coverage = {
  valueKw: null,
  contributingSites: 0,
  ambiguousSites: 0,
  missingSites: 2,
  eligibleSites: 2,
  isPartial: true,
  oldestSampledAt: null,
  newestSampledAt: null,
}
const data = {
  asOf: '2026-10-18T08:00:00Z',
  source: 'SIMULATED',
  siteCount: 2,
  demoSiteCount: 2,
  serviceCount: 1,
  tollCount: 1,
  deviceCount: 8,
  deviceStates: { normal: 0, warning: 0, offline: 8, unknown: 0 },
  activeAlarmCount: 0,
  unacknowledgedAlarmCount: 0,
  power: {
    GRID: { ...coverage, valueKw: 0, contributingSites: 1 },
    PV: coverage,
    ESS: { ...coverage, valueKw: -5 },
    CHARGING: coverage,
  },
  note: '模拟测试口径',
}
const html = await renderToString(
  createSSRApp(Panel, { data, loading: false, error: '', source: 'SIMULATED' }),
)
assert.ok(html.includes('0.0') && html.includes('-5.0') && html.includes('—'))
assert.ok(html.includes('覆盖 1 / 2 站') && html.includes('模拟测试口径'))
assert.ok(!html.includes('NaN'))
const failure = await renderToString(
  createSSRApp(Panel, {
    data: undefined,
    loading: false,
    error: 'backend unavailable',
    source: 'FIELD',
  }),
)
assert.ok(failure.includes('backend unavailable') && !failure.includes('0.0'))
console.log(
  'Passed: dashboard scope/source/account isolation, stale responses, revoked permission, disabled public preview, errors/retry/unmount; real SFC zero/null/negative and coverage rendering.',
)
