<template>
  <main class="auth-page">
    <section class="auth-card" aria-labelledby="login-title">
      <div class="auth-symbol" aria-hidden="true">ϟ</div>
      <p class="auth-eyebrow">SMART POWER · DIGITAL TWIN</p>
      <h1 id="login-title">智慧电力 · 数字孪生</h1>
      <p class="auth-description">登录后进入地图工作台，查看授权站点与三维场景。</p>
      <button
        v-if="auth.canRestore"
        class="account-primary"
        type="button"
        :disabled="busy"
        @click="retrySession"
      >
        {{ busy ? '正在验证…' : '重新验证登录状态' }}
      </button>
      <form class="account-form" @submit.prevent="submit">
        <label for="login-username">账号</label>
        <input
          id="login-username"
          v-model="username"
          autocomplete="username"
          required
          maxlength="64"
          placeholder="请输入管理员开通的账号"
        />
        <label for="login-password">密码</label>
        <div class="password-input">
          <input
            id="login-password"
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="current-password"
            required
            maxlength="128"
          />
          <button type="button" :aria-pressed="showPassword" @click="showPassword = !showPassword">
            {{ showPassword ? '隐藏' : '显示' }}
          </button>
        </div>
        <p v-if="error || auth.notice" class="account-error" role="alert">
          {{ error || auth.notice }}
        </p>
        <button class="account-primary" type="submit" :disabled="busy">
          {{ busy ? '正在登录…' : '登录工作台' }}
        </button>
      </form>
      <p class="auth-description">
        账号由管理员开通。当前使用MySQL账号。密码可由管理员在数据库中修改。
      </p>
    </section>
  </main>
</template>

<script setup lang="ts">
/** 独立登录页：账号密码由用户输入，不展示或读取任何初始登录凭据。 */
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { health } from '@/services/authService'
import { safeRedirect } from '@/utils/authRedirect'
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const showPassword = ref(false)
const busy = ref(false)
const error = ref('')
onMounted(async () => {
  try {
    await health()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '无法连接后端'
  }
})
async function submit() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    if (!(await auth.signIn(username.value.trim(), password.value))) return
    await router.replace(safeRedirect(route.query.redirect))
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '登录失败，请重试'
  } finally {
    password.value = ''
    busy.value = false
  }
}
/** 已保存令牌但后端暂时离线时可重试核验，不要求再次输入密码。 */
async function retrySession() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    if (await auth.restoreSession(true)) await router.replace(safeRedirect(route.query.redirect))
  } finally {
    busy.value = false
  }
}
</script>
