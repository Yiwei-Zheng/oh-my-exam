import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'

import SiteHeader from './SiteHeader.vue'

afterEach(() => {
  window.localStorage.clear()
  Reflect.deleteProperty(document, 'startViewTransition')
  vi.unstubAllGlobals()
})

function mountHeader() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })

  return mount(SiteHeader, { global: { plugins: [router, i18n] } })
}

describe('SiteHeader', () => {
  it('opens an accessible globe menu and selects a language', async () => {
    const wrapper = mountHeader()
    const trigger = wrapper.get('[aria-haspopup="menu"]')

    expect(trigger.text()).toBe('')
    await trigger.trigger('click')
    expect(wrapper.get('[role="menu"]').isVisible()).toBe(true)

    const english = wrapper
      .findAll<HTMLButtonElement>('[role="menuitemradio"]')
      .find((option) => option.text().includes('English'))
    expect(english).toBeDefined()
    await english!.trigger('click')

    expect(document.documentElement.lang).toBe('en')
    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('switches theme directly without requesting a document snapshot', async () => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false })))
    const startViewTransition = vi.fn()
    Object.defineProperty(document, 'startViewTransition', {
      configurable: true,
      value: startViewTransition,
    })
    const wrapper = mountHeader()
    const themeButton = wrapper.get('[aria-label="Use dark theme"]')

    await themeButton.trigger('click')

    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(startViewTransition).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
