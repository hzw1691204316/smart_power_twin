/** 测点表单纯逻辑：数字输入以字符串保存，明确区分留空与0，按后端白名单生成请求。 */
import type {
  ManagedPoint,
  PointConfigInput,
  PointCreateInput,
  PointDefinition,
} from '@/types/monitoring'

export interface PointFormState {
  code: string
  name: string
  unit: string
  valueType: PointDefinition['valueType']
  aggregationType: PointDefinition['aggregationType']
  directionConvention: string
  sampleIntervalMs: string
  staleAfterMs: string
  alarmLow: string
  alarmHigh: string
  enabled: boolean
}

/** record为空时创建空表单；编辑时保留0和负阈值，不用真假判断把0变成空白。 */
export function pointForm(record?: ManagedPoint): PointFormState {
  return {
    code: record?.code ?? '',
    name: record?.name ?? '',
    unit: record?.unit ?? '',
    valueType: record?.valueType ?? 'NUMERIC',
    aggregationType: record?.aggregationType ?? 'INSTANT',
    directionConvention: record?.directionConvention ?? '',
    sampleIntervalMs: String(record?.sampleIntervalMs ?? 5000),
    staleAfterMs: String(record?.staleAfterMs ?? 15000),
    alarmLow: record?.alarmLow == null ? '' : String(record.alarmLow),
    alarmHigh: record?.alarmHigh == null ? '' : String(record.alarmHigh),
    enabled: record?.enabled ?? true,
  }
}

function period(value: string, label: string, max: number) {
  const text = value.trim(),
    number = Number(text)
  if (!text || !Number.isSafeInteger(number) || number < 100 || number > max)
    throw new Error(`${label}须为100—${max}之间的整数，单位为毫秒`)
  return number
}
function threshold(value: string) {
  if (!value.trim()) return null
  const number = Number(value.trim())
  if (!Number.isFinite(number)) throw new Error('告警阈值必须是有限数字，留空表示不设置')
  return number
}
/** 返回周期/启用/阈值白名单；非数值点不接受阈值，异常用于表单内提示，不发请求。 */
export function pointConfigPayload(
  form: PointFormState,
  valueType = form.valueType,
): PointConfigInput {
  const sampleIntervalMs = period(form.sampleIntervalMs, '采样周期', 3600000)
  const staleAfterMs = period(form.staleAfterMs, '陈旧时间', 86400000)
  if (staleAfterMs < sampleIntervalMs) throw new Error('陈旧时间不能小于采样周期')
  const alarmLow = threshold(form.alarmLow),
    alarmHigh = threshold(form.alarmHigh)
  if (alarmLow !== null && alarmHigh !== null && alarmLow >= alarmHigh)
    throw new Error('低阈值必须小于高阈值')
  if (valueType !== 'NUMERIC' && (alarmLow !== null || alarmHigh !== null))
    throw new Error('文本和布尔测点不能设置数值阈值')
  return { sampleIntervalMs, staleAfterMs, enabled: form.enabled, alarmLow, alarmHigh }
}
/** 新增额外允许身份字段；文本/布尔必须使用STATE，方向说明为空转null。 */
export function pointCreatePayload(form: PointFormState): PointCreateInput {
  const config = pointConfigPayload(form)
  const code = form.code.trim(),
    name = form.name.trim(),
    unit = form.unit.trim()
  if (!/^[a-z][a-z0-9_]{0,63}$/.test(code))
    throw new Error('编码需小写字母开头，可含小写字母、数字和下划线，最多64位')
  if (!name || name.length > 100 || !unit || unit.length > 32)
    throw new Error('请填写名称（最多100字）和单位（最多32字）')
  if (
    !['NUMERIC', 'TEXT', 'BOOLEAN'].includes(form.valueType) ||
    !['INSTANT', 'COUNTER', 'STATE'].includes(form.aggregationType)
  )
    throw new Error('数据类型或聚合类型无效')
  if (form.valueType !== 'NUMERIC' && form.aggregationType !== 'STATE')
    throw new Error('文本和布尔测点必须使用STATE状态类型')
  const directionConvention = form.directionConvention.trim() || null
  if (directionConvention && directionConvention.length > 300) throw new Error('方向说明最多300字')
  return {
    ...config,
    code,
    name,
    unit,
    valueType: form.valueType,
    aggregationType: form.aggregationType,
    directionConvention,
  }
}

/** 快捷项只填表，不写数据库或假定现场阈值；累计量必须COUNTER，布尔值为0/1。 */
export const pointPresets = [
  {
    code: 'active_power',
    name: '有功功率',
    unit: 'kW',
    valueType: 'NUMERIC',
    aggregationType: 'INSTANT',
  },
  {
    code: 'total_energy',
    name: '累计电量',
    unit: 'kWh',
    valueType: 'NUMERIC',
    aggregationType: 'COUNTER',
  },
  {
    code: 'temperature',
    name: '设备温度',
    unit: '°C',
    valueType: 'NUMERIC',
    aggregationType: 'INSTANT',
  },
  { code: 'soc', name: '荷电状态', unit: '%', valueType: 'NUMERIC', aggregationType: 'INSTANT' },
  {
    code: 'online',
    name: '在线状态',
    unit: 'BOOL',
    valueType: 'BOOLEAN',
    aggregationType: 'STATE',
  },
] as const
