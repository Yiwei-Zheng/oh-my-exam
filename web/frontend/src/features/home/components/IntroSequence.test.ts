import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import IntroSequence from './IntroSequence.vue'
import { i18n } from '../../../i18n'

afterEach(() => {
  vi.useRealTimers()
})

describe('IntroSequence', () => {
  it('can be skipped immediately', async () => {
    vi.useFakeTimers()
    const wrapper = mount(IntroSequence, {
      props: { targetId: 'missing-target' },
      global: { plugins: [i18n] },
      attachTo: document.body,
    })

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('formation')).toHaveLength(1)
    expect(wrapper.emitted('complete')).toHaveLength(1)
    wrapper.unmount()
  })

  it('supports Escape as a skip shortcut', async () => {
    vi.useFakeTimers()
    const wrapper = mount(IntroSequence, {
      props: { targetId: 'missing-target' },
      global: { plugins: [i18n] },
    })

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('complete')).toHaveLength(1)
    wrapper.unmount()
  })
})
