import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/pages/DashboardPage.vue'),
    meta: { title: '总览仪表盘' },
  },
  {
    path: '/analyze',
    name: 'Analyze',
    component: () => import('@/pages/AnalyzePage.vue'),
    meta: { title: '触发分析' },
  },
  {
    path: '/decisions/:id',
    name: 'DecisionDetail',
    component: () => import('@/pages/DecisionDetailPage.vue'),
    meta: { title: '决策详情' },
  },
  {
    path: '/approvals',
    name: 'ApprovalList',
    component: () => import('@/pages/ApprovalListPage.vue'),
    meta: { title: '审批列表' },
  },
  {
    path: '/approvals/:id',
    name: 'ApprovalDetail',
    component: () => import('@/pages/ApprovalDetailPage.vue'),
    meta: { title: '审批详情' },
  },
  {
    path: '/rules',
    name: 'Rules',
    component: () => import('@/pages/RulesPage.vue'),
    meta: { title: '规则配置' },
  },
  {
    path: '/backtest',
    name: 'Backtest',
    component: () => import('@/pages/BacktestPage.vue'),
    meta: { title: '历史回测' },
  },
  {
    path: '/graph',
    name: 'Graph',
    component: () => import('@/pages/GraphPage.vue'),
    meta: { title: '经验图谱' },
  },
  {
    path: '/portfolio',
    name: 'Portfolio',
    component: () => import('@/pages/PortfolioPage.vue'),
    meta: { title: '持仓管理' },
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0, behavior: 'smooth' }
  },
})

router.afterEach((to) => {
  const title = to.meta?.title as string | undefined
  document.title = title ? `${title} - 投资组合管理系统` : '投资组合管理系统'
})

export default router