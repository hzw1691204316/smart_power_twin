/** 告警交互回归：真实composable与SFC的身份切换、迟到响应、筛选分页和只读处置；非视觉验收。 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { compileScript, parse } from '@vue/compiler-sfc'
import { createRenderer, h, nextTick, reactive, ref } from 'vue'

const auth = reactive({
  scopeKey: 'first:1',
  permissions: ['alarm:read'],
  can: (code) => auth.permissions.includes(code),
})
const lists = [],
  details = [],
  actions = []
const deferred = () => {
  let resolve, reject
  const promise = new Promise((ok, fail) => {
    resolve = ok
    reject = fail
  })
  return { promise, resolve, reject }
}
const mocks = {
  getAlarms: (site, filters) => {
    const pending = deferred()
    lists.push({ site, filters, ...pending })
    return pending.promise
  },
  getAlarm: (id) => {
    const pending = deferred()
    details.push({ id, ...pending })
    return pending.promise
  },
  actOnAlarm: (id, action, note) => {
    const pending = deferred()
    actions.push({ id, action, note, ...pending })
    return pending.promise
  },
}
globalThis.__alarmAuth = auth
globalThis.__alarmApi = mocks
const url = (source) => `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
const authUrl = url('export const useAuthStore=()=>globalThis.__alarmAuth')
const apiUrl = url(
  Object.keys(mocks)
    .map((k) => `export const ${k}=(...args)=>globalThis.__alarmApi.${k}(...args)`)
    .join('\n'),
)
function compile(source) {
  return ts
    .transpileModule(source, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    })
    .outputText.replace(/from (['"])vue\1/g, `from ${JSON.stringify(import.meta.resolve('vue'))}`)
    .replace(/from (['"])@\/stores\/auth\1/g, `from ${JSON.stringify(authUrl)}`)
    .replace(/from (['"])@\/services\/alarmService\1/g, `from ${JSON.stringify(apiUrl)}`)
}
const composableUrl = url(
  compile(readFileSync(new URL('../src/composables/useAlarmEvents.ts', import.meta.url), 'utf8')),
)
const { useAlarmEvents } = await import(composableUrl)
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
const event = (id, extra = {}) => ({
  id,
  siteId: '2',
  status: 'ACTIVE',
  acknowledgedAt: null,
  ...extra,
})
const page = (items, total = items.length) => ({
  data: items,
  meta: { total, page: 1, pageSize: 10, hasNext: total > 10 },
})
const code = ref('A')
let state
const app = renderer.createApp({
  setup() {
    state = useAlarmEvents(code)
    return () => h('div')
  },
})
try {
  app.mount({})
  assert.equal(lists.length, 1)
  code.value = 'B'
  assert.equal(lists.length, 2)
  lists[1].resolve(page([event('B')], 11))
  await flush()
  lists[0].resolve(page([event('OLD')]))
  await flush()
  assert.equal(state.rows.value[0].id, 'B')
  assert.equal(state.total.value, 11)
  state.page.value = 2
  await flush()
  assert.equal(lists.at(-1).filters.page, 2)
  const oldPage = lists.at(-1)
  state.status.value = 'RECOVERED'
  await flush()
  assert.equal(state.page.value, 1)
  assert.equal(lists.at(-1).filters.status, 'RECOVERED')
  lists.at(-1).resolve(page([event('filtered')]))
  oldPage.resolve(page([event('old-page')]))
  await flush()
  assert.equal(state.rows.value[0].id, 'filtered')
  void state.open('X')
  void state.open('Y')
  details.at(-1).resolve({ data: event('Y') })
  await flush()
  details.at(-2).resolve({ data: event('X') })
  await flush()
  assert.equal(state.detail.value.id, 'Y')
  await state.act('acknowledge')
  assert.equal(actions.length, 0) // viewer读权不能越过UI发出写入。
  auth.permissions = ['alarm:read', 'alarm:ack']
  await flush()
  void state.open('Y')
  details.at(-1).resolve({ data: event('Y') })
  await flush()
  state.note.value = '检查后确认'
  const action = state.act('acknowledge')
  assert.equal(actions.length, 1)
  assert.equal(actions[0].note, '检查后确认')
  code.value = 'C'
  actions[0].resolve({ data: event('Y', { acknowledgedAt: '2026-10-18T00:00:00Z' }) })
  await action
  assert.equal(state.detail.value, undefined) // 旧站写入响应不能污染新站。
  lists.at(-1).resolve(page([event('C')]))
  await flush()
  auth.permissions = []
  await flush()
  assert.equal(state.rows.value.length, 0)
  assert.equal(state.detail.value, undefined)
  assert.match(state.error.value, /没有告警查看权限/)
  lists.at(-2).resolve(page([event('late')]))
  await flush()
  assert.equal(state.rows.value.length, 0)
} finally {
  app.unmount()
}

// 实际组件的处置按钮条件：只有恢复+确认后可关闭；只读角色没有任何处置按钮。
auth.permissions = ['alarm:read']
const source = readFileSync(
  new URL('../src/components/twin/AlarmPanel.vue', import.meta.url),
  'utf8',
)
const { descriptor } = parse(source)
let compiled = compile(compileScript(descriptor, { id: 'alarm-panel-regression' }).content)
compiled = compiled.replace(
  /from (['"])@\/composables\/useAlarmEvents\1/g,
  `from ${JSON.stringify(composableUrl)}`,
)
const Component = (await import(url(compiled))).default
Component.render = () => null
const componentApp = renderer.createApp({ render: () => h(Component, { siteCode: 'S' }) })
try {
  componentApp.mount({})
  const view = componentApp._instance.subTree.component.setupState
  view.detail = event('E')
  assert.equal(!!view.canAck, false)
  assert.equal(!!view.canClose, false)
  auth.permissions = ['alarm:read', 'alarm:ack', 'alarm:close']
  await flush()
  view.detail = event('E')
  assert.equal(!!view.canAck, true)
  assert.equal(!!view.canClose, false)
  view.detail = event('E', { status: 'RECOVERED', acknowledgedAt: '2026-10-18T00:00:00Z' })
  assert.equal(!!view.canClose, true)
  assert.equal(!!view.canAck, false)
  view.detail = event('E', { status: 'CLOSED', acknowledgedAt: '2026-10-18T00:00:00Z' })
  assert.equal(!!view.canClose, false)
} finally {
  componentApp.unmount()
  delete globalThis.__alarmAuth
  delete globalThis.__alarmApi
}
console.log(
  'Passed: alarm scope isolation, late list/detail/action responses, filters/pages, viewer read-only and valid close controls.',
)
