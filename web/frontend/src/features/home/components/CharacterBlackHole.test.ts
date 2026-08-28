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
  it('moves text offsets along fixed paths', () => {
    const wrapper = mount(CharacterBlackHole, { props: baseProps })

    expect(wrapper.findAll('animate[attributeName="startOffset"]')).toHaveLength(5)
    expect(wrapper.findAll('.black-hole__stream')).toHaveLength(5)
  })

  it('renders a static version for reduced motion', () => {
    const wrapper = mount(CharacterBlackHole, {
      props: { ...baseProps, reducedMotion: true },
    })

    expect(wrapper.find('animate').exists()).toBe(false)
  })
})
