/** 地图取当前账号全部授权台账，身份/坐标/名称来自后端；旧演示路由ID继续保留。 */
import { demoSites } from '@/data/demo'
import type { Site } from '@/types/domain'
import { allAssetSites } from './assetsService'
import { assetSiteToMap } from '@/utils/assetSiteAdapter'
export async function getSites(): Promise<Site[]> {
  const rows = await allAssetSites()
  return rows
    .map((row) =>
      assetSiteToMap(
        row,
        demoSites.find((s) => s.code === row.code),
      ),
    )
    .filter((site): site is Site => site !== undefined)
}
