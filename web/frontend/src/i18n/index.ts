import { createI18n } from 'vue-i18n'

import { getInitialLocale } from '../shared/composables/useLocale'

export const messages = {
  en: {
    controls: {
      switchLanguage: 'Switch language',
      useLightTheme: 'Use light theme',
      useDarkTheme: 'Use dark theme',
      replayIntro: 'Replay intro',
      pauseMotion: 'Pause motion',
      resumeMotion: 'Resume motion',
      skipIntro: 'Skip intro',
      skipToContent: 'Skip to main content',
    },
    home: {
      blackHoleAriaLabel:
        'A black hole formed from orbiting academic formulas, equations, symbols, and code.',
      accessibleHeadline:
        "OH, I'M answering faster, getting higher scores, learning deeper, and thinking clearer.",
    },
    notFound: {
      label: '404 / LOST IN THE VOID',
      title: 'This page crossed the event horizon.',
      description:
        'There is nothing at this address. Return home to keep exploring.',
      backHome: 'Return home',
    },
  },
  'zh-CN': {
    controls: {
      switchLanguage: '切换语言',
      useLightTheme: '使用浅色主题',
      useDarkTheme: '使用深色主题',
      replayIntro: '重播片头',
      pauseMotion: '暂停动画',
      resumeMotion: '继续动画',
      skipIntro: '跳过片头',
      skipToContent: '跳到主要内容',
    },
    home: {
      blackHoleAriaLabel: '由环绕运行的学术公式、方程、符号和代码构成的黑洞。',
      accessibleHeadline:
        "OH, I'M：更快作答、取得更高分、学得更深入、思考更清晰。",
    },
    notFound: {
      label: '404 / LOST IN THE VOID',
      title: '这个页面已越过事件视界。',
      description: '此地址没有可显示的内容。返回首页继续探索。',
      backHome: '返回首页',
    },
  },
} as const

export const i18n = createI18n({
  legacy: false,
  locale: getInitialLocale(),
  fallbackLocale: 'en',
  messages,
})
