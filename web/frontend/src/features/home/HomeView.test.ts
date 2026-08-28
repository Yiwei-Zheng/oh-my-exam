/* eslint-disable vue/one-component-per-file, vue/require-default-prop */
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'

import HomeView from './HomeView.vue'

const HeaderStub = defineComponent({
  props: {
    showPause: Boolean,
    showReplay: Boolean,
  },
  template: '<div data-header></div>',
})

const BlackHoleStub = defineComponent({
  props: {
    stage: String,
    reducedMotion: Boolean,
  },
  template: '<div data-black-hole></div>',
})

const TypewriterStub = defineComponent({
  props: {
    paused: Boolean,
    reducedMotion: Boolean,
  },
  template: '<span data-typewriter></span>',
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.sessionStorage.clear()
})

describe('HomeView', () => {
  it('enters the static hero and hides motion controls when motion is reduced', async () => {
    const mediaQuery = {
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => mediaQuery),
    )

    const wrapper = mount(HomeView, {
      global: {
        plugins: [i18n],
        stubs: {
          CharacterBlackHole: BlackHoleStub,
          SiteHeader: HeaderStub,
          TypewriterHeadline: TypewriterStub,
        },
      },
    })
    await wrapper.vm.$nextTick()

    const header = wrapper.findComponent(HeaderStub)
    const blackHole = wrapper.findComponent(BlackHoleStub)
    const typewriter = wrapper.findComponent(TypewriterStub)

    expect(wrapper.find('.intro').exists()).toBe(false)
    expect(header.props('showPause')).toBe(false)
    expect(header.props('showReplay')).toBe(false)
    expect(blackHole.props('stage')).toBe('ready')
    expect(blackHole.props('reducedMotion')).toBe(true)
    expect(typewriter.props('paused')).toBe(true)
    expect(window.sessionStorage.getItem('oh-my-exam.intro-seen')).toBe('true')

    wrapper.unmount()
  })
})
