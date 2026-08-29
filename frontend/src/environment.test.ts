import { describe, expect, it } from 'vitest'

import { i18n } from './i18n'
import { router } from './router'

describe('frontend environment', () => {
  it('registers both supported locales', () => {
    expect(i18n.global.availableLocales).toEqual(['en', 'zh-CN'])
  })

  it('registers the authentication, admin, and not-found routes', () => {
    expect(
      router.getRoutes().map(({ name, path }) => ({
        name,
        path,
      })),
    ).toEqual(
      expect.arrayContaining([
        { name: 'login', path: '/login' },
        { name: 'admin', path: '/admin' },
        { name: 'not-found', path: '/:pathMatch(.*)*' },
      ]),
    )
    expect(router.getRoutes()).toHaveLength(4)
  })
})
