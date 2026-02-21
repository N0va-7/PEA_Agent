import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from './views/AppLayout.vue'
import HistoryView from './views/HistoryView.vue'
import LoginView from './views/LoginView.vue'
import OverviewView from './views/OverviewView.vue'
import TuningView from './views/TuningView.vue'
import UploadView from './views/UploadView.vue'
import { isAuthed } from './session'

const routes = [
  { path: '/', redirect: '/app/overview' },
  { path: '/login', name: 'login', component: LoginView },
  {
    path: '/app',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/app/overview' },
      { path: 'overview', name: 'overview', component: OverviewView },
      { path: 'upload', name: 'upload', component: UploadView },
      { path: 'history', name: 'history', component: HistoryView },
      { path: 'history/:analysisId', name: 'history-detail', component: HistoryView },
      { path: 'tuning', name: 'tuning', component: TuningView },
    ],
  },
  { path: '/dashboard', redirect: '/app/overview' },
  { path: '/analyses/:analysisId', redirect: (to) => `/app/history/${to.params.analysisId}` },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !isAuthed.value) {
    return '/login'
  }
  if (to.path === '/login' && isAuthed.value) {
    return '/app/overview'
  }
  return true
})

export default router
