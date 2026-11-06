<template>
  <details v-if="auth.user" ref="menu" class="account-menu">
    <summary class="account-name" :title="auth.user.username">
      {{ auth.user.username }}
    </summary>
    <div class="account-menu-panel">
      <span>{{ auth.user.username }}</span>
      <RouterLink v-if="auth.can('user:manage') && auth.can('system:read')" to="/admin/users"
        >账号管理</RouterLink
      >
      <RouterLink v-if="auth.can('site:read')" to="/admin/assets">站点与设备台账</RouterLink>
      <RouterLink v-if="auth.can('site:read')" to="/admin/site-relations"
        >站内区域与高速关联</RouterLink
      >
      <RouterLink
        v-if="auth.can('site:read') && auth.can('device:read') && auth.can('monitor:read')"
        to="/admin/points"
        >设备测点管理</RouterLink
      >
      <RouterLink v-if="auth.can('site:read') && auth.can('twin:read')" to="/admin/scenes"
        >三维场景配置</RouterLink
      >
      <button type="button" @click="logout">退出</button>
    </div>
  </details>
</template>
<script setup lang="ts">
/** 地图页与三维页共用身份入口：显示实际登录用户名，退出后清空会话并回到登录页。 */
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const menu = ref<HTMLDetailsElement>()
watch(
  () => route.fullPath,
  () => {
    if (menu.value) menu.value.open = false
  },
)
async function logout() {
  auth.logout()
  await router.replace('/login')
}
</script>
