/** 场景绑定回归：GLB键边界、对象身份、真实composable迟到响应/公开预览/权限撤销。非视觉验收。 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { createRenderer, h, nextTick, reactive, ref } from 'vue'
import { matchSceneObject, sceneDevices, sceneModelUrl } from '../src/utils/twinPresentation.ts'

const objects = [
  { id: 'object-A', objectKey: 'storage_01' },
  { id: 'object-B', objectKey: 'storage_01_door' },
]
assert.equal(matchSceneObject('storage_01_door_panel', objects).id, 'object-B')
assert.equal(matchSceneObject('storage_010_door', objects), undefined)
assert.equal(matchSceneObject('storage_01.001', objects).id, 'object-A')
assert.equal(sceneModelUrl('/models/service_medium.glb'), '/models/service_medium.glb')
for (const uri of [null, 'https://evil.test/model.glb', '/models/../x.glb', '//evil.test/x.glb'])
  assert.throws(() => sceneModelUrl(uri))
assert.deepEqual(
  sceneDevices({
    objects: [
      {
        id: 'visual-200',
        objectKey: 'any_key',
        name: '真实对象',
        device: { id: 'device-999', systemType: 'ESS' },
      },
      { id: 'decoration', device: null },
    ],
  }),
  [
    {
      id: 'visual-200',
      objectKey: 'any_key',
      name: '真实对象',
      category: '储能系统',
      status: 'unknown',
    },
  ],
)

const auth = reactive({ scopeKey: 'first:1', readable: true, can: () => auth.readable })
const requests = []
globalThis.__twinRegressionAuth = auth
globalThis.__twinRegressionLoad = (site) =>
  new Promise((resolve, reject) => requests.push({ site, resolve, reject }))
const moduleUrl = (content) =>
  `data:text/javascript;base64,${Buffer.from(content).toString('base64')}`
const authModule = moduleUrl('export const useAuthStore=()=>globalThis.__twinRegressionAuth')
const serviceModule = moduleUrl(
  'export const getPublishedScene=(site)=>globalThis.__twinRegressionLoad(site)',
)
let compiled = ts.transpileModule(
  readFileSync(new URL('../src/composables/usePublishedScene.ts', import.meta.url), 'utf8'),
  { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } },
).outputText
compiled = compiled
  .replace(/from (['"])vue\1/g, `from ${JSON.stringify(import.meta.resolve('vue'))}`)
  .replace(/from (['"])@\/stores\/auth\1/g, `from ${JSON.stringify(authModule)}`)
  .replace(/from (['"])@\/services\/twinService\1/g, `from ${JSON.stringify(serviceModule)}`)
  .replace(
    /from (['"])@\/utils\/twinPresentation\1/g,
    `from ${JSON.stringify(new URL('../src/utils/twinPresentation.ts', import.meta.url).href)}`,
  )
const { usePublishedScene } = await import(moduleUrl(compiled))
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
const code = ref('A'),
  isPublic = ref(false)
let state
const app = renderer.createApp({
  setup() {
    state = usePublishedScene(code, isPublic)
    return () => h('div')
  },
})
const flush = async () => {
  for (let i = 0; i < 4; i++) {
    await Promise.resolve()
    await nextTick()
  }
}
try {
  app.mount({})
  assert.equal(requests.length, 1)
  code.value = 'B'
  assert.equal(requests.length, 2)
  requests[1].resolve({ id: 'sceneB', modelUrl: '/models/toll_medium.glb' })
  await flush()
  assert.equal(state.scene.value.id, 'sceneB')
  requests[0].resolve({ id: 'sceneA', modelUrl: '/models/service_medium.glb' })
  await flush()
  assert.equal(state.scene.value.id, 'sceneB')
  isPublic.value = true
  assert.equal(state.scene.value, undefined)
  const count = requests.length
  code.value = 'PUBLIC'
  assert.equal(requests.length, count)
  isPublic.value = false
  requests.at(-1).reject(new Error('本站尚无发布场景'))
  await flush()
  assert.equal(state.scene.value, undefined)
  assert.match(state.error.value, /尚无发布/)
  auth.readable = false
  assert.equal(state.scene.value, undefined)
  assert.match(state.error.value, /没有三维场景权限/)
  assert.equal(requests.length, count + 1)
} finally {
  app.unmount()
  delete globalThis.__twinRegressionAuth
  delete globalThis.__twinRegressionLoad
}
console.log(
  'Passed: database scene identity, complete GLB key matching, stale response isolation, no private query in public preview, revoked permissions.',
)
