import { createRouter, createWebHistory } from 'vue-router'
import MarketingHomePage from './pages/MarketingHomePage.vue'
import DashboardPage from './pages/DashboardPage.vue'
import InspectionDeskPage from './pages/InspectionDeskPage.vue'
import KnowledgeBasePage from './pages/KnowledgeBasePage.vue'
import HistoryPage from './pages/HistoryPage.vue'
import StatisticsPage from './pages/StatisticsPage.vue'
import SettingsPage from './pages/SettingsPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: MarketingHomePage },
    { path: '/dashboard', component: DashboardPage },
    { path: '/inspection-desk', component: InspectionDeskPage },
    { path: '/knowledge-base', component: KnowledgeBasePage },
    { path: '/history', component: HistoryPage },
    { path: '/statistics', component: StatisticsPage },
    { path: '/settings', component: SettingsPage },
  ],
})

export default router
