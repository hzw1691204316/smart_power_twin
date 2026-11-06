<template>
  <section class="relations-page" aria-labelledby="relations-title">
    <header>
      <div>
        <p class="auth-eyebrow">SITE AREAS & HIGHWAY LINKS</p>
        <h1 id="relations-title">站内区域与高速关联</h1>
      </div>
      <nav>
        <RouterLink to="/admin/assets">返回设备台账</RouterLink
        ><RouterLink to="/overview">返回地图</RouterLink>
      </nav>
    </header>
    <p class="relations-note">
      先划分上下行、建筑、配电房、充电区等空间，再把设备分配到区域。路线关系记录方向和米制桩号，不会重新绘制地图。
    </p>
    <p v-if="error" role="alert" class="relations-error">{{ error }}</p>
    <p v-if="message" role="status" class="relations-success">{{ message }}</p>
    <p v-if="busy" role="status">正在读取或保存…</p>
    <section class="relations-panel relations-actions">
      <label
        >授权站点<select v-model="siteId" :disabled="busy || !!editor" @change="loadSite">
          <option value="">无可用站点</option>
          <option v-for="s in sites" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select></label
      ><button :disabled="busy || !!editor" @click="initialize">重读目录</button>
    </section>
    <p v-if="!editable" class="relations-note">
      当前账号只读，维护需要asset:manage权限及本站范围。
    </p>
    <div v-if="site && loaded" class="relations-grid">
      <section class="relations-panel">
        <h2>
          站内区域 <small>{{ areas.length }} 个</small>
        </h2>
        <button
          v-if="editable"
          :disabled="busy || !!editor || site.assetStatus !== 'ACTIVE'"
          @click="open('area')"
        >
          ＋ 新增区域
        </button>
        <div class="relations-table">
          <table>
            <thead>
              <tr>
                <th>区域 / 编码</th>
                <th>类型</th>
                <th>父区域</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in areas" :key="a.id">
                <td>
                  {{ a.name }}<small>{{ a.code }} · ID {{ a.id }}</small>
                </td>
                <td>{{ a.areaType }}</td>
                <td>
                  {{
                    a.parentId
                      ? (areas.find((p) => p.id === a.parentId)?.name ?? `ID ${a.parentId}`)
                      : '顶层'
                  }}
                </td>
                <td>
                  <button v-if="editable" :disabled="busy || !!editor" @click="open('area', a)">
                    编辑</button
                  ><span v-else>只读</span>
                </td>
              </tr>
              <tr v-if="!areas.length">
                <td colspan="4">尚无区域，可以新增后到设备台账分配设备。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      <section class="relations-panel">
        <h2>
          本站高速方向关联 <small>{{ site.routes.length }} 条</small>
        </h2>
        <button
          v-if="editable"
          :disabled="busy || !!editor || site.assetStatus !== 'ACTIVE'"
          @click="open('link')"
        >
          ＋ 新增关联
        </button>
        <div class="relations-table">
          <table>
            <thead>
              <tr>
                <th>路线 / 关联编码</th>
                <th>方向 / 区域</th>
                <th>桩号（米）</th>
                <th>主关联</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in site.routes" :key="r.id">
                <td>
                  {{ r.routeCode }} · {{ r.name }}<small>{{ r.linkCode }} · ID {{ r.id }}</small>
                </td>
                <td>
                  {{ directionName(r.directionCode) }} · {{ r.directionLabel || '未核验说明'
                  }}<small
                    >{{
                      r.areaId
                        ? (areas.find((a) => a.id === r.areaId)?.name ?? `ID ${r.areaId}`)
                        : '未分配区域'
                    }}
                    · {{ accessName(r.accessType) }}</small
                  >
                </td>
                <td>{{ r.chainageM ?? '未知' }}</td>
                <td>{{ r.isPrimary ? '主关联' : '其他关联' }}</td>
                <td>
                  <button v-if="editable" :disabled="busy || !!editor" @click="open('link', r)">
                    编辑</button
                  ><span v-else>只读</span>
                </td>
              </tr>
              <tr v-if="!site.routes.length">
                <td colspan="5">暂无路线关联；需要先在既有公共路线目录中找到路线。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
    <section v-if="editor" ref="editorPanel" class="relations-panel relations-editor">
      <h2>
        {{ editor.record ? '编辑' : '新增'
        }}{{ editor.kind === 'area' ? '站内区域' : '路线方向关联' }}
      </h2>
      <p class="relations-note">
        编辑期间先保存或取消，再切站；离开页面将丢弃未保存输入。已有区域与关联编码固定，当前不提供硬删除。
      </p>
      <RelationForm
        :key="`${siteId}:${editor.kind}:${editor.record?.id ?? 'new'}`"
        :kind="editor.kind"
        :record="editor.record"
        :areas="areas"
        :highways="highways"
        :busy="busy"
        @save="save"
        @cancel="cancel"
      />
    </section>
  </section>
