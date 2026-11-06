import { reactive } from 'vue'
import { defineStore } from 'pinia'

interface DirectoryState {
  query: string
  type: string
  highway: string
  selectedId: string
  facilityId: string
  tab: 'models' | 'public'
  limit: number
}

/** 各市与全省独立保存条件；进入三维、切换配对站点后仍能返回原检索。 */
export const useDirectoryStore = defineStore('directory', () => {
  const scopes = reactive<Record<string, DirectoryState>>({})
  function scope(key: string): DirectoryState {
    return (scopes[key] ??= {
      query: '',
      type: '',
      highway: '',
      selectedId: '',
      facilityId: '',
      tab: 'models',
      limit: 40,
    })
  }
  /** 退出或切换授权后丢弃旧检索，不跨账号复用选中的站点。 */
  function reset() {
    for (const key of Object.keys(scopes)) delete scopes[key]
  }
  return { scope, reset }
})
