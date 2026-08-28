import { nextTick } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../features/home/HomeView.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('../features/not-found/NotFoundView.vue'),
    },
  ],
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
