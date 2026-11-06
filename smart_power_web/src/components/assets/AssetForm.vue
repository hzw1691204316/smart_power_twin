<template>
  <form class="asset-form" @submit.prevent="emit('save', assetPayload(kind, !record, form))">
    <p v-if="record" class="asset-note">
      编码、类型、来源与归属站点在创建后固定。修改名称或停用不会删除测点、历史和三维绑定。
    </p>
    <label v-for="field in fields" :key="field.key"
      >{{ field.label }}
      <select
        v-if="field.type === 'select'"
        v-model="form[field.key]"
        :required="field.required"
        :disabled="busy"
      >
        <option
          v-if="
            !field.required &&
            !['assetStatus', 'scaleLevel', 'isDemo', 'siteType', 'systemType'].includes(field.key)
          "
          value=""
        >
          未指定
        </option>
        <option v-for="option in options(field)" :key="option[0]" :value="option[0]">
          {{ option[1] }}
        </option>
      </select>
      <input
        v-else
        v-model="form[field.key]"
        :required="field.required"
        :maxlength="field.max"
        :disabled="busy"
        :type="field.type === 'number' ? 'number' : 'text'"
        :step="field.type === 'number' ? 'any' : undefined"
        :min="
          field.type === 'number' && !['longitude', 'latitude'].includes(field.key) ? 0 : undefined
        "
        autocomplete="off"
      />
    </label>
    <div class="asset-actions">
      <button type="submit" :disabled="busy">
        {{ busy ? '正在保存…' : record ? '保存修改' : '新增台账' }}</button
      ><button type="button" :disabled="busy" @click="emit('cancel')">取消</button>
    </div>
  </form>
</template>
<script setup lang="ts">
/** 站点/设备复用表单；record为空为新增，白名单定义决定显示字段与提交参数。 */
import { computed, ref, watch } from 'vue'
import { assetFields, assetForm, assetPayload, type AssetField } from '@/utils/assetForms'
import type { AssetArea, AssetBody, AssetDevice, AssetSite, HighwayOption } from '@/types/assets'
const props = defineProps<{
  kind: 'site' | 'device'
  record?: AssetSite | AssetDevice
  busy: boolean
  areas: AssetArea[]
  highways: HighwayOption[]
}>()
const emit = defineEmits<{ save: [AssetBody]; cancel: [] }>()
const form = ref<Record<string, string>>({})
watch(
  () => [props.kind, props.record],
  () => {
    form.value = assetForm(props.kind, props.record)
  },
  { immediate: true },
)
const fields = computed(() => assetFields(props.kind, !props.record))
/** 旧主路线/区域即使被停用也保留当前ID，避免打开表单就无意清除归属。 */
function options(field: AssetField): [string, string][] {
  let rows: [string, string][] =
    field.key === 'areaId'
      ? props.areas.map((a) => [a.id, a.name])
      : field.key === 'primaryRouteId'
        ? props.highways.map((r) => [r.id, `${r.routeCode} ${r.name}`])
        : (field.options ?? [])
  const current = form.value[field.key]
  if (current && !rows.some((r) => r[0] === current))
    rows = [...rows, [current, `当前值 ${current}`]]
  return rows
}
</script>
