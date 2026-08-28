import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TypewriterHeadline from './TypewriterHeadline.vue'

const phrases = ['ANSWERING FASTER', 'THINKING CLEARER'] as const

afterEach(() => {
  vi.useRealTimers()
})

describe('TypewriterHeadline', () => {
  it('shows a stable complete phrase when motion is reduced', async () => {
    const wrapper = mount(TypewriterHeadline, {
      props: {
        phrases,
        paused: false,
        reducedMotion: true,
      },
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('ANSWERING FASTER')
    expect(wrapper.find('.typewriter--reduced').exists()).toBe(true)
  })

  it('does not advance while motion is paused', () => {
    vi.useFakeTimers()
    const wrapper = mount(TypewriterHeadline, {
      props: {
        phrases,
        paused: true,
        reducedMotion: false,
      },
    })

    vi.advanceTimersByTime(1200)

    expect(wrapper.text()).toBe('')
  })

  it('types the first phrase over time', async () => {
    vi.useFakeTimers()
    const wrapper = mount(TypewriterHeadline, {
      props: {
        phrases,
        paused: false,
        reducedMotion: false,
      },
    })

    vi.advanceTimersByTime(620)
    await wrapper.vm.$nextTick()

    expect(wrapper.text().length).toBeGreaterThan(0)
    expect('ANSWERING FASTER'.startsWith(wrapper.text())).toBe(true)
  })

  it('holds the underline stage when paused mid-transition', async () => {
    vi.useFakeTimers()
    const wrapper = mount(TypewriterHeadline, {
      props: {
        phrases: ['A'],
        paused: false,
        reducedMotion: false,
      },
    })

    vi.advanceTimersByTime(360)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.typewriter__cursor--underline').exists()).toBe(true)

    await wrapper.setProps({ paused: true })
    vi.advanceTimersByTime(600)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.typewriter__cursor--underline').exists()).toBe(true)

    await wrapper.setProps({ paused: false })
    vi.advanceTimersByTime(100)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.typewriter__cursor--holding').exists()).toBe(true)
  })
})
