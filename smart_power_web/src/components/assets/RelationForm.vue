<template>
  <form class="relation-form" @submit.prevent="submit">
    <template v-if="kind === 'area'">
      <label v-if="!record"
        >区域编码<input
          v-model="form.code"
          required
          maxlength="64"
          placeholder="例如 NORTH_POWER"
          :disabled="busy"
      /></label>
      <p v-else>区域编码：{{ form.code }}（固定）</p>
      <label>区域名称<input v-model="form.name" required maxlength="150" :disabled="busy" /></label>
      <label
        >区域类型<input
          v-model="form.areaType"
          list="relation-area-types"
          required
          maxlength="32"
          :disabled="busy" /><datalist id="relation-area-types">
          <option
            v-for="t in [
              'DIRECTION',
              'BUILDING',
              'PARKING',
              'POWER_ROOM',
              'CHARGING',
              'PV',
              'ESS',
              'OTHER',
            ]"
            :key="t"
            :value="t"
          /></datalist
      ></label>
      <label
        >父区域<select v-model="form.parentId" :disabled="busy">
          <option value="">顶层区域</option>
          <option v-for="a in parents" :key="a.id" :value="a.id">
            {{ a.name }} · {{ a.code }}
          </option>
        </select></label
      >
      <p class="relation-wide relation-note">
        父区域只能选本站区域，不能指向自身或后代。修改区域名称不会改变设备所在区域ID；新增后可到设备台账分配所属区域。
      </p>
    </template>
    <template v-else>
      <label v-if="!record"
        >关联编码<input
          v-model="form.linkCode"
          required
          maxlength="64"
          placeholder="例如 G4_UP"
          :disabled="busy"
      /></label>
      <p v-else>关联编码：{{ form.linkCode }}（固定）</p>
      <label
        >既有高速路线<select v-model="form.routeId" required :disabled="busy">
          <option value="">请选择路线</option>
          <option
            v-for="r in highways"
            :key="r.id"
            :value="r.id"
            :disabled="r.status !== 'ACTIVE' && r.id !== originalRoute"
          >
            {{ r.routeCode }} · {{ r.name }}{{ r.status === 'ACTIVE' ? '' : '（停用）' }}
          </option>
        </select></label
      >
      <label
        >对应站内区域<select v-model="form.areaId" :disabled="busy">
          <option value="">未分配</option>
          <option v-for="a in areas" :key="a.id" :value="a.id">{{ a.name }} · {{ a.code }}</option>
        </select></label
      >
      <label
        >方向编码<select v-model="form.directionCode" :disabled="busy">
          <option value="UNKNOWN">待核验 UNKNOWN</option>
          <option value="UP">上行 UP</option>
          <option value="DOWN">下行 DOWN</option>
          <option value="BOTH">双向 BOTH</option>
        </select></label
      >
      <label
        >方向说明<input
          v-model="form.directionLabel"
          maxlength="100"
          placeholder="如往郑州方向；未知留空"
          :disabled="busy"
      /></label>
      <label
        >里程桩号（米）<input
          v-model="form.chainageM"
          inputmode="decimal"
          placeholder="如K23+456.5，填写23456.5；未知留空"
          :disabled="busy"
      /></label>
      <label
        >接入类型<select v-model="form.accessType" :disabled="busy">
          <option value="DIRECT">直接接入</option>
          <option value="INTERCHANGE">互通接入</option>
          <option value="OTHER">其他</option>
        </select></label
      >
      <label class="relation-check"
        ><input v-model="form.isPrimary" type="checkbox" :disabled="busy" />设为本站主关联</label
      >
      <p class="relation-wide relation-note">
        同一路线可用不同关联编码记录上下行。设为主关联会取消其他主标记，保留其方向、桩号和区域资料。取消主标记不删除关联；本页不修改公共路线字典或地图上的高速几何。
      </p>
    </template>
    <p v-if="error" role="alert" class="relation-error relation-wide">{{ error }}</p>
    <div class="relation-wide relation-actions">
      <button :disabled="busy">{{ busy ? '正在保存…' : record ? '保存修改' : '新增记录' }}</button
      ><button type="button" :disabled="busy" @click="emit('cancel')">取消编辑</button>
    </div>
  </form>
</template>
<script setup lang="ts">
/** 区域/路线关联表单：新增编码、编辑白名单、米制桩号字符串与区域父选项；不直接写库。 */
import { computed, reactive, ref } from 'vue'
import { areaParents, relationForm, relationPayload } from '@/utils/relationForms'
import type { RelationKind, RelationRecord } from '@/utils/relationForms'
import type { AssetArea, AssetBody, HighwayOption } from '@/types/assets'
const props = defineProps<{
  kind: RelationKind
  record?: RelationRecord
  areas: AssetArea[]
  highways: HighwayOption[]
  busy: boolean
}>()
const emit = defineEmits<{ save: [body: AssetBody]; cancel: [] }>()
const form = reactive(relationForm(props.kind, props.record)),
  error = ref('')
const parents = computed(() =>
  areaParents(props.areas, props.kind === 'area' ? props.record?.id : undefined),
)
const originalRoute = props.record && 'routeId' in props.record ? props.record.routeId : ''
/** 校验失败留在本表单；只有校验通过才发出允许字段，身份列在编辑时不提交。 */
function submit() {
  if (props.busy) return
  error.value = ''
  try {
    emit('save', relationPayload(props.kind, !props.record, form))
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '请检查填写内容'
  }
}
</script>
<style scoped>
.relation-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
label {
  display: grid;
  gap: 8px;
  min-width: 0;
  font-size: 14px;
}
input,
select,
button {
  font: inherit;
  color: #def4ff;
  background: #103452;
  border: 1px solid #4b8ca7;
  border-radius: 9px;
  padding: 10px;
  min-width: 0;
  box-sizing: border-box;
}
input:not([type='checkbox']),
select {
  width: 100%;
}
:disabled {
  opacity: 0.5;
}
button {
  cursor: pointer;
}
.relation-wide {
  grid-column: 1/-1;
}
.relation-check,
.relation-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.relation-note {
  color: #a8cddd;
  line-height: 1.8;
  font-size: 14px;
}
.relation-error {
  color: #ffd084;
  overflow-wrap: anywhere;
}
@media (max-width: 650px) {
  .relation-form {
    grid-template-columns: 1fr;
  }
}
</style>
