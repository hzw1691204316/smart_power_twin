<template>
  <form class="point-form" @submit.prevent="submit">
    <template v-if="!record">
      <label class="point-wide"
        >快捷填写（仍需核对后保存）<select v-model="preset" :disabled="busy" @change="applyPreset">
          <option value="">自定义测点</option>
          <option v-for="p in pointPresets" :key="p.code" :value="p.code">
            {{ p.name }} / {{ p.unit }}
          </option>
        </select></label
      >
      <label
        >设备内测点编码<input
          v-model="form.code"
          required
          maxlength="64"
          pattern="[a-z][a-z0-9_]{0,63}"
          placeholder="例如 active_power"
          :disabled="busy"
      /></label>
      <label
        >测点名称<input
          v-model="form.name"
          required
          maxlength="100"
          placeholder="例如 有功功率"
          :disabled="busy"
      /></label>
      <label
        >单位<input
          v-model="form.unit"
          required
          maxlength="32"
          placeholder="kW / kWh / °C / % / BOOL"
          :disabled="busy"
      /></label>
      <label
        >数据类型<select v-model="form.valueType" :disabled="busy" @change="changeType">
          <option value="NUMERIC">NUMERIC · 数值</option>
          <option value="BOOLEAN">BOOLEAN · 布尔0/1</option>
          <option value="TEXT">TEXT · 文本</option>
        </select></label
      >
      <label
        >聚合类型<select
          v-model="form.aggregationType"
          :disabled="busy || form.valueType !== 'NUMERIC'"
        >
          <option v-if="form.valueType === 'NUMERIC'" value="INSTANT">INSTANT · 瞬时量</option>
          <option v-if="form.valueType === 'NUMERIC'" value="COUNTER">COUNTER · 累计量</option>
          <option value="STATE">STATE · 状态量</option>
        </select></label
      >
      <label
        >正负方向说明<input
          v-model="form.directionConvention"
          maxlength="300"
          placeholder="例如：储能正放电、负充电；未知可留空"
          :disabled="busy"
      /></label>
    </template>
    <div v-else class="point-identity point-wide">
      <strong>{{ record.name }} · {{ record.code }}</strong>
      <p>
        {{ record.unit }} · {{ record.valueType }} / {{ record.aggregationType }} · ID
        {{ record.id }}
      </p>
      <p>{{ record.directionConvention || '正负方向未填写' }}</p>
      <p>编码、名称、单位、类型和方向说明保持创建时定义，本页只调整下方采样配置。</p>
    </div>
    <label
      >采样周期（毫秒）<input
        v-model="form.sampleIntervalMs"
        inputmode="numeric"
        required
        :disabled="busy"
      /><small>5000毫秒 = 5秒；这是建议周期，不会控制采集硬件。</small></label
    >
    <label
      >陈旧时间（毫秒）<input
        v-model="form.staleAfterMs"
        inputmode="numeric"
        required
        :disabled="busy"
      /><small>不得小于采样周期，超时读数会标为陈旧。</small></label
    >
    <label
      >低阈值（{{ form.unit || '测点单位' }}）<input
        v-model="form.alarmLow"
        inputmode="decimal"
        placeholder="留空表示不设置"
        :disabled="busy || form.valueType !== 'NUMERIC'"
    /></label>
    <label
      >高阈值（{{ form.unit || '测点单位' }}）<input
        v-model="form.alarmHigh"
        inputmode="decimal"
        placeholder="留空表示不设置"
        :disabled="busy || form.valueType !== 'NUMERIC'"
    /></label>
    <label class="point-enabled point-wide"
      ><input v-model="form.enabled" type="checkbox" :disabled="busy" />接收该测点的新样本</label
    >
    <p class="point-note point-wide">
      编码在本设备内唯一，创建后身份与单位固定。留空阈值与0不同。文本/布尔不配置数值阈值；停用保留历史、模型绑定和告警。阈值修改在后续有效采样时参与判定，不会重写旧告警。
    </p>
    <p v-if="error" role="alert" class="point-error point-wide">{{ error }}</p>
    <div class="point-form-actions point-wide">
      <button :disabled="busy">{{ busy ? '正在保存…' : record ? '保存配置' : '新增测点' }}</button
      ><button type="button" :disabled="busy" @click="emit('cancel')">取消编辑</button>
    </div>
  </form>
</template>

<script setup lang="ts">
/** 测点编辑表单：新增才显示身份字段；字符串数值校验后发白名单，不直接提交响应对象。
 * 数值框使用inputmode保持字符串；type=number会触发Vue自动数值转换，破坏空字符串/0的区分。
 */
import { reactive, ref } from 'vue'
import { pointConfigPayload, pointCreatePayload, pointForm, pointPresets } from '@/utils/pointForms'
import type { ManagedPoint, PointConfigInput, PointCreateInput } from '@/types/monitoring'
const props = defineProps<{ record?: ManagedPoint; busy: boolean }>()
const emit = defineEmits<{ save: [body: PointCreateInput | PointConfigInput]; cancel: [] }>()
const form = reactive(pointForm(props.record)),
  error = ref(''),
  preset = ref('')
/** 仅新增时切换类型；不能把已有文本阈值残留带入布尔/文本创建请求。 */
function changeType() {
  if (form.valueType !== 'NUMERIC') {
    form.aggregationType = 'STATE'
    form.alarmLow = ''
    form.alarmHigh = ''
  }
}
/** 快捷项只更新身份和类型，保留周期输入；阈值清空待用户核实，不预设现场标准。 */
function applyPreset() {
  const item = pointPresets.find((p) => p.code === preset.value)
  if (!item) return
  Object.assign(form, item, { alarmLow: '', alarmHigh: '', directionConvention: '' })
  changeType()
  error.value = ''
}
/** 校验失败在本表单显示；编辑时使用服务器记录的类型，不信任可变表单身份。 */
function submit() {
  if (props.busy) return
  error.value = ''
  try {
    emit(
      'save',
      props.record ? pointConfigPayload(form, props.record.valueType) : pointCreatePayload(form),
    )
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '请检查填写内容'
  }
}
</script>

<style scoped>
.point-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
label {
  display: grid;
  gap: 7px;
  min-width: 0;
  font-size: 14px;
}
input,
select,
button {
  font: inherit;
  border-radius: 9px;
  padding: 10px;
  color: #def4ff;
  background: #103452;
  border: 1px solid #4b8ca7;
  box-sizing: border-box;
  min-width: 0;
}
input:not([type='checkbox']),
select {
  width: 100%;
}
button {
  cursor: pointer;
}
:disabled {
  opacity: 0.55;
}
.point-wide {
  grid-column: 1/-1;
}
.point-enabled {
  display: flex;
  align-items: center;
  gap: 8px;
}
.point-enabled input {
  width: 18px;
  height: 18px;
}
.point-form-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.point-note,
small,
.point-identity p {
  color: #a8cddd;
  line-height: 1.8;
  font-size: 13px;
  margin: 0;
  overflow-wrap: anywhere;
}
.point-identity {
  border-left: 3px solid #29c6e0;
  padding: 8px 14px;
  background: #0b2a4580;
}
.point-error {
  color: #ffd084;
  overflow-wrap: anywhere;
}
@media (max-width: 650px) {
  .point-form {
    grid-template-columns: 1fr;
  }
}
</style>
