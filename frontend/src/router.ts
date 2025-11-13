import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import HomePage from './pages/HomePage.vue'
import NotFound from './pages/NotFound.vue'
import { logger } from './lib/logger'

const CodeGeneratorApp = () => import('./modules/code-generator/CodeGeneratorApp.vue')
const CodeReviewApp = () => import('./modules/code-review/CodeReviewApp.vue')
const AboutPage = () => import('./modules/about/AboutMe.vue')
const FpfChatbotApp = () => import('./modules/FPF-chatbot/FpfChatbotApp.vue')
const ChemblAgentApp = () => import('./modules/chembl-agent/ChemblAgentApp.vue')

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: HomePage },
  { path: '/code-generator', name: 'code-generator', component: CodeGeneratorApp },
  { path: '/code-review', name: 'code-review', component: CodeReviewApp },
  { path: '/about', name: 'about', component: AboutPage },
  { path: '/fpf-chatbot', name: 'fpf-chatbot', component: FpfChatbotApp },
  { path: '/chembl-agent', name: 'chembl-agent', component: ChemblAgentApp },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFound }
]

export const router = createRouter({
  history: createWebHistory(),
  routes
})

// Add navigation logging
router.beforeEach((to, from) => {
  const fromPath = from.path || '(initial)'
  const toPath = to.path
  logger.navigation(fromPath, toPath)
})

// Log route load errors
router.onError((error) => {
  logger.error('ROUTER', 'Route loading failed', error)
})
