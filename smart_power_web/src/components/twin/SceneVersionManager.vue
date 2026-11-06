<template>
  <details class="scene-manager" @toggle="openManager">
    <summary>
      场景版本 {{ current.version }} · {{ current.objects.length }} 对象 /
      {{ current.bindings.length }} 绑定
    </summary>
    <p>当前模型只展示已发布版本。草稿保存不会立即影响监测。</p>
    <button :disabled="busy" @click="emit('refresh')">刷新已发布场景</button>
    <template v-if="auth.can('twin:publish')">
      <div class="scene-actions">
        <button :disabled="busy" @click="runClone">复制为新草稿</button
        ><select v-model="selectedId" aria-label="场景版本" :disabled="busy" @change="loadSelected">
          <option v-for="s in versions" :key="s.id" :value="s.id">
            版本 {{ s.version }} · {{ statusName(s.status) }}
          </option>
        </select>
      </div>
      <p v-if="busy">正在处理场景…</p>
      <p v-if="error" role="alert" class="scene-error">{{ error }}</p>
      <p v-if="message" role="status">{{ message }}</p>
      <template v-if="editing">
        <p>正在查看版本 {{ editing.version }}（{{ statusName(editing.status) }}）</p>
        <div class="binding-editor">
          <div
            v-for="(row, index) in rows"
            :key="`${row.objectId}:${row.propertyCode}`"
            class="binding-row"
          >
            <label
              >{{ objectName(row.objectId) }} · {{ row.propertyCode
              }}<select
                v-model="row.pointId"
                :disabled="editing.status !== 'DRAFT' || busy"
                @change="dirty = true"
              >
                <option v-for="p in pointsFor(row.objectId)" :key="p.id" :value="p.id">
                  {{ p.name }} / {{ p.unit }}{{ p.enabled ? '' : '（停用）' }}
                </option>
              </select></label
            ><button
              v-if="editing.status === 'DRAFT'"
              :disabled="busy"
              @click="removeBinding(index)"
            >
              移除
            </button>
          </div>
          <p v-if="!rows.length">此版本暂无绑定。</p>
        </div>
        <div v-if="editing.status === 'DRAFT'" class="scene-actions">
          <select v-model="newObject" aria-label="新增绑定的对象">
            <option value="">选择对象</option>
            <option v-for="o in editing.objects.filter((o) => o.device)" :key="o.id" :value="o.id">
              {{ o.name }}
            </option></select
          ><button :disabled="busy || !newObject" @click="addBinding">增加测点绑定</button>
        </div>
        <div v-if="editing.status === 'DRAFT'" class="scene-actions">
          <button :disabled="busy || !dirty" @click="runSave">保存草稿绑定</button
          ><button :disabled="busy || dirty" @click="runPublish">发布此版本</button>
        </div>
        <p v-if="dirty" class="scene-error">
          有未保存修改，请先保存再发布。切换版本会放弃未保存修改。
        </p>
      </template>
    </template>
    <p v-else>当前账号仅查看已发布场景；编辑和发布由管理员完成。</p>
  </details>
</template>

