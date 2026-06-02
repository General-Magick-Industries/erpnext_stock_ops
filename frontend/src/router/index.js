import { createRouter, createWebHashHistory } from 'vue-router'
import { useApp } from '../stores/app'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/', name: 'home', component: () => import('../views/HomeView.vue'), meta: { tab: 'home' } },
  { path: '/docs', name: 'docs', component: () => import('../views/DocListView.vue'), meta: { tab: 'docs' } },
  { path: '/create', name: 'create', component: () => import('../views/CreateView.vue'), meta: { tab: 'create' } },
  { path: '/sync', name: 'sync', component: () => import('../views/SyncView.vue'), meta: { tab: 'settings' } },
  { path: '/settings', name: 'settings', component: () => import('../views/SettingsView.vue'), meta: { tab: 'settings' } },
  { path: '/reports', name: 'reports', component: () => import('../views/ReportsView.vue'), meta: { tab: 'settings' } },
  { path: '/balance', name: 'balance', component: () => import('../views/StockBalanceView.vue'), meta: { tab: 'home' } },
  { path: '/movement', name: 'movement', component: () => import('../views/StockMovementView.vue'), meta: { tab: 'home' } },
  { path: '/lookup', name: 'lookup', component: () => import('../views/ItemLookupView.vue'), meta: { tab: 'home' } },
  { path: '/item/:code', name: 'item', component: () => import('../views/ItemDetailView.vue'), meta: { tab: 'home' } },
  { path: '/low', name: 'low', component: () => import('../views/LowStockView.vue'), meta: { tab: 'home' } },
  { path: '/quick-transfer', name: 'quick-transfer', component: () => import('../views/QuickTransferView.vue'), meta: { tab: 'home' } },
  { path: '/opname', name: 'opname', component: () => import('../views/OpnameView.vue'), meta: { tab: 'home' } },
  { path: '/form/:type', name: 'form', component: () => import('../views/DocFormView.vue') },
  { path: '/doc/:localId', name: 'detail', component: () => import('../views/DocDetailView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

router.beforeEach((to) => {
  const app = useApp()
  if (!to.meta.public && !app.isLoggedIn) return { name: 'login' }
  if (to.name === 'login' && app.isLoggedIn) return { name: 'home' }
})

export default router
