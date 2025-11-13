import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import './styles.css'
import { router } from './router'
import GlobalNotifierPlugin from './plugins/global-notifier'
import { logger } from './lib/logger'


const vuetify = createVuetify({
	components,
	directives,
	theme: {
		defaultTheme: 'customDark',
		themes: {
			customDark: {
				dark: true,
				colors: {
					background: '#0f1115',
						surface: '#111318',
						primary: '#9a5fff',
						secondary: '#38d6ee',
						accent: '#38d6ee',
						info: '#38d6ee',
						success: '#10b981',
						warning: '#f59e0b',
						error: '#ef4444',
						'on-background': '#e2e8f0',
						'on-surface': '#e2e8f0'
				}
			}
		}
	}
})

const pinia = createPinia()

// Log application startup
logger.info('APP', 'Application starting', {
	environment: import.meta.env.MODE,
	timestamp: new Date().toISOString()
})

// Global error handler
window.addEventListener('error', (event) => {
	logger.error('GLOBAL', 'Uncaught error', event.error, {
		message: event.message,
		filename: event.filename,
		lineno: event.lineno,
		colno: event.colno
	})
})

// Global unhandled promise rejection handler
window.addEventListener('unhandledrejection', (event) => {
	logger.error('GLOBAL', 'Unhandled promise rejection', event.reason)
})

createApp(App).use(router).use(pinia).use(vuetify).use(GlobalNotifierPlugin).mount('#app')

logger.info('APP', 'Application mounted successfully')