</template>
<script setup lang="ts">
/** 站内关系页：区域父关系和路线方向并列展示，查询/保存及迟到响应交给composable。 */
import { ref, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import RelationForm from '@/components/assets/RelationForm.vue'
import { useSiteRelations } from '@/composables/useSiteRelations'
const route = useRoute()
const {
  sites,
  siteId,
  site,
  areas,
  highways,
  editor,
  editable,
  busy,
  loaded,
  error,
  message,
  initialize,
  loadSite,
  open,
  save,
  cancel,
} = useSiteRelations(typeof route.query.siteId === 'string' ? route.query.siteId : '')
const directionName = (value: string) =>
  ({ UP: '上行', DOWN: '下行', BOTH: '双向', UNKNOWN: '待核验' })[value] ?? value
const accessName = (value: string) =>
  ({ DIRECT: '直接接入', INTERCHANGE: '互通接入', OTHER: '其他' })[value] ?? value
const editorPanel = ref<HTMLElement>()
watch(editor, async (value) => {
  if (value) {
    await nextTick()
    editorPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
})
</script>
<style scoped>
.relations-page {
  max-width: 1600px;
  margin: auto;
  padding: 24px;
  color: var(--ocean-text, #d8efff);
}
header {
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
  margin: 0 0 16px;
}
nav,
.relations-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: end;
}
.relations-panel {
  min-width: 0;
  margin-top: 18px;
  padding: 20px;
  border: 1px solid #36738e;
  border-radius: 20px;
  background: linear-gradient(140deg, #164366dd, #0b2844ee);
}
.relations-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
  gap: 18px;
}
label {
  display: grid;
  gap: 8px;
  flex: 1;
  min-width: 180px;
}
select,
button {
  font: inherit;
  font-size: 14px;
  padding: 10px;
  border-radius: 9px;
  border: 1px solid #4b8ca7;
  background: #103452;
  color: #def4ff;
  min-width: 0;
}
button {
  cursor: pointer;
}
:disabled {
  opacity: 0.5;
}
.relations-note {
  font-size: 14px;
  line-height: 1.8;
  color: #a8cddd;
  overflow-wrap: anywhere;
}
.relations-error {
  color: #ffd084;
  overflow-wrap: anywhere;
}
.relations-success {
  color: #62e6dc;
}
.relations-table {
  overflow: auto;
  max-height: 540px;
  margin-top: 16px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
th,
td {
  padding: 11px;
  text-align: left;
  border-bottom: 1px solid #34718c66;
  white-space: nowrap;
}
th {
  position: sticky;
  top: 0;
  background: #103452;
}
small {
  color: #9fc6d8;
  font-size: 12px;
}
td small {
  display: block;
  margin-top: 6px;
}
.relations-editor {
  scroll-margin-top: 20px;
}
@media (max-width: 1100px) {
  .relations-grid {
    grid-template-columns: 1fr;
    gap: 0;
  }
}
@media (max-width: 650px) {
  .relations-page {
    padding: 12px;
  }
  .relations-panel {
    padding: 14px;
  }
  header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
