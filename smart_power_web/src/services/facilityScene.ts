import type { Site, ScaleLevel } from '@/types/domain'
import type { PublicFacility } from '@/types/map'
import { largeServiceModel, largeServiceModelDevices } from '../data/serviceModelCatalog.ts'

/** 公开设施按所选模型规模选择模板；requestedScale只影响公开预览，不修改站点台账或发布场景。 */
export function createFacilityScene(
  facility: PublicFacility,
  template: Site,
  cityName = '河南省',
  requestedScale?: ScaleLevel,
): Site {
  if (template.type !== facility.type) throw new Error('设施与三维模板类型不匹配')
  const modelScale = requestedScale ?? facility.modelScale ?? template.scale
  const assigned = modelScale === 'L' && facility.type === 'SERVICE'
  return {
    ...template,
    id: facility.id,
    scale: assigned ? 'L' : template.scale,
    code: facility.id,
    name: facility.name,
    city: cityName,
    cityCode: facility.cityCode ?? undefined,
    complexCode: undefined,
    publicFacilityId: facility.id,
    highway: facility.ref || '路线待核验',
    direction: '方向待核验',
    longitude: facility.longitude,
    latitude: facility.latitude,
    modelUrl: assigned ? largeServiceModel.modelUrl : template.modelUrl,
    locationSource: 'OpenStreetMap公开参考位置',
    locationNote: assigned
      ? largeServiceModel.description
      : '当前为该公开设施的同类型通用模型预览，并非本站实景。布局、设备及读数来自演示模板；本站电力数据尚未接入。',
    // 指定模型只显示实际存在的节点，不继承朝歌模板四台设备和固定读数。
    publicModel: assigned
      ? {
          devices: largeServiceModelDevices(facility.id),
          pvPanelCount: largeServiceModel.pvPanelCount,
          description: largeServiceModel.description,
        }
      : undefined,
    powerKw: assigned ? 0 : template.powerKw,
    pvKw: assigned ? 0 : template.pvKw,
    dailyEnergyKwh: assigned ? 0 : template.dailyEnergyKwh,
    devices: assigned
      ? []
      : template.devices.map((device) => ({
          ...device,
          id: `${facility.id}-${device.id}`,
          description: '模板演示设备，尚未核验该公开设施的实际设备配置。',
        })),
  }
}
