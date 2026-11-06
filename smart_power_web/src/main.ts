import { createApp, nextTick, watch } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useAuthStore } from '@/stores/auth'
import { useSitesStore } from '@/stores/sites'
import { useDirectoryStore } from '@/stores/directory'
import './styles/global.css'
import './styles/map.css'
import './styles/twin-dashboard.css'
import './styles/ocean-theme.css'
import './styles/typography.css'
import './styles/map-workspace.css'
import './styles/auth.css'

const app = createApp(App)

app.use(createPinia())
const auth = useAuthStore()
// 换账号、授权变化或退出时清空旧站点缓存，避免把上个账号的页面状态带给下个账号。
watch(
  () => auth.scopeKey,
  () => {
    useSitesStore().reset()
    useDirectoryStore().reset()
    // 等signIn完成配置Bearer头，再加载新范围，避免仍使用旧账号请求。
    void nextTick(() => {
      if (auth.authenticated) void useSitesStore().load()
    })
  },
  { flush: 'sync' },
)
watch(
  () => auth.authenticated,
  (active, previous) => {
    if (!active && previous && router.currentRoute.value.name !== 'login')
      void router.replace({
        name: 'login',
        query: { redirect: router.currentRoute.value.fullPath },
      })
  },
)
app.use(router)

app.mount('#app')
