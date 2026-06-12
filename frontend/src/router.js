import { createRouter, createWebHistory } from 'vue-router'
import MarketingHomePage from './pages/MarketingHomePage.vue'
import SolutionPage from './pages/SolutionPage.vue'
import SecurityPage from './pages/SecurityPage.vue'
import CasesPage from './pages/CasesPage.vue'
import PricingPage from './pages/PricingPage.vue'
import DashboardPage from './pages/DashboardPage.vue'
import KnowledgeBasePage from './pages/KnowledgeBasePage.vue'
import HistoryPage from './pages/HistoryPage.vue'
import StatisticsPage from './pages/StatisticsPage.vue'
import SettingsPage from './pages/SettingsPage.vue'
import LoginPage from './pages/LoginPage.vue'
import { useAuth } from './composables/useAuth.js'

const publicPaths = ['/', '/login', '/solution', '/security', '/cases', '/pricing']

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: MarketingHomePage },
    { path: '/solution', component: SolutionPage },
    { path: '/security', component: SecurityPage },
    { path: '/cases', component: CasesPage },
    { path: '/pricing', component: PricingPage },
    { path: '/login', component: LoginPage },
    { path: '/dashboard', component: DashboardPage },
    { path: '/knowledge-base', component: KnowledgeBasePage },
    { path: '/history', component: HistoryPage },
    { path: '/statistics', component: StatisticsPage },
    { path: '/settings', component: SettingsPage },
  ],
})

router.beforeEach((to) => {
  const { isLoggedIn } = useAuth()
  const path = to.path.replace(/\.html$/, '')
  if (!publicPaths.includes(path) && !isLoggedIn()) {
    return '/login'
  }
})

export default router
