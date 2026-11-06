/** GLB对象键选择规则：精确名称优先，否则取最长完整下划线前缀，不能把storage_01匹配到storage_010。 */
import type { TwinSceneData } from '../types/twin'
import type { SceneDevice } from '../types/domain'

export function matchSceneObject<T extends { objectKey: string }>(
  name: string,
  objects: T[],
): T | undefined {
  const key = name.replace(/[._]\d{3,}$/, '')
  return (
    objects.find((o) => o.objectKey === name) ??
    objects.find((o) => o.objectKey === key) ??
    [...objects]
      .sort((a, b) => b.objectKey.length - a.objectKey.length)
      .find((o) => key.startsWith(`${o.objectKey}_`))
  )
}
export function sceneModelUrl(url: string | null): string {
  if (!url || !/^\/models\/[A-Za-z0-9_-]+\.glb$/.test(url))
    throw new Error('场景没有合法的本地GLB资源，请检查模板和发布配置')
  return url
}
/** 只把数据库中有关联设备的对象放入交互目录，不以本地样例补出不存在的绑定或设备。 */
export function sceneDevices(scene: TwinSceneData): SceneDevice[] {
  const labels: Record<string, string> = {
    PV: '光伏系统',
    ESS: '储能系统',
    CHARGING: '充电系统',
    GRID: '配电系统',
    LOAD: '负荷系统',
    AUX: '辅助系统',
  }
  return scene.objects
    .filter((o) => o.device !== null)
    .map((o) => ({
      id: o.id,
      objectKey: o.objectKey,
      name: o.name,
      category: labels[o.device!.systemType] ?? '其他系统',
      status: 'unknown',
    }))
}
