<template>
  <section class="accounts-page" aria-labelledby="accounts-title">
    <div class="accounts-heading">
      <div>
        <p class="auth-eyebrow">IDENTITY & ACCESS</p>
        <h1 id="accounts-title">账号与站点授权</h1>
      </div>
      <RouterLink to="/overview">← 返回地图工作台</RouterLink>
    </div>
    <p class="account-hint">
      当前为MySQL模式：账号、授权和状态保存在数据库中；密码按当前学习配置明文保存。
      空授权表示不能访问任何站点。
    </p>
    <p v-if="error" class="account-error" role="alert">{{ error }}</p>
    <p v-if="message" class="account-success" role="status">{{ message }}</p>
    <p v-if="loading" role="status">正在读取账号资料…</p>
    <div class="accounts-grid">
      <section class="account-panel">
        <h2>开通账号</h2>
        <form class="account-form" @submit.prevent="create">
          <label for="new-username">登录账号</label>
          <input
            id="new-username"
            v-model="form.username"
            autocomplete="off"
            pattern="[A-Za-z0-9_.\-]{3,64}"
            required
            maxlength="64"
            placeholder="3—64位字母、数字及 _ . -"
          />
          <label for="new-name">显示名称</label>
          <input
            id="new-name"
            v-model="form.displayName"
            required
            maxlength="100"
            autocomplete="off"
          />
          <label for="new-password">初始密码</label>
          <input
            id="new-password"
            v-model="form.password"
            type="password"
            autocomplete="new-password"
            required
            minlength="10"
            maxlength="128"
            placeholder="至少10字符"
          />
          <label for="new-role">角色</label>
          <select id="new-role" v-model="form.roleId" required>
            <option v-for="role in assignableRoles" :key="role.id" :value="role.id">
              {{ role.name }}（{{ role.code }}）
            </option>
          </select>
          <fieldset>
            <legend>授权站点</legend>
            <label v-for="site in sites" :key="site.id" class="account-check"
              ><input v-model="form.siteIds" type="checkbox" :value="site.id" />{{
                site.name
              }}</label
            >
            <p v-if="!sites.length">当前账号没有可授予的站点。</p>
          </fieldset>
          <button type="submit" class="account-primary" :disabled="busy || loading || !form.roleId">
            {{ busy ? '正在提交…' : '创建账号' }}
          </button>
        </form>
      </section>
      <section class="account-panel account-list">
        <h2>
          账号列表 <small>{{ total }} 个</small>
        </h2>
        <div class="account-table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">账号 / 名称</th>
                <th scope="col">角色</th>
                <th scope="col">站点授权</th>
                <th scope="col">状态</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in accounts" :key="user.id">
                <td>
                  <strong>{{ user.displayName }}</strong
                  ><small>{{ user.username }}</small>
                </td>
                <td>{{ user.roleCode }}</td>
                <td>
                  {{
                    user.siteIds
                      .map((id) => sites.find((site) => site.id === id)?.name ?? id)
                      .join('、') || '无授权'
                  }}
                </td>
                <td>{{ { ACTIVE: '有效', LOCKED: '锁定', INACTIVE: '停用' }[user.status] }}</td>
                <td class="account-actions">
                  <button :disabled="busy || loading || !canMaintain(user)" @click="edit(user)">
                    授权</button
                  ><button
                    :disabled="busy || loading || user.id === auth.user?.id || !canMaintain(user)"
                    @click="changeStatus(user)"
                  >
                    {{ user.status === 'ACTIVE' ? '锁定' : '恢复' }}
                  </button>
                </td>
              </tr>
              <tr v-if="!accounts.length && !loading">
                <td colspan="5">当前范围内没有账号。</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="account-pagination">
          <button :disabled="page <= 1 || busy || loading" @click="turnPage(page - 1)">
            上一页</button
          ><span>第 {{ page }} 页</span
          ><button :disabled="page * 20 >= total || busy || loading" @click="turnPage(page + 1)">
            下一页
          </button>
        </div>
        <form v-if="editing" class="account-form scope-editor" @submit.prevent="saveScope">
          <h3>调整 {{ editing.displayName }} 的站点范围</h3>
          <fieldset>
            <legend>保存时完整替换；全部取消即撤销站点访问权限</legend>
            <label v-for="site in sites" :key="site.id" class="account-check"
              ><input v-model="selectedSites" type="checkbox" :value="site.id" />{{
                site.name
              }}</label
            >
          </fieldset>
          <div class="account-actions">
            <button type="submit" class="account-primary" :disabled="busy">保存授权</button
            ><button type="button" :disabled="busy" @click="editing = null">取消</button>
          </div>
        </form>
        <p class="account-hint">
          角色定义暂不可编辑；当前仅支持一个账号对应一个角色。不能锁定自己，也不能向他人授予超出自身范围的权限。
        </p>
      </section>
    </div>
  </section>