<script setup lang="ts">
/** 草稿管理组件：只编辑当前站点的测点绑定；模型始终由父页面按已发布版本展示。 */
import { onUnmounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import * as api from '@/services/twinService'
import { getPoints } from '@/services/monitoringService'
import type { BindingInput, SceneSummary, TwinSceneData } from '@/types/twin'
import type { PointDefinition } from '@/types/monitoring'
const props = defineProps<{ current: TwinSceneData }>()
const emit = defineEmits<{ refresh: [] }>()
const auth = useAuthStore()
const versions = ref<SceneSummary[]>([props.current]),
  selectedId = ref(props.current.id)
const editing = ref<TwinSceneData>(),
  rows = ref<BindingInput[]>([]),
  points = ref<Record<string, PointDefinition[]>>({})
const busy = ref(false),
  dirty = ref(false),
  error = ref(''),
  message = ref(''),
  newObject = ref('')
let alive = true,
  opened = false
onUnmounted(() => {
  alive = false
})
const statusName = (s: string) =>
  ({ DRAFT: '草稿', PUBLISHED: '已发布', ARCHIVED: '已归档' })[s] ?? s
const objectName = (id: string) => editing.value?.objects.find((o) => o.id === id)?.name ?? id
const pointsFor = (id: string) =>
  points.value[editing.value?.objects.find((o) => o.id === id)?.deviceId ?? ''] ?? []

/** 安装服务器版本并查询其设备测点；API返回成功后才替换编辑状态，不沿用旧对象ID。 */
async function install(scene: TwinSceneData) {
  const ids = [...new Set(scene.objects.flatMap((o) => (o.deviceId ? [o.deviceId] : [])))]
  const definitions = auth.can('monitor:read')
    ? await Promise.all(ids.map(async (id) => [id, (await getPoints(id)).data] as const))
    : []
  if (!alive) return
  editing.value = scene
  selectedId.value = scene.id
  rows.value = scene.bindings.map((b) => ({
    objectId: b.objectId,
    pointId: b.pointId,
    propertyCode: b.propertyCode,
    mappingConfig: b.mappingConfig,
  }))
  points.value = Object.fromEntries(definitions)
  dirty.value = false
  newObject.value = ''
}
async function act(task: () => Promise<void>) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    await task()
  } catch (cause) {
    if (alive) error.value = cause instanceof Error ? cause.message : '场景操作失败'
  } finally {
    if (alive) busy.value = false
  }
}
async function openManager(event: Event) {
  if (!(event.target as HTMLDetailsElement).open || opened || !auth.can('twin:publish')) return
  opened = true
  await act(async () => {
    versions.value = await api.getSceneVersions(props.current.siteId)
    await install(props.current)
  })
}
async function loadSelected() {
  await act(async () => {
    await install((await api.getScene(selectedId.value)).data)
  })
}
async function runClone() {
  await act(async () => {
    const draft = (await api.cloneScene(props.current.siteId)).data
    await install(draft)
    if (alive) versions.value = await api.getSceneVersions(props.current.siteId)
  })
}
async function runSave() {
  if (!editing.value) return
  await act(async () => {
    await install((await api.saveBindings(editing.value!.id, rows.value)).data)
    if (alive) message.value = '草稿绑定已保存，当前已发布场景未改变'
  })
}
async function runPublish() {
  if (!editing.value || dirty.value) return
  await act(async () => {
    await api.publishScene(editing.value!.id)
    if (alive) emit('refresh')
  })
}
function addBinding() {
  const available = pointsFor(newObject.value).find(
    (p) => !rows.value.some((r) => r.objectId === newObject.value && r.propertyCode === p.code),
  )
  if (!available) {
    error.value = '该对象没有可增加的测点；修改现有选择或先在监测模块配置测点'
    return
  }
  rows.value.push({
    objectId: newObject.value,
    pointId: available.id,
    propertyCode: available.code,
    mappingConfig: null,
  })
  dirty.value = true
}
/** 移除仅修改本地草稿，保存按钮才发出完整替换请求。 */
function removeBinding(index: number) {
  rows.value.splice(index, 1)
  dirty.value = true
}
</script>

<style scoped>
.scene-manager {
  font-size: 12px;
  line-height: 1.7;
  margin: 8px 0 14px;
  padding: 9px;
  border: 1px solid var(--ocean-border);
  border-radius: 12px;
  color: var(--ocean-secondary);
}
summary {
  cursor: pointer;
  color: var(--ocean-text);
}
p {
  margin: 7px 0;
  overflow-wrap: anywhere;
}
button,
select {
  font: inherit;
  color: var(--ocean-text);
  border: 1px solid var(--ocean-border);
  background: #0c2b49;
  border-radius: 8px;
  padding: 6px;
  min-width: 0;
}
button {
  cursor: pointer;
}
button:disabled {
  opacity: 0.5;
}
.scene-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.scene-actions select {
  max-width: 100%;
  flex: 1;
}
.binding-editor {
  max-height: 270px;
  overflow: auto;
}
.binding-row {
  display: flex;
  align-items: end;
  gap: 5px;
  padding: 7px 0;
  border-top: 1px solid #28618c55;
}
.binding-row label {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}
.binding-row select {
  width: 100%;
  display: block;
}
.scene-error {
  color: var(--amber);
}
</style>
