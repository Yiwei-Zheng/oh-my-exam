import { nextTick } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'

import { pinia } from '../stores'
import { useAuthStore } from '../stores/auth'

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/questions',
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../features/auth/LoginView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../features/admin/AdminView.vue'),
      meta: { requiresAuth: true, role: 'admin' },
    },
    {
      path: '/questions',
      name: 'questions',
      component: () => import('../features/questions/QuestionSearchView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('../features/not-found/NotFoundView.vue'),
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore(pinia)
  if (!auth.checked) await auth.fetchMe()
  if (to.meta.requiresAuth && !auth.user) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.role && auth.user?.role !== to.meta.role) return { name: 'login' }
  if (to.meta.guestOnly && auth.user)
    return { name: auth.user.role === 'admin' ? 'admin' : 'questions' }
})

router.afterEach((_to, from, failure) => {
  if (failure || !from.name) {
    return
  }

  void nextTick(() => {
    const main = document.querySelector<HTMLElement>('main[tabindex="-1"]')

    if (!main?.hasAttribute('inert')) {
      main?.focus({ preventScroll: true })
    }
  })
})
