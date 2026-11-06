<template>
  <section class="accounts-page">
    <div class="account-panel">
      <p class="auth-eyebrow">ACCESS CONTROL</p>
      <h1>当前账号没有访问此页面的权限</h1>
      <p class="account-hint">如需管理账号，请联系管理员授予相应角色。已有站点权限不受影响。</p>
      <RouterLink to="/overview">返回地图工作台</RouterLink>
    </div>
  </section>
</template>
<script setup lang="ts">
/** 403页面：账号已登录但缺少页面动作权限，不误导用户反复登录。 */
</script>
