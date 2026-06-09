import { createRouter, createWebHistory } from 'vue-router'
import MarketingHomePage from './pages/MarketingHomePage.vue'
import DashboardPage from './pages/DashboardPage.vue'
import KnowledgeBasePage from './pages/KnowledgeBasePage.vue'
import HistoryPage from './pages/HistoryPage.vue'
import StatisticsPage from './pages/StatisticsPage.vue'
import SettingsPage from './pages/SettingsPage.vue'
import LoginPage from './pages/LoginPage.vue'
import { useAuth } from './composables/useAuth.js'

const publicPaths = ['/', '/login']

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: MarketingHomePage },
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
  if (!publicPaths.includes(to.path) && !isLoggedIn()) {
    return '/login'
  }
})

export default router
