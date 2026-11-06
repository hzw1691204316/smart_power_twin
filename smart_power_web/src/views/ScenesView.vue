<template>
  <section class="scene-config" aria-labelledby="scene-config-title">
    <header class="scene-config-heading">
      <div>
        <p class="auth-eyebrow">DIGITAL TWIN CONFIGURATION</p>
        <h1 id="scene-config-title">三维场景配置</h1>
      </div>
      <nav>
        <RouterLink
          v-if="auth.can('device:read') && auth.can('monitor:read')"
          :to="{ path: '/admin/points', query: siteId ? { siteId } : {} }"
          >设备测点管理</RouterLink
        >
        <RouterLink to="/admin/assets">站点与设备台账</RouterLink
        ><RouterLink to="/overview">← 返回地图</RouterLink>
      </nav>
    </header>
    <p class="config-note">
      选择站点 → 选模板或复制当前版本 → 关联本站设备 → 配置测点 →
      保存并发布。模型沿用GLB内置布局，不生成现场读数。
    </p>
    <p v-if="error" role="alert" class="config-error">{{ error }}</p>
    <p v-if="message" role="status" class="config-message">{{ message }}</p>
    <p v-if="busy" role="status">正在读取或保存，请稍候…</p>
    <section class="config-panel config-controls">
      <label
        >授权站点<select v-model="siteId" :disabled="busy || dirty" @change="loadSite">
          <option value="">选择站点</option>
          <option v-for="s in sites" :key="s.id" :value="s.id">
            {{ s.name }} · {{ s.scaleLevel }} · {{ s.isDemo ? '模拟' : '现场' }}
          </option>
        </select></label
      >
      <label
        >已有版本<select
          v-model="selectedVersion"
          :disabled="busy || dirty || !versions.length"
          @change="selectVersion"
        >
          <option value="">暂无版本</option>
          <option v-for="v in versions" :key="v.id" :value="v.id">
            V{{ v.version }} · {{ statusName(v.status) }}
          </option>
        </select></label
      >
      <button :disabled="busy || !siteId" @click="refresh">
        {{ dirty ? '放弃修改并重载' : '重载版本' }}
      </button>
    </section>
    <section v-if="site && auth.can('twin:publish')" class="config-panel">
      <h2>
        1. 创建草稿
        <small
          >{{ site.siteType === 'SERVICE' ? '服务区' : '收费站' }} / {{ site.scaleLevel }}</small
        >
      </h2>
      <div class="config-controls">
        <label
          >与本站类型、规模匹配的已发布模板<select v-model="templateId" :disabled="busy || dirty">
            <option value="">无可用模板</option>
            <option v-for="t in availableTemplates" :key="t.id" :value="t.id">
              {{ t.code }} · 版本 {{ t.version }}
            </option>
          </select></label
        >
        <button
          :disabled="busy || dirty || !templateId || site.assetStatus !== 'ACTIVE'"
          @click="create"
        >
          从模板创建草稿
        </button>
        <button
          :disabled="busy || dirty || !versions.some((v) => v.status === 'PUBLISHED')"
          @click="clone"
        >
          复制当前发布版本
        </button>
      </div>
      <p class="config-note">
        每次创建产生独立版本。对象名称初始使用模型键，请改成便于识别的名称；设备关系由你选择，不按名称猜测。
      </p>
      <p v-if="!availableTemplates.length" class="config-error">
        此类型/规模没有已发布资源。大型服务区需手动导入C07模板注册SQL；其他未制作模型不能直接发布。
      </p>
    </section>
    <template v-if="scene">
      <section class="config-panel">
        <h2>
          2. 模型对象与设备 <small>V{{ scene.version }} · {{ statusName(scene.status) }}</small>
        </h2>
        <p class="config-note">
          {{ scene.modelUrl || '缺少模型资源' }} ·
          {{ scene.isDemo ? '模拟场景' : '业务场景，是否现场数据以设备和采样来源为准' }}
        </p>
        <p v-if="warning" role="alert" class="config-error">{{ warning }}</p>
        <p class="config-note">
          未关联设备的对象只作为模型背景。已绑定测点的对象需先在下方移除并保存相关绑定，才能换设备或删除。停用设备保留历史关系。
        </p>
        <div class="config-table-wrap">
          <table>
            <thead>
              <tr>
                <th>GLB对象键</th>
                <th>显示名称</th>
                <th>本站设备</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(o, index) in objectRows" :key="o.objectKey">
                <td class="config-key">{{ o.objectKey }}</td>
                <td>
                  <input
                    v-model="o.name"
                    :aria-label="`${o.objectKey}显示名称`"
                    maxlength="100"
                    :disabled="!writable || busy || bindingsDirty"
                    @input="objectsDirty = true"
                  />
                </td>
                <td>
                  <select
                    v-model="o.deviceId"
                    :aria-label="`${o.objectKey}关联设备`"
                    :disabled="!writable || busy || bindingsDirty || !auth.can('device:read')"
                    @change="objectsDirty = true"
                  >
                    <option :value="null">不关联设备</option>
                    <option
                      v-if="o.deviceId && !devices.some((d) => d.id === o.deviceId)"
                      :value="o.deviceId"
                    >
                      原设备ID {{ o.deviceId }}（目录未加载）
                    </option>
                    <option v-for="d in devices" :key="d.id" :value="d.id">
                      {{ d.name }} · {{ d.code }} · {{ d.isDemo ? '模拟' : '现场' }} ·
                      {{ d.assetStatus }}
                    </option>
                  </select>
                </td>
                <td>
                  <button
                    v-if="writable"
                    :disabled="busy || bindingsDirty"
                    @click="removeObject(index)"
                  >
                    移除</button
                  ><span v-else>只读</span>
                </td>
              </tr>
              <tr v-if="!objectRows.length">
                <td colspan="4">暂无对象，从下方选择GLB对象键。</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="writable" class="config-controls config-bottom">
          <label
            >增加对象<select v-model="newKey" :disabled="busy || bindingsDirty">
              <option value="">选择模型对象键</option>
              <option
                v-for="key in keys.filter((k) => !objectRows.some((o) => o.objectKey === k))"
                :key="key"
                :value="key"
              >
                {{ key }}
              </option>
            </select></label
          >
          <button :disabled="busy || bindingsDirty || !newKey" @click="addObject">增加对象</button
          ><button :disabled="busy || !objectsDirty || bindingsDirty" @click="saveObjects">
            保存对象关系
          </button>
        </div>
      </section>
      <section class="config-panel">
        <h2>3. 对象属性与测点</h2>
        <p class="config-note">
          先保存对象关系，再配置绑定。属性编码是展示字段，单位取自测点；多个对象可关联同一设备，不代表多台设备或重复计量。
        </p>
        <div class="config-table-wrap">
          <table>
            <thead>
              <tr>
                <th>对象</th>
                <th>属性编码</th>
                <th>同设备测点</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(b, index) in bindingRows" :key="index">
                <td>{{ scene.objects.find((o) => o.id === b.objectId)?.name ?? b.objectId }}</td>
                <td>
                  <input
                    v-model="b.propertyCode"
                    aria-label="绑定属性编码"
                    pattern="[a-z][a-z0-9_]{0,63}"
                    maxlength="64"
                    :disabled="!writable || busy || objectsDirty"
                    @input="bindingsDirty = true"
                  />
                </td>
                <td>
                  <select
                    v-model="b.pointId"
                    aria-label="绑定测点"
                    :disabled="!writable || busy || objectsDirty || !auth.can('monitor:read')"
                    @change="bindingsDirty = true"
                  >
                    <option
                      v-if="!pointsFor(b.objectId).some((p) => p.id === b.pointId)"
                      :value="b.pointId"
                    >
                      原测点ID {{ b.pointId }}（目录未加载）
                    </option>
                    <option v-for="p in pointsFor(b.objectId)" :key="p.id" :value="p.id">
                      {{ p.name }} · {{ p.unit }}{{ p.enabled ? '' : '（停用）' }}
                    </option>
                  </select>
                </td>
                <td>
                  <button
                    v-if="writable"
                    :disabled="busy || objectsDirty"
                    @click="removeBinding(index)"
                  >
                    移除</button
                  ><span v-else>只读</span>
                </td>
              </tr>
              <tr v-if="!bindingRows.length">
                <td colspan="4">
                  暂无测点绑定。发布至少需要一个绑定；新增测点可前往设备测点管理页面。
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="writable" class="config-controls config-bottom">
          <label
            >选择已关联设备的对象<select v-model="newObjectId" :disabled="busy || objectsDirty">
              <option value="">选择对象</option>
              <option
                v-for="o in scene.objects.filter((o) => o.deviceId)"
                :key="o.id"
                :value="o.id"
              >
                {{ o.name }}
              </option>
            </select></label
          >
          <button
            :disabled="busy || objectsDirty || !newObjectId || !auth.can('monitor:read')"
            @click="addBinding"
          >
            增加绑定</button
          ><button :disabled="busy || objectsDirty || !bindingsDirty" @click="saveBindings">
            保存测点绑定
          </button>
        </div>
      </section>
      <section class="config-panel config-publish">
        <div>
          <h2>4. 检查并发布</h2>
          <p class="config-note">
            {{
              dirty
                ? '有未保存修改，请先保存。'
                : '已保存。发布后替换本站当前版本，原发布版本保留为历史。'
            }}
          </p>
          <p v-if="!auth.can('twin:publish')" class="config-note">当前账号仅查看已发布版本。</p>
        </div>
        <button v-if="writable" :disabled="busy || dirty" @click="publish">发布此草稿</button>
      </section>
    </template>
    <p v-else-if="!busy" class="config-note">
      {{
        siteId ? '本站尚无场景。管理员可从上方选择匹配模板创建草稿。' : '当前没有可管理的授权站点。'
      }}
    </p>
  </section>
