import { computed, onBeforeUnmount, onMounted, readonly, ref } from 'vue'

export const THEME_STORAGE_KEY = 'oh-my-exam.theme'

export type Theme = 'light' | 'dark'

const COLOR_SCHEME_QUERY = '(prefers-color-scheme: dark)'
const theme = ref<Theme>('light')
const hasManualPreference = ref(false)

let mediaQuery: MediaQueryList | null = null
let subscriberCount = 0

function isTheme(value: string | null): value is Theme {
  return value === 'light' || value === 'dark'
}

function getColorSchemeQuery(): MediaQueryList | null {
  if (
    typeof window === 'undefined' ||
    typeof window.matchMedia !== 'function'
  ) {
    return null
  }

  return window.matchMedia(COLOR_SCHEME_QUERY)
}

function getSystemTheme(): Theme {
  return getColorSchemeQuery()?.matches ? 'dark' : 'light'
}

function readStoredTheme(): Theme | null {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)
    return isTheme(storedTheme) ? storedTheme : null
  } catch {
    return null
  }
}

function persistTheme(nextTheme: Theme) {
  if (typeof window === 'undefined') {
    return
  }

  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme)
  } catch {
    // A blocked storage backend must not prevent the theme switch.
  }
}

function removeStoredTheme() {
  if (typeof window === 'undefined') {
    return
  }

  try {
    window.localStorage.removeItem(THEME_STORAGE_KEY)
  } catch {
    // The in-memory preference can still follow the system theme.
  }
}

function applyTheme(nextTheme: Theme) {
  theme.value = nextTheme

  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = nextTheme
    document.documentElement.style.colorScheme = nextTheme
  }
}

function initializeTheme() {
  if (typeof document === 'undefined') {
    return
  }

  const storedTheme = readStoredTheme()
  const documentTheme = document.documentElement.dataset.theme

  hasManualPreference.value = storedTheme !== null
  applyTheme(
    storedTheme ??
      (isTheme(documentTheme ?? null) ? documentTheme : getSystemTheme()),
  )
}

function handleSystemThemeChange(event: MediaQueryListEvent) {
  if (!hasManualPreference.value) {
    applyTheme(event.matches ? 'dark' : 'light')
  }
}

function subscribeToSystemTheme() {
  subscriberCount += 1

  if (subscriberCount > 1) {
    return
  }

  mediaQuery = getColorSchemeQuery()

  if (typeof mediaQuery?.addEventListener === 'function') {
    mediaQuery.addEventListener('change', handleSystemThemeChange)
  } else {
    mediaQuery?.addListener?.(handleSystemThemeChange)
  }
}

function unsubscribeFromSystemTheme() {
  subscriberCount = Math.max(0, subscriberCount - 1)

  if (subscriberCount === 0) {
    if (typeof mediaQuery?.removeEventListener === 'function') {
      mediaQuery.removeEventListener('change', handleSystemThemeChange)
    } else {
      mediaQuery?.removeListener?.(handleSystemThemeChange)
    }

    mediaQuery = null
  }
}

initializeTheme()

export function useTheme() {
  onMounted(() => {
    initializeTheme()
    subscribeToSystemTheme()
  })
  onBeforeUnmount(unsubscribeFromSystemTheme)

  const isDark = computed(() => theme.value === 'dark')

  function setTheme(nextTheme: Theme) {
    hasManualPreference.value = true
    persistTheme(nextTheme)
    applyTheme(nextTheme)
  }

  function toggleTheme() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  function followSystemTheme() {
    hasManualPreference.value = false
    removeStoredTheme()
    applyTheme(getSystemTheme())
  }

  return {
    theme: readonly(theme),
    isDark,
    hasManualPreference: readonly(hasManualPreference),
    setTheme,
    toggleTheme,
    followSystemTheme,
  }
}
