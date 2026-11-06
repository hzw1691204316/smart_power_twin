import { createRouter, createWebHistory } from 'vue-router'
import { registerAuthGuard } from './authGuard'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/forbidden',
      name: 'forbidden',
      component: () => import('@/views/ForbiddenView.vue'),
      meta: { title: '访问受限' },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '账号登录', public: true },
    },
    {
      path: '/admin/users',
      name: 'accounts',
      component: () => import('@/views/AccountsView.vue'),
      meta: { title: '账号与站点授权', permissions: ['system:read', 'user:manage'] },
    },
    {
      path: '/admin/assets',
      name: 'assets',
      component: () => import('@/views/AssetsView.vue'),
      meta: { title: '站点与设备台账', permissions: ['site:read'] },
    },
    { path: '/', redirect: '/overview' },
    {
      path: '/admin/site-relations',
      name: 'site-relations',
      component: () => import('@/views/SiteRelationsView.vue'),
      meta: { title: '站内区域与高速关联', permissions: ['site:read'] },
    },
    {
      path: '/admin/points',
      name: 'points',
      component: () => import('@/views/PointsView.vue'),
      meta: { title: '设备测点管理', permissions: ['site:read', 'device:read', 'monitor:read'] },
    },
    {
      path: '/admin/scenes',
      name: 'scenes',
      component: () => import('@/views/ScenesView.vue'),
      meta: { title: '三维场景配置', permissions: ['site:read', 'twin:read'] },
    },
    {
      path: '/overview',
      name: 'overview',
      component: () => import('@/views/OverviewView.vue'),
      meta: { title: '全国概览' },
    },
    {
      path: '/province/henan',
      name: 'henan',
      component: () => import('@/views/ProvinceView.vue'),
      meta: { title: '河南路网' },
    },
    {
      path: '/province/henan/cities/:cityCode',
      name: 'henan-city',
      component: () => import('@/views/ProvinceView.vue'),
      meta: { title: '地市高速路网' },
    },
    {
      path: '/sites/:siteId',
      name: 'site',
      component: () => import('@/views/SiteView.vue'),
      meta: { title: '站点孪生' },
    },
    {
      path: '/province/:provinceCode',
      name: 'province',
      component: () => import('@/views/ProvinceMapView.vue'),
      meta: { title: '省域地图' },
      beforeEnter: (to) => (to.params.provinceCode === '410000' ? { name: 'henan' } : undefined),
    },
    {
      path: '/templates/service-large',
      name: 'service-template',
      component: () => import('@/views/SiteView.vue'),
      meta: { title: '大型服务区模型' },
    },
    {
      path: '/facilities/:facilityId',
      name: 'facility',
      component: () => import('@/views/SiteView.vue'),
      meta: { title: '公开设施三维模板' },
    },
    {
      path: '/:pathMatch(.*)*',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { title: '页面未找到' },
    },
  ],
})

registerAuthGuard(router)

router.afterEach((to) => {
  document.title = `${String(to.meta.title ?? '工作台')} · 智慧电力数字孪生`
})

export default router
