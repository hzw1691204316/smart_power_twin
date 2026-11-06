# CVue文件区块顺序说明

更新日期：2026-10-15

前端 `src` 下共29个 `.vue` 文件已统一按以下顺序组织：

```vue
<template>
  <!-- 页面结构 -->
</template>

<script setup lang="ts">
// 组件逻辑
</script>

<style scoped>
/* 如果组件有独立样式，放在最后 */
</style>
```

本次只移动已有区块，没有新增空的 `script` 或 `style`。现有集中样式继续放在 `src/styles`，不复制到每个组件。

已通过Vue解析器核对所有29个文件：模板、脚本、样式的内容及区块属性保持不变。完整 `npm.cmd run verify` 通过，包含类型检查、生产构建、地图布局与三维导航、登录跳转及刷新会话测试。本次无需修改或启动后端。

`eslint.config.ts` 新增 `vue/block-order` 规则，固定顺序为 `template`、`script`、`style`；以后新增组件也遵循，`npm.cmd run lint` 可检查并自动修正。

本轮是源码组织调整，没有进行浏览器视觉复测；已有本地预览权限限制保持不变。
