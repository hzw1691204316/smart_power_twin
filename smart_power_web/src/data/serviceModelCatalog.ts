/** 全系统服务区模型目录：SERVICE_L为双侧大型能源设施模板；不依赖城市或站点名称。
 * 对象键来自Blender导出的能源节点清单；status=unknown表示未接入采集，非故障或离线。
 */
import type { SceneDevice } from '../types/domain'
export const largeServiceModel = {
  code: 'SERVICE_L',
  scale: 'L' as const,
  modelUrl: '/models/service_large.glb',
  pvPanelCount: 154,
  description:
    '大型双侧服务区能源设施方案，依据总平面参考制作；位置、外观和设备配置待现场核验，尚未接入电力采集。',
}
const objects: Pick<SceneDevice, 'objectKey' | 'name' | 'category'>[] = [
  {
    objectKey: 'pv_roof_north_01',
    name: '上侧主楼屋顶光伏1',
    category: '光伏系统',
  },
  {
    objectKey: 'pv_roof_north_02',
    name: '上侧主楼屋顶光伏2',
    category: '光伏系统',
  },
  {
    objectKey: 'pv_roof_south_01',
    name: '下侧主楼屋顶光伏1',
    category: '光伏系统',
  },
  {
    objectKey: 'pv_roof_south_02',
    name: '下侧主楼屋顶光伏2',
    category: '光伏系统',
  },
  {
    objectKey: 'pv_roof_north_aux',
    name: '上侧辅助楼屋顶光伏',
    category: '光伏系统',
  },
  {
    objectKey: 'pv_roof_south_aux',
    name: '下侧辅助楼屋顶光伏',
    category: '光伏系统',
  },
  {
    objectKey: 'pv_canopy_north',
    name: '上侧充电雨棚平铺光伏',
    category: '光伏系统',
  },
  {
    objectKey: 'charger_north_01',
    name: '上侧直流充电桩01',
    category: '充电系统',
  },
  {
    objectKey: 'charger_north_02',
    name: '上侧直流充电桩02',
    category: '充电系统',
  },
  {
    objectKey: 'charger_north_03',
    name: '上侧直流充电桩03',
    category: '充电系统',
  },
  {
    objectKey: 'charger_north_04',
    name: '上侧直流充电桩04',
    category: '充电系统',
  },
  {
    objectKey: 'charger_north_05',
    name: '上侧直流充电桩05',
    category: '充电系统',
  },
  {
    objectKey: 'charger_north_06',
    name: '上侧直流充电桩06',
    category: '充电系统',
  },
  {
    objectKey: 'pv_canopy_south',
    name: '下侧充电雨棚平铺光伏',
    category: '光伏系统',
  },
  {
    objectKey: 'charger_south_01',
    name: '下侧直流充电桩01',
    category: '充电系统',
  },
  {
    objectKey: 'charger_south_02',
    name: '下侧直流充电桩02',
    category: '充电系统',
  },
  {
    objectKey: 'charger_south_03',
    name: '下侧直流充电桩03',
    category: '充电系统',
  },
  {
    objectKey: 'charger_south_04',
    name: '下侧直流充电桩04',
    category: '充电系统',
  },
  {
    objectKey: 'charger_south_05',
    name: '下侧直流充电桩05',
    category: '充电系统',
  },
  {
    objectKey: 'charger_south_06',
    name: '下侧直流充电桩06',
    category: '充电系统',
  },
  {
    objectKey: 'transformer_north_01',
    name: '上侧箱式变压器',
    category: '配电系统',
  },
  {
    objectKey: 'storage_north_01',
    name: '上侧储能一体柜',
    category: '储能系统',
  },
  {
    objectKey: 'storage_north_02',
    name: '上侧储能一体柜',
    category: '储能系统',
  },
  {
    objectKey: 'inverter_north_01',
    name: '上侧光伏逆变器',
    category: '光伏系统',
  },
  {
    objectKey: 'inverter_north_02',
    name: '上侧光伏逆变器',
    category: '光伏系统',
  },
  {
    objectKey: 'meter_north_01',
    name: '上侧并网计量及低压配电柜',
    category: '配电系统',
  },
  {
    objectKey: 'fire_cabinet_north',
    name: '上侧能源区消防器材柜',
    category: '辅助系统',
  },
  {
    objectKey: 'transformer_south_01',
    name: '下侧箱式变压器',
    category: '配电系统',
  },
  {
    objectKey: 'storage_south_01',
    name: '下侧储能一体柜',
    category: '储能系统',
  },
  {
    objectKey: 'storage_south_02',
    name: '下侧储能一体柜',
    category: '储能系统',
  },
  {
    objectKey: 'inverter_south_01',
    name: '下侧光伏逆变器',
    category: '光伏系统',
  },
  {
    objectKey: 'inverter_south_02',
    name: '下侧光伏逆变器',
    category: '光伏系统',
  },
  {
    objectKey: 'meter_south_01',
    name: '下侧并网计量及低压配电柜',
    category: '配电系统',
  },
  {
    objectKey: 'fire_cabinet_south',
    name: '下侧能源区消防器材柜',
    category: '辅助系统',
  },
]
/** sceneId为当前预览实例的稳定ID；据此构造独立交互ID，返回可定位的模型节点，不生成任何测点读数。 */
export function largeServiceModelDevices(sceneId: string): SceneDevice[] {
  return objects.map((object) => ({
    ...object,
    id: `${sceneId}-${object.objectKey}`,
    status: 'unknown',
  }))
}
