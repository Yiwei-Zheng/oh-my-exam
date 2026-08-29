import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'

import SiteHeader from './SiteHeader.vue'

interface AnimationStub {
  playbackRate: number
  onfinish: (() => void) | null
  cancel: ReturnType<typeof vi.fn>
  reverse: ReturnType<typeof vi.fn>
}

let animations: AnimationStub[]

beforeEach(() => {
  animations = []
  document.documentElement.dataset.theme = 'light'
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: false })),
  )
  Object.defineProperty(Element.prototype, 'animate', {
    configurable: true,
    value: vi.fn(() => {
      const animation: AnimationStub = {
        playbackRate: 1,
        onfinish: null,
        cancel: vi.fn(),
        reverse: vi.fn(() => {
          animation.playbackRate *= -1
        }),
      }
      animations.push(animation)
      return animation as unknown as Animation
    }),
  })
})

afterEach(() => {
  window.localStorage.clear()
  Reflect.deleteProperty(document, 'startViewTransition')
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  Reflect.deleteProperty(Element.prototype, 'animate')
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

  it('reveals the next theme without requesting a document snapshot', async () => {
    const startViewTransition = vi.fn()
    Object.defineProperty(document, 'startViewTransition', {
      configurable: true,
      value: startViewTransition,
    })
    const wrapper = mountHeader()
    const themeButton = wrapper.get('[aria-label="Use dark theme"]')

    await themeButton.trigger('click')

    expect(document.documentElement.dataset.theme).toBe('light')
    expect(animations).toHaveLength(1)
    animations[0]?.onfinish?.()
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(animations).toHaveLength(2)
    animations[1]?.onfinish?.()
    expect(startViewTransition).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('reverses an in-flight theme reveal when toggled again', async () => {
    const wrapper = mountHeader()
    const initialTheme = document.documentElement.dataset.theme
    const themeButton = wrapper
      .findAll('button')
      .find((button) => button.attributes('aria-label')?.includes('theme'))

    expect(themeButton).toBeDefined()

    await themeButton!.trigger('click')
    await themeButton!.trigger('click')

    expect(animations[0]?.reverse).toHaveBeenCalledOnce()
    animations[0]?.onfinish?.()
    expect(document.documentElement.dataset.theme).toBe(initialTheme)
    expect(animations).toHaveLength(1)
    wrapper.unmount()
  })
})
