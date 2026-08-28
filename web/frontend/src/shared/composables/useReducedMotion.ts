import { onBeforeUnmount, onMounted, readonly, ref } from 'vue'

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'

function getMediaQuery(): MediaQueryList | null {
  if (
    typeof window === 'undefined' ||
    typeof window.matchMedia !== 'function'
  ) {
    return null
  }

  return window.matchMedia(REDUCED_MOTION_QUERY)
}

export function useReducedMotion() {
  let mediaQuery = getMediaQuery()
  const prefersReducedMotion = ref(mediaQuery?.matches ?? false)

  const updatePreference = (event: MediaQueryListEvent) => {
    prefersReducedMotion.value = event.matches
  }

  onMounted(() => {
    mediaQuery = getMediaQuery()

    if (!mediaQuery) {
      return
    }

    prefersReducedMotion.value = mediaQuery.matches

    if (typeof mediaQuery.addEventListener === 'function') {
      mediaQuery.addEventListener('change', updatePreference)
    } else {
      mediaQuery.addListener?.(updatePreference)
    }
  })

  onBeforeUnmount(() => {
    if (typeof mediaQuery?.removeEventListener === 'function') {
      mediaQuery.removeEventListener('change', updatePreference)
    } else {
      mediaQuery?.removeListener?.(updatePreference)
    }
  })

  return {
    prefersReducedMotion: readonly(prefersReducedMotion),
  }
}
