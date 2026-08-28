import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

export const LOCALE_STORAGE_KEY = 'oh-my-exam.locale'

export type SupportedLocale = 'en' | 'zh-CN'

let initialized = false

function isSupportedLocale(value: string | null): value is SupportedLocale {
  return value === 'en' || value === 'zh-CN'
}

function readStoredLocale(): SupportedLocale | null {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const storedLocale = window.localStorage.getItem(LOCALE_STORAGE_KEY)
    return isSupportedLocale(storedLocale) ? storedLocale : null
  } catch {
    return null
  }
}

function getBrowserLocale(): SupportedLocale {
  if (typeof navigator === 'undefined') {
    return 'en'
  }

  return navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en'
}

export function getInitialLocale(): SupportedLocale {
  return readStoredLocale() ?? getBrowserLocale()
}

function syncDocumentLanguage(locale: SupportedLocale) {
  if (typeof document !== 'undefined') {
    document.documentElement.lang = locale
  }
}

function persistLocale(locale: SupportedLocale) {
  if (typeof window === 'undefined') {
    return
  }

  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale)
  } catch {
    // A blocked storage backend must not prevent the locale switch.
  }
}

export function useLocale() {
  const { locale: i18nLocale } = useI18n({ useScope: 'global' })

  if (!initialized) {
    i18nLocale.value = getInitialLocale()
    initialized = true
  }

  syncDocumentLanguage(
    isSupportedLocale(i18nLocale.value) ? i18nLocale.value : 'en',
  )

  const locale = computed<SupportedLocale>(() =>
    isSupportedLocale(i18nLocale.value) ? i18nLocale.value : 'en',
  )
  const isChinese = computed(() => locale.value === 'zh-CN')

  function setLocale(nextLocale: SupportedLocale) {
    i18nLocale.value = nextLocale
    syncDocumentLanguage(nextLocale)
    persistLocale(nextLocale)
  }

  function toggleLocale() {
    setLocale(locale.value === 'en' ? 'zh-CN' : 'en')
  }

  return {
    locale,
    isChinese,
    setLocale,
    toggleLocale,
  }
}