</template>
<script setup lang="ts">
/** 管理员工作页：账号开通、站点范围完整替换、锁定/恢复；暂不编辑角色定义或重置密码。 */
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import * as api from '@/services/authService'
import type { AccountInput, AssetOption, AuthUser, Role } from '@/types/auth'
const auth = useAuthStore()
const accounts = ref<AuthUser[]>([])
const roles = ref<Role[]>([])
const sites = ref<AssetOption[]>([])
const page = ref(1)
const total = ref(0)
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const message = ref('')
const editing = ref<AuthUser | null>(null)
const selectedSites = ref<string[]>([])
const form = ref<AccountInput>({
  username: '',
  displayName: '',
  password: '',
  roleId: '2',
  siteIds: [],
})
const assignableRoles = computed(() =>
  roles.value.filter((role) => role.permissions.every(auth.can)),
)
const canMaintain = (user: AuthUser) =>
  user.permissions.every(auth.can) && user.siteIds.every((id) => auth.user?.siteIds.includes(id))
function explain(cause: unknown) {
  return cause instanceof Error ? cause.message : '请求失败，请重试'
}
async function loadUsers() {
  const response = await api.users(page.value)
  accounts.value = response.data.items
  total.value = response.data.total
}
onMounted(async () => {
  loading.value = true
  try {
    const [roleResult, siteResult] = await Promise.all([api.roles(), api.authorizedSites()])
    roles.value = roleResult.data
    sites.value = siteResult
    form.value.roleId =
      assignableRoles.value.find((role) => role.code === 'VIEWER')?.id ??
      assignableRoles.value[0]?.id ??
      ''
    await loadUsers()
  } catch (cause) {
    error.value = explain(cause)
  } finally {
    loading.value = false
  }
})
/** 串行提交写操作；成功后重新读取列表，失败不伪造本地成功状态。 */
async function mutate(action: () => Promise<unknown>, success: string) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    await action()
    await loadUsers()
    message.value = success
  } catch (cause) {
    error.value = explain(cause)
  } finally {
    busy.value = false
  }
}
async function create() {
  await mutate(async () => {
    await api.createUser({ ...form.value, siteIds: [...form.value.siteIds] })
    form.value.username = ''
    form.value.displayName = ''
    form.value.siteIds = []
    page.value = 1
  }, '账号已开通。请通过你认可的安全方式交付初始密码。')
  form.value.password = ''
}
function edit(user: AuthUser) {
  editing.value = user
  selectedSites.value = [...user.siteIds]
  message.value = ''
}
async function saveScope() {
  const target = editing.value
  if (!target) return
  await mutate(async () => {
    await api.setSites(target.id, [...selectedSites.value])
    editing.value = null
    // 如果修改本人授权，立即更新当前身份与场景缓存。
    await auth.refreshIdentity()
  }, '站点授权已更新，下一次接口请求立即按新范围校验。')
}
async function changeStatus(user: AuthUser) {
  const status = user.status === 'ACTIVE' ? 'LOCKED' : 'ACTIVE'
  await mutate(
    () => api.setStatus(user.id, status),
    status === 'ACTIVE' ? '账号已恢复。' : '账号已锁定，已有令牌无法继续访问接口。',
  )
}
async function turnPage(next: number) {
  if (loading.value || busy.value) return
  loading.value = true
  const previous = page.value
  page.value = next
  try {
    await loadUsers()
  } catch (cause) {
    page.value = previous
    error.value = explain(cause)
  } finally {
    loading.value = false
  }
}
</script>
