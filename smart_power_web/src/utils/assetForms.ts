/** 台账表单定义：字段标签、单位、空值与不可变身份在此集中；新增/编辑提交严格白名单。 */
import type { AssetBody, AssetDevice, AssetSite } from '../types/assets'
export interface AssetField {
  key: string
  label: string
  required?: boolean
  type?: 'number' | 'select'
  options?: [string, string][]
  max?: number
}
const status: [string, string][] = [
  ['ACTIVE', '有效'],
  ['INACTIVE', '停用'],
  ['RETIRED', '退役'],
]
const source: [string, string][] = [
  ['true', '模拟台账'],
  ['false', '现场资料（须核验）'],
]
export function assetFields(kind: 'site' | 'device', creating: boolean): AssetField[] {
  const identity: AssetField[] = creating
    ? [
        { key: 'code', label: '业务编码（创建后固定）', required: true, max: 64 },
        ...(kind === 'site'
          ? [
              {
                key: 'siteType',
                label: '站点类型',
                type: 'select' as const,
                options: [
                  ['SERVICE', '服务区'],
                  ['TOLL', '收费站'],
                ] as [string, string][],
              },
            ]
          : [
              { key: 'deviceType', label: '设备类型编码，如CHARGER', required: true, max: 32 },
              {
                key: 'systemType',
                label: '能源系统',
                type: 'select' as const,
                options: [
                  ['PV', '光伏'],
                  ['ESS', '储能'],
                  ['GRID', '配电'],
                  ['CHARGING', '充电'],
                  ['LOAD', '负荷'],
                  ['AUX', '辅助'],
                ] as [string, string][],
              },
            ]),
        { key: 'isDemo', label: '资料来源（创建后固定）', type: 'select', options: source },
      ]
    : []
  const common: AssetField[] = [
    { key: 'name', label: '名称', required: true, max: 150 },
    {
      key: 'assetStatus',
      label: '资产生命周期（不是在线状态）',
      type: 'select',
      options: kind === 'device' ? [...status, ['MAINTENANCE', '维护']] : status,
    },
  ]
  return [
    ...identity,
    ...common,
    ...(kind === 'site'
      ? [
          {
            key: 'scaleLevel',
            label: '场景规模（有场景后冻结）',
            type: 'select' as const,
            options: [
              ['S', '小型'],
              ['M', '中型'],
              ['L', '大型'],
            ] as [string, string][],
          },
          { key: 'provinceCode', label: '省级代码，如410000', required: true, max: 6 },
          { key: 'cityName', label: '地市名称，如郑州市', max: 100 },
          { key: 'longitude', label: 'WGS84经度（未知留空）', type: 'number' as const },
          { key: 'latitude', label: 'WGS84纬度（未知留空）', type: 'number' as const },
          { key: 'locationSource', label: '坐标来源 / 核验说明', max: 500 },
          { key: 'complexCode', label: '共同站区分组码（可空）', max: 64 },
          {
            key: 'primaryRouteId',
            label: '主路线（保留其他关系）',
            type: 'select' as const,
            options: [],
          },
        ]
      : [
          { key: 'areaId', label: '所属区域（可空）', type: 'select' as const, options: [] },
          { key: 'parentDeviceId', label: '父设备ID（本站，可空）', max: 20 },
          { key: 'ratedPowerKw', label: '额定功率 kW（可空）', type: 'number' as const },
          { key: 'ratedEnergyKwh', label: '额定储能电量 kWh（可空）', type: 'number' as const },
          { key: 'ratedCapacityKva', label: '额定视在容量 kVA（可空）', type: 'number' as const },
          { key: 'manufacturer', label: '厂家（可空）', max: 100 },
          { key: 'modelCode', label: '厂家型号（可空，非模型文件）', max: 100 },
        ]),
  ]
}
export function assetForm(
  kind: 'site' | 'device',
  record?: AssetSite | AssetDevice,
): Record<string, string> {
  const form: Record<string, string> = {
    assetStatus: 'ACTIVE',
    isDemo: 'true',
    siteType: 'SERVICE',
    scaleLevel: 'M',
    provinceCode: '410000',
    systemType: 'AUX',
  }
  for (const field of assetFields(kind, !record)) {
    const value = (record as unknown as Record<string, unknown>)?.[field.key]
    if (value !== undefined && value !== null) form[field.key] = String(value)
    else if (!(field.key in form)) form[field.key] = ''
  }
  if (kind === 'site' && record)
    form.primaryRouteId = (record as AssetSite).routes.find((r) => r.isPrimary)?.routeId ?? ''
  return form
}
/** 数值使用字符串提交让后端Decimal验证精度；空输入为null，不能用Number('')冒充0。 */
export function assetPayload(
  kind: 'site' | 'device',
  creating: boolean,
  form: Record<string, string>,
): AssetBody {
  return Object.fromEntries(
    assetFields(kind, creating).map((f) => [
      f.key,
      f.key === 'isDemo' ? form[f.key] === 'true' : form[f.key]?.trim() || null,
    ]),
  )
}
