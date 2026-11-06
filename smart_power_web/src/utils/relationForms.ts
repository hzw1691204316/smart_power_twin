/** 区域/路线关联表单白名单；桩号以米制十进制字符串提交，避免0被空值替代。 */
import type { AssetArea, AssetBody, AssetRoute } from '@/types/assets'
export type RelationKind = 'area' | 'link'
export type RelationRecord = AssetArea | AssetRoute
export type RelationFormState = Record<string, string | boolean>

/** kind区分区域和关联；record为空则创建，不让用户编辑既有编码。 */
export function relationForm(kind: RelationKind, record?: RelationRecord): RelationFormState {
  if (kind === 'area') {
    const row = record as AssetArea | undefined
    return {
      code: row?.code ?? '',
      name: row?.name ?? '',
      areaType: row?.areaType ?? 'POWER_ROOM',
      parentId: row?.parentId ?? '',
    }
  }
  const row = record as AssetRoute | undefined
  return {
    linkCode: row?.linkCode ?? '',
    routeId: row?.routeId ?? '',
    areaId: row?.areaId ?? '',
    directionCode: row?.directionCode ?? 'UNKNOWN',
    directionLabel: row?.directionLabel ?? '',
    chainageM: row?.chainageM == null ? '' : String(row.chainageM),
    accessType: row?.accessType ?? 'DIRECT',
    isPrimary: row?.isPrimary ?? false,
  }
}
/** 对象身份只在创建时提交；长度/编码和有限的枚举本地校验，服务端仍强制复核。 */
export function relationPayload(
  kind: RelationKind,
  creating: boolean,
  form: RelationFormState,
): AssetBody {
  const text = (key: string) => String(form[key] ?? '').trim()
  const id = (key: string) => {
    const value = text(key)
    if (value && !/^[1-9]\d{0,19}$/.test(value)) throw new Error('请选择有效的数据库ID')
    return value || null
  }
  if (kind === 'area') {
    if (!text('name') || text('name').length > 150) throw new Error('区域名称必填，最多150字')
    if (!/^[A-Z][A-Z0-9_]{0,31}$/.test(text('areaType')))
      throw new Error('区域类型须为大写字母开头的类型编码，最多32位')
    if (creating && !/^[A-Za-z0-9_-]{1,64}$/.test(text('code')))
      throw new Error('区域编码须为1—64位字母、数字、下划线或连字符')
    return {
      name: text('name'),
      areaType: text('areaType'),
      parentId: id('parentId'),
      ...(creating ? { code: text('code') } : {}),
    }
  }
  if (creating && !/^[A-Za-z0-9_-]{1,64}$/.test(text('linkCode')))
    throw new Error('关联编码须为1—64位字母、数字、下划线或连字符')
  if (!id('routeId')) throw new Error('请选择已有高速路线')
  if (
    !['UP', 'DOWN', 'BOTH', 'UNKNOWN'].includes(text('directionCode')) ||
    !['DIRECT', 'INTERCHANGE', 'OTHER'].includes(text('accessType'))
  )
    throw new Error('方向或接入类型无效')
  if (text('directionLabel').length > 100) throw new Error('方向说明最多100字')
  const chainage = text('chainageM')
  if (chainage && !/^(?:0|[1-9]\d{0,8})(?:\.\d{1,3})?$/.test(chainage))
    throw new Error('桩号请填米数，最多9位整数、3位小数；未知留空')
  return {
    routeId: id('routeId'),
    areaId: id('areaId'),
    directionCode: text('directionCode'),
    directionLabel: text('directionLabel') || null,
    chainageM: chainage || null,
    accessType: text('accessType'),
    isPrimary: form.isPrimary === true,
    ...(creating ? { linkCode: text('linkCode') } : {}),
  }
}
/** 排除自己及全部后代作为父选项，异常老数据的循环也会被seen终止；后端再次防环。 */
export function areaParents(areas: AssetArea[], id?: string) {
  const byId = new Map(areas.map((area) => [area.id, area]))
  return areas.filter((area) => {
    let cursor: AssetArea | undefined = area
    const seen = new Set<string>()
    while (cursor) {
      if (cursor.id === id || seen.has(cursor.id)) return false
      seen.add(cursor.id)
      cursor = cursor.parentId ? byId.get(cursor.parentId) : undefined
    }
    return true
  })
}
