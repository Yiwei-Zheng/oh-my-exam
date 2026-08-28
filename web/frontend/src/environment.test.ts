import { describe, expect, it } from 'vitest'

import { i18n } from './i18n'
import { router } from './router'

describe('frontend environment', () => {
  it('registers both supported locales', () => {
    expect(i18n.global.availableLocales).toEqual(['en', 'zh-CN'])
  })

  it('does not define product routes before the website is designed', () => {
    expect(router.getRoutes()).toEqual([])
  })
})
