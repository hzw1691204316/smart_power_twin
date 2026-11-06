/** 监测展示业务回归：0/空值/陈旧、质量断点、采样缺口、同时间大序号修订。非视觉验收。 */
import assert from 'node:assert/strict'
import { readingValue, historyPlot } from '../src/utils/monitoringPresentation.ts'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import { createRenderer, h, nextTick, reactive } from 'vue'

const reading = {
  sampledAt: '2026-10-16T00:00:00Z',
  valueType: 'NUMERIC',
  valueNumeric: 0,
  quality: 'GOOD',
  isStale: true,
}
assert.equal(readingValue(reading), '0')
assert.equal(readingValue({ ...reading, valueNumeric: null }), '—')
assert.equal(readingValue({ ...reading, quality: 'BAD' }), '—')
assert.equal(readingValue({ ...reading, valueType: 'BOOLEAN', valueNumeric: 1 }), '在线')
assert.equal(readingValue({ ...reading, valueType: 'TEXT', valueText: '模拟并网' }), '模拟并网')
const row = (minutes, valueNumeric, quality = 'GOOD', sourceSequence = '1') => ({
  sampledAt: new Date(Date.UTC(2026, 9, 16, 0, minutes)).toISOString(),
  valueNumeric,
  quality,
  sourceSequence,
})
const plot = historyPlot(
  [row(0, 0), row(15, null, 'BAD'), row(30, 30), row(45, 40), row(90, 20)],
  900000,
)
assert.equal(plot.count, 4)
assert.equal(plot.paths.length, 3) // BAD断点+超过建议间隔的缺口均不可连线。
assert.equal(plot.min, 0)
assert.equal(plot.max, 40)
const revised = historyPlot(
  [row(0, 10, 'GOOD', '9007199254740992'), row(0, 20, 'GOOD', '9007199254740993')],
  900000,
)
assert.equal(revised.count, 1)
assert.equal(revised.max, 20)
assert.deepEqual(historyPlot([row(0, null, 'BAD')], 900000).paths, [])
console.log(
  'Passed: monitoring zero/null values, typed states, BAD/gap breaks, large source-sequence revisions.',
)

// 执行真实SFC的setup和生命周期，用内存渲染器验收异步状态；不打开浏览器或声称视觉通过。
const source = readFileSync(
  new URL('../src/components/twin/DeviceMonitoring.vue', import.meta.url),
  'utf8',
)
const { descriptor } = parse(source)
const script = compileScript(descriptor, { id: 'monitoring-state-regression' }).content
const auth = reactive({ scopeKey: 'first:1', readable: true, can: () => auth.readable })
const deviceRequests = [],
  historyRequests = []
const deferred = () => {
  let resolve
  const promise = new Promise((r) => {
    resolve = r
  })
  return { promise, resolve }
}
const latest = (id) => ({
  pointId: id,
  sampledAt: '2026-10-16T00:00:00Z',
  quality: 'GOOD',
  valueNumeric: 10,
  unit: 'kW',
  valueType: 'NUMERIC',
})
const mocks = {
  getPoints: (id) => {
    const pending = deferred()
    deviceRequests.push({ id, ...pending })
    return pending.promise
  },
  getLatest: async (id) => ({ data: [latest(id), latest('NOT_BOUND')] }),
  getHistory: (pointId, start, end) => {
    const pending = deferred()
    historyRequests.push({ pointId, start, end, ...pending })
    return pending.promise
  },
}
globalThis.__monitoringRegressionAuth = auth
globalThis.__monitoringRegressionApi = mocks
const moduleUrl = (content) =>
  `data:text/javascript;base64,${Buffer.from(content).toString('base64')}`
const authModule = moduleUrl('export const useAuthStore=()=>globalThis.__monitoringRegressionAuth')
const apiModule = moduleUrl(
  Object.keys(mocks)
    .map(
      (key) =>
        `export const ${key}=(...args)=>globalThis.__monitoringRegressionApi.${key}(...args)`,
    )
    .join('\n'),
)
let compiled = ts.transpileModule(script, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText
compiled = compiled
  .replace(/from (['"])vue\1/g, `from ${JSON.stringify(import.meta.resolve('vue'))}`)
  .replace(/from (['"])@\/stores\/auth\1/g, `from ${JSON.stringify(authModule)}`)
  .replace(/from (['"])@\/services\/monitoringService\1/g, `from ${JSON.stringify(apiModule)}`)
  .replace(
    /from (['"])@\/utils\/monitoringPresentation\1/g,
    `from ${JSON.stringify(new URL('../src/utils/monitoringPresentation.ts', import.meta.url).href)}`,
  )
const Component = (await import(moduleUrl(compiled))).default
Component.render = () => null
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
const props = reactive({ deviceId: 'A', deviceName: '设备A', isDemo: true, pointIds: ['A'] })
const app = renderer.createApp({ render: () => h(Component, props) })
const flush = async () => {
  for (let i = 0; i < 5; i++) {
    await Promise.resolve()
    await nextTick()
  }
}
try {
  app.mount({})
  assert.equal(deviceRequests.length, 1)
  props.deviceId = 'B'
  props.deviceName = '设备B'
  props.pointIds = ['B']
  await flush()
  assert.equal(deviceRequests.length, 2)
  deviceRequests[1].resolve({
    data: [
      { id: 'B', name: 'B', sampleIntervalMs: 900000, valueType: 'NUMERIC' },
      { id: 'NOT_BOUND', name: '不应显示' },
    ],
  })
  await flush()
  const state = app._instance.subTree.component.setupState
  assert.equal(state.device.id, 'B')
  assert.equal(state.readings[0].pointId, 'B')
  assert.equal(state.readings.length, 1)
  assert.equal(state.definitions.length, 1)
  deviceRequests[0].resolve({
    data: [{ id: 'A', name: 'A', sampleIntervalMs: 900000, valueType: 'NUMERIC' }],
  })
  await flush()
  assert.equal(state.device.id, 'B') // 旧站点请求迟到不能覆盖当前站点。
  const oldHistory = historyRequests.at(-1)
  state.hours = 1
  await flush()
  const newHistory = historyRequests.at(-1)
  assert.notEqual(oldHistory, newHistory)
  newHistory.resolve({
    data: { pointId: 'B', items: [{ ...latest('B'), sampledAt: '2026-10-16T00:00:00Z' }] },
  })
  await flush()
  oldHistory.resolve({ data: { pointId: 'OLD_WINDOW', items: [] } })
  await flush()
  assert.equal(state.history.pointId, 'B') // 旧时间范围请求迟到也不能覆盖。
  auth.readable = false
  await flush()
  assert.equal(state.readings.length, 0)
  assert.match(state.error, /没有电力监测权限/)
} finally {
  app.unmount() // 生命周期须关闭自动刷新定时器。
  delete globalThis.__monitoringRegressionAuth
  delete globalThis.__monitoringRegressionApi
}
console.log(
  'Passed: real monitoring component drops stale device/history responses and clears data on revoked permission.',
)
