import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './style.css'
import { initializeTheme } from './composables/useTheme.js'

initializeTheme()
createApp(App).use(router).mount('#app')