</template>

<script setup lang="ts">
/** 场景配置页只承载管理布局；不改变地图及三维大屏，业务与异步隔离交给composable。 */
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSceneConfiguration } from '@/composables/useSceneConfiguration'
const auth = useAuthStore()
const route = useRoute()
const initialSite = typeof route.query.siteId === 'string' ? route.query.siteId : ''
const {
  sites,
  siteId,
  site,
  versions,
  selectedVersion,
  availableTemplates,
  templateId,
  scene,
  devices,
  objectRows,
  bindingRows,
  keys,
  pointsFor,
  newKey,
  newObjectId,
  busy,
  error,
  message,
  warning,
  objectsDirty,
  bindingsDirty,
  dirty,
  writable,
  loadSite,
  selectVersion,
  refresh,
  create,
  clone,
  saveObjects,
  saveBindings,
  publish,
  addObject,
  removeObject,
  addBinding,
  removeBinding,
} = useSceneConfiguration(initialSite)
const statusName = (status: string) =>
  ({ DRAFT: '草稿', PUBLISHED: '已发布', ARCHIVED: '已归档' })[status] ?? status
</script>

<style scoped>
.scene-config {
  max-width: 1500px;
  margin: auto;
  padding: 24px;
  color: var(--ocean-text, #d8efff);
}
.scene-config-heading,
.config-publish {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
h1 {
  font-size: 26px;
}
h2 {
  font-size: 20px;
  margin: 0 0 12px;
}
small {
  font-size: 14px;
  color: #9ec5df;
}
nav,
.config-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 12px;
}
.config-panel {
  margin: 16px 0;
  border: 1px solid #36738e;
  border-radius: 20px;
  padding: 20px;
  background: linear-gradient(140deg, #164366dd, #0b2844ee);
  min-width: 0;
}
.config-controls label {
  display: grid;
  gap: 8px;
  flex: 1;
  min-width: 200px;
}
.config-note {
  line-height: 1.8;
  font-size: 14px;
  color: #abcddd;
  overflow-wrap: anywhere;
}
.config-error {
  color: #ffd084;
  overflow-wrap: anywhere;
}
.config-message {
  color: #62e6dc;
}
input,
select,
button {
  font: inherit;
  font-size: 14px;
  padding: 10px;
  border: 1px solid #4b8ca7;
  border-radius: 9px;
  color: #def4ff;
  background: #103452;
  min-width: 0;
}
button {
  cursor: pointer;
}
button:disabled,
input:disabled,
select:disabled {
  opacity: 0.55;
  cursor: default;
}
.config-table-wrap {
  overflow: auto;
  max-height: 560px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
th,
td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid #34718c66;
}
th {
  position: sticky;
  top: 0;
  background: #103452;
  z-index: 1;
}
td input {
  width: 100%;
  min-width: 150px;
  box-sizing: border-box;
}
td select {
  width: 100%;
  min-width: 230px;
}
.config-key {
  overflow-wrap: anywhere;
  min-width: 170px;
  max-width: 250px;
}
.config-bottom {
  margin-top: 16px;
}
@media (max-width: 700px) {
  .scene-config {
    padding: 12px;
  }
  .scene-config-heading,
  .config-publish {
    align-items: flex-start;
    flex-direction: column;
  }
  .config-panel {
    padding: 14px;
  }
}
</style>
