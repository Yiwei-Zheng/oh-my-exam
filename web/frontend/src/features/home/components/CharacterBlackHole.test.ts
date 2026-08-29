import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import CharacterBlackHole from './CharacterBlackHole.vue'

const baseProps = {
  stage: 'ready' as const,
  paused: false,
  reducedMotion: false,
  label: 'Academic black hole',
}

describe('CharacterBlackHole', () => {
  it('provides sixteen static character streams while GPU rendering loads', () => {
    const wrapper = mount(CharacterBlackHole, { props: baseProps })

    expect(wrapper.attributes('data-renderer')).toBe('svg')
    expect(wrapper.findAll('.black-hole__fallback-text')).toHaveLength(16)
  })

  it('renders a static version for reduced motion', () => {
    const wrapper = mount(CharacterBlackHole, {
      props: { ...baseProps, reducedMotion: true },
    })

    expect(wrapper.attributes('data-renderer')).toBe('svg')
    expect(wrapper.classes()).toContain('black-hole--reduced')
  })
})
