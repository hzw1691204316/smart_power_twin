/** 读数及曲线展示规则。数值0是有效值，缺失/BAD不能补0；历史陈旧值不称实时。 */
import type { HistoryItem, LatestReading } from '../types/monitoring'

export function readingValue(reading: LatestReading): string {
  if (!reading.sampledAt || reading.quality === 'BAD') return '—'
  if (reading.valueType === 'TEXT') return reading.valueText ?? '—'
  if (reading.valueType === 'BOOLEAN')
    return reading.valueNumeric === 1 ? '在线' : reading.valueNumeric === 0 ? '离线' : '—'
  return reading.valueNumeric === null
    ? '—'
    : reading.valueNumeric.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

/** 原始点按真实时间绘图；同时间取最大源序号；BAD/缺测间隔断线，避免跨缺口连成正常曲线。 */
export function historyPlot(items: HistoryItem[], intervalMs: number) {
  const byTime = new Map<string, HistoryItem>()
  for (const item of items) {
    const old = byTime.get(item.sampledAt)
    if (!old || BigInt(item.sourceSequence ?? '0') >= BigInt(old.sourceSequence ?? '0'))
      byTime.set(item.sampledAt, item)
  }
  const rows = [...byTime.values()].sort(
    (a, b) => Date.parse(a.sampledAt) - Date.parse(b.sampledAt),
  )
  const valid = rows.filter(
    (r) => r.quality === 'GOOD' && r.valueNumeric !== null && Number.isFinite(r.valueNumeric),
  )
  if (!valid.length) return { paths: [] as string[], min: null, max: null, count: 0 }
  const min = Math.min(...valid.map((r) => r.valueNumeric!))
  const max = Math.max(...valid.map((r) => r.valueNumeric!))
  const from = Date.parse(rows[0]!.sampledAt),
    to = Date.parse(rows.at(-1)!.sampledAt)
  const paths: string[] = []
  let points: string[] = [],
    previous: number | undefined
  const flush = () => {
    if (points.length) paths.push(points.join(' '))
    points = []
  }
  for (const row of rows) {
    const time = Date.parse(row.sampledAt)
    if (previous !== undefined && time - previous > intervalMs * 1.5) flush()
    if (row.quality !== 'GOOD' || row.valueNumeric === null || !Number.isFinite(row.valueNumeric)) {
      flush()
      previous = time
      continue
    }
    const x = to === from ? 160 : 12 + (296 * (time - from)) / (to - from)
    const y = max === min ? 66 : 116 - (100 * (row.valueNumeric - min)) / (max - min)
    points.push(`${x.toFixed(2)},${y.toFixed(2)}`)
    previous = time
  }
  flush()
  return { paths, min, max, count: valid.length }
}
