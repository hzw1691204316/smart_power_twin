/** 单站告警状态。切站/换账号/撤权立即清空；列表、详情和写入迟到响应各自隔离。无后台轮询。 */
import { onUnmounted, ref, watch, type Ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import * as api from '@/services/alarmService'
import type { AlarmEvent, AlarmSeverity, AlarmStatus } from '@/types/alarms'

/** siteCode为授权站点业务编码；返回分页/筛选/详情/处置状态，不自行启动采集或轮询。 */
export function useAlarmEvents(siteCode: Ref<string>) {
  const auth = useAuthStore()
  const rows = ref<AlarmEvent[]>([]),
    total = ref(0),
    page = ref(1),
    hasNext = ref(false)
  const status = ref<AlarmStatus | ''>(''),
    severity = ref<AlarmSeverity | ''>('')
  const acknowledged = ref<'' | 'true' | 'false'>('')
  const loading = ref(false),
    error = ref(''),
    detail = ref<AlarmEvent>()
  const detailLoading = ref(false),
    detailError = ref(''),
    busy = ref(false),
    note = ref('')
  const feedback = ref('')
  let listGeneration = 0,
    detailGeneration = 0,
    contextGeneration = 0

  /** 每次刷新清旧页，失败保留错误而不是显示其他站点/旧账号的记录。 */
  async function load() {
    const current = ++listGeneration
    rows.value = []
    total.value = 0
    hasNext.value = false
    error.value = ''
    loading.value = false
    if (!siteCode.value) return
    if (!auth.can('alarm:read')) {
      error.value = '当前账号没有告警查看权限，请导入C06权限补丁后重新登录'
      return
    }
    loading.value = true
    try {
      const result = await api.getAlarms(siteCode.value, {
        page: page.value,
        status: status.value,
        severity: severity.value,
        acknowledged: acknowledged.value,
      })
      if (current !== listGeneration) return
      rows.value = result.data
      total.value = result.meta.total
      hasNext.value = result.meta.hasNext
    } catch (cause) {
      if (current === listGeneration)
        error.value = cause instanceof Error ? cause.message : '告警查询失败'
    } finally {
      if (current === listGeneration) loading.value = false
    }
  }

  /** 详情须从后端重读；不把列表旧快照直接当作当前可处置状态。 */
  async function open(id: string) {
    const current = ++detailGeneration
    const context = contextGeneration
    detail.value = undefined
    detailError.value = ''
    feedback.value = ''
    note.value = ''
    if (!auth.can('alarm:read')) return
    detailLoading.value = true
    try {
      const result = await api.getAlarm(id)
      if (current === detailGeneration && context === contextGeneration) {
        detail.value = result.data
        note.value = ''
      }
    } catch (cause) {
      if (current === detailGeneration && context === contextGeneration)
        detailError.value = cause instanceof Error ? cause.message : '详情查询失败'
    } finally {
      if (current === detailGeneration && context === contextGeneration) detailLoading.value = false
    }
  }

  /** 仅允许当前权限和状态对应的操作；后端仍检查权限、范围、只读开关及并发行锁。 */
  async function act(action: 'acknowledge' | 'close') {
    if (!detail.value || busy.value) return
    const allowed =
      action === 'acknowledge'
        ? auth.can('alarm:ack') && !detail.value.acknowledgedAt && detail.value.status !== 'CLOSED'
        : auth.can('alarm:close') &&
          detail.value.status === 'RECOVERED' &&
          !!detail.value.acknowledgedAt
    if (!allowed) return
    const context = contextGeneration,
      selected = detailGeneration
    const id = detail.value.id
    busy.value = true
    detailError.value = ''
    try {
      const result = await api.actOnAlarm(id, action, note.value)
      if (context !== contextGeneration) return
      if (selected === detailGeneration) {
        detail.value = result.data
        feedback.value = action === 'acknowledge' ? '已确认，确认不会代替恢复' : '事件已关闭'
        note.value = ''
      }
      await load()
    } catch (cause) {
      if (context === contextGeneration && selected === detailGeneration)
        detailError.value = cause instanceof Error ? cause.message : '处置失败，请刷新详情后重试'
    } finally {
      if (context === contextGeneration) busy.value = false
    }
  }

  /** 清理详情并作废旧详情请求，防止筛选或身份变化后显示旧事件。 */
  function clearDetail() {
    detailGeneration++
    detail.value = undefined
    detailLoading.value = false
    detailError.value = ''
    note.value = ''
    feedback.value = ''
  }
  watch([status, severity, acknowledged], () => {
    clearDetail()
    if (page.value !== 1) page.value = 1
    else void load()
  })
  watch(page, () => {
    clearDetail()
    void load()
  })
  watch(
    () => [
      siteCode.value,
      auth.scopeKey,
      auth.can('alarm:read'),
      auth.can('alarm:ack'),
      auth.can('alarm:close'),
    ],
    () => {
      contextGeneration++
      listGeneration++
      clearDetail()
      rows.value = []
      total.value = 0
      hasNext.value = false
      loading.value = false
      error.value = ''
      busy.value = false
      if (page.value !== 1) page.value = 1
      else void load()
    },
    { immediate: true, flush: 'sync' },
  )
  onUnmounted(() => {
    contextGeneration++
    listGeneration++
    detailGeneration++
  })
  return {
    rows,
    total,
    page,
    hasNext,
    status,
    severity,
    acknowledged,
    loading,
    error,
    detail,
    detailLoading,
    detailError,
    busy,
    note,
    feedback,
    load,
    open,
    act,
  }
}
