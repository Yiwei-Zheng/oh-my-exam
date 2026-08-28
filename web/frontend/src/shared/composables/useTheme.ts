import { computed, onBeforeUnmount, onMounted, readonly, ref } from 'vue'

export const THEME_STORAGE_KEY = 'oh-my-exam.theme'

export type Theme = 'light' | 'dark'
export interface ThemeTransitionOrigin {
  x: number
  y: number
}

interface ViewTransition {
  ready: Promise<void>
  finished: Promise<void>
  skipTransition?: () => void
}

type ViewTransitionDocument = Document & {
  startViewTransition?: (callback: () => void) => ViewTransition
}

type PseudoElementAnimationOptions = KeyframeAnimationOptions & {
  pseudoElement: string
}

const COLOR_SCHEME_QUERY = '(prefers-color-scheme: dark)'
const VIEW_TRANSITION_DURATION = 550

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

function prefersReducedMotion() {
  if (
    typeof window === 'undefined' ||
    typeof window.matchMedia !== 'function'
  ) {
    return false
  }

  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function normalizeOrigin(
  origin?: ThemeTransitionOrigin,
): ThemeTransitionOrigin {
  if (typeof window === 'undefined') {
    return { x: 0, y: 0 }
  }

  return {
    x: Math.min(
      Math.max(origin?.x ?? window.innerWidth / 2, 0),
      window.innerWidth,
    ),
    y: Math.min(
      Math.max(origin?.y ?? window.innerHeight / 2, 0),
      window.innerHeight,
    ),
  }
}

function createViewTransitionStyles() {
  const style = document.createElement('style')
  style.textContent = `
    ::view-transition-old(root),
    ::view-transition-new(root) {
      animation: none;
      mix-blend-mode: normal;
    }
    ::view-transition-old(root) { z-index: 1; }
    ::view-transition-new(root) { z-index: 2; }
  `
  document.head.append(style)
  return style
}

async function applyThemeWithTransition(
  nextTheme: Theme,
  origin?: ThemeTransitionOrigin,
) {
  if (typeof document === 'undefined') {
    applyTheme(nextTheme)
    return
  }

  const transitionDocument = document as ViewTransitionDocument

  if (!transitionDocument.startViewTransition || prefersReducedMotion()) {
    applyTheme(nextTheme)
    return
  }

  const transitionStyles = createViewTransitionStyles()
  let transition: ViewTransition

  try {
    transition = transitionDocument.startViewTransition(() =>
      applyTheme(nextTheme),
    )
  } catch {
    transitionStyles.remove()
    applyTheme(nextTheme)
    return
  }

  try {
    await transition.ready

    const { x, y } = normalizeOrigin(origin)
    const viewportWidth = typeof window === 'undefined' ? 0 : window.innerWidth
    const viewportHeight =
      typeof window === 'undefined' ? 0 : window.innerHeight
    const radius = Math.hypot(
      Math.max(x, viewportWidth - x),
      Math.max(y, viewportHeight - y),
    )

    const options: PseudoElementAnimationOptions = {
      duration: VIEW_TRANSITION_DURATION,
      easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
      fill: 'both',
      pseudoElement: '::view-transition-new(root)',
    }

    document.documentElement.animate(
      {
        clipPath: [
          `circle(0px at ${x}px ${y}px)`,
          `circle(${radius}px at ${x}px ${y}px)`,
        ],
      },
      options,
    )

    await transition.finished
  } catch {
    transition.skipTransition?.()
    applyTheme(nextTheme)
  } finally {
    transitionStyles.remove()
  }
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

  async function setTheme(nextTheme: Theme, origin?: ThemeTransitionOrigin) {
    hasManualPreference.value = true
    persistTheme(nextTheme)

    if (nextTheme === theme.value) {
      applyTheme(nextTheme)
      return
    }

    await applyThemeWithTransition(nextTheme, origin)
  }

  function toggleTheme(origin?: ThemeTransitionOrigin) {
    return setTheme(theme.value === 'dark' ? 'light' : 'dark', origin)
  }

  async function followSystemTheme(origin?: ThemeTransitionOrigin) {
    hasManualPreference.value = false
    removeStoredTheme()
    await applyThemeWithTransition(getSystemTheme(), origin)
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
