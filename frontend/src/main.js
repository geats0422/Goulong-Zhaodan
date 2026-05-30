import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './style.css'
import { applyThemeMode, getStoredThemeMode } from './theme'

applyThemeMode(getStoredThemeMode())

createApp(App).use(router).mount('#app')
