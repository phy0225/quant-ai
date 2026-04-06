import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('@/pages/DashboardPage.vue'), meta: { title: '资产总览' } },
  { path: '/lab', name: 'Lab', component: () => import('@/pages/LabPage.vue'), meta: { title: 'AI实验室' } },
  { path: '/analyze', name: 'Analyze', component: () => import('@/pages/AnalyzePage.vue'), meta: { title: '决策触发' } },
  { path: '/decisions', name: 'DecisionList', component: () => import('@/pages/DecisionListPage.vue'), meta: { title: '决策列表' } },
  { path: '/decisions/:id', name: 'DecisionDetail', component: () => import('@/pages/DecisionDetailPage.vue'), meta: { title: '决策详情' } },
  { path: '/approvals', name: 'ApprovalList', component: () => import('@/pages/ApprovalListPage.vue'), meta: { title: '审批中心' } },
  { path: '/approvals/:id', name: 'ApprovalDetail', component: () => import('@/pages/ApprovalDetailPage.vue'), meta: { title: '审批详情' } },
  { path: '/portfolio', name: 'Portfolio', component: () => import('@/pages/PortfolioPage.vue'), meta: { title: '持仓管理' } },
  { path: '/factors', name: 'Factors', component: () => import('@/pages/FactorsPage.vue'), meta: { title: '因子研究' } },
  { path: '/strategy', name: 'Strategy', component: () => import('@/pages/StrategyPage.vue'), meta: { title: '策略开发' } },
  { path: '/rules', name: 'Rules', component: () => import('@/pages/RulesPage.vue'), meta: { title: '规则配置' } },
  { path: '/graph', name: 'Graph', component: () => import('@/pages/GraphPage.vue'), meta: { title: '经验图谱' } },
  { path: '/backtest', name: 'Backtest', component: () => import('@/pages/BacktestPage.vue'), meta: { title: '回测分析' } },
  { path: '/weights', name: 'Weights', component: () => import('@/pages/WeightManagementPage.vue'), meta: { title: '权重管理' } },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.afterEach((to) => {
  const title = to.meta?.title as string | undefined
  document.title = title ? `${title} - Quant AI` : 'Quant AI'
})

export default router
