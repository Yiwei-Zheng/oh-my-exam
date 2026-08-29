<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { BRAND_NAME } from '@/i18n/invariantContent'
import { useLocale, type SupportedLocale } from '@/shared/composables/useLocale'
import { useTheme, type Theme } from '@/shared/composables/useTheme'

withDefaults(
  defineProps<{
    showReplay?: boolean
    hidden?: boolean
  }>(),
  { showReplay: true, hidden: false },
)

const emit = defineEmits<{ replay: [] }>()
const { t } = useI18n({ useScope: 'global' })
const { locale, setLocale } = useLocale()
const { theme, isDark, setTheme } = useTheme()
const localeMenuOpen = ref(false)
const localePicker = ref<HTMLElement>()
const localeTrigger = ref<HTMLButtonElement>()
const themeCurtain = ref<HTMLElement>()
let themeAnimation: Animation | undefined
let themeAnimationPhase: 'cover' | 'fade' | undefined

const themeLabel = computed(() =>
  isDark.value ? t('controls.useLightTheme') : t('controls.useDarkTheme'),
)

function toggleLocaleMenu() {
  localeMenuOpen.value = !localeMenuOpen.value
}

function chooseLocale(nextLocale: SupportedLocale) {
  setLocale(nextLocale)
  localeMenuOpen.value = false
  void nextTick(() => localeTrigger.value?.focus())
}

function focusFirstLocale() {
  void nextTick(() => {
    localePicker.value
      ?.querySelector<HTMLButtonElement>('[role="menuitemradio"]')
      ?.focus()
  })
}

function openLocaleMenuFromKeyboard() {
  localeMenuOpen.value = true
  focusFirstLocale()
}

function handleDocumentPointerDown(event: PointerEvent) {
  if (!localePicker.value?.contains(event.target as Node)) {
    localeMenuOpen.value = false
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && localeMenuOpen.value) {
    localeMenuOpen.value = false
    localeTrigger.value?.focus()
  }
}

function prefersReducedMotion() {
  return (
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  )
}

function resetThemeCurtain() {
  themeAnimation = undefined
  themeAnimationPhase = undefined
  themeCurtain.value?.removeAttribute('style')
}

function startThemeReveal(nextTheme: Theme, x: number, y: number) {
  const curtain = themeCurtain.value
  if (!curtain) {
    setTheme(nextTheme)
    return
  }

  const radius = Math.hypot(
    Math.max(x, window.innerWidth - x),
    Math.max(y, window.innerHeight - y),
  )
  const scale = Math.max((radius * 2.08) / 24, 1)
  const baseTransform = `translate3d(${x - 12}px, ${y - 12}px, 0)`

  curtain.dataset.targetTheme = nextTheme
  curtain.style.opacity = '1'
  curtain.style.transform = `${baseTransform} scale(0.02)`
  themeAnimationPhase = 'cover'
  themeAnimation = curtain.animate(
    [
      { transform: `${baseTransform} scale(0.02)` },
      { transform: `${baseTransform} scale(${scale})` },
    ],
    {
      duration: 330,
      easing: 'cubic-bezier(0.2, 0.74, 0.24, 1)',
      fill: 'forwards',
    },
  )

  themeAnimation.onfinish = () => {
    if ((themeAnimation?.playbackRate ?? 1) < 0) {
      resetThemeCurtain()
      return
    }

    setTheme(nextTheme)
    themeAnimationPhase = 'fade'
    themeAnimation = curtain.animate([{ opacity: 1 }, { opacity: 0 }], {
      duration: 130,
      easing: 'ease-out',
      fill: 'forwards',
    })
    themeAnimation.onfinish = resetThemeCurtain
  }
}

function handleThemeToggle(event: MouseEvent) {
  if (prefersReducedMotion()) {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
    return
  }

  if (themeAnimationPhase === 'cover' && themeAnimation) {
    themeAnimation.reverse()
    return
  }

  themeAnimation?.cancel()
  resetThemeCurtain()
  const nextTheme: Theme = theme.value === 'dark' ? 'light' : 'dark'
  startThemeReveal(nextTheme, event.clientX, event.clientY)
}

onMounted(() => {
  document.addEventListener('pointerdown', handleDocumentPointerDown)
  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handleDocumentPointerDown)
  document.removeEventListener('keydown', handleKeydown)
  themeAnimation?.cancel()
})
</script>

<template>
  <header v-if="!hidden" class="site-header">
    <RouterLink class="site-header__brand" to="/">
      {{ BRAND_NAME }}
    </RouterLink>

    <div class="site-header__controls">
      <div ref="localePicker" class="site-header__locale-picker">
        <button
          ref="localeTrigger"
          class="site-header__control"
          type="button"
          aria-haspopup="menu"
          aria-controls="language-menu"
          :aria-expanded="localeMenuOpen"
          :title="t('controls.chooseLanguage')"
          :aria-label="t('controls.chooseLanguage')"
          @click="toggleLocaleMenu"
          @keydown.down.prevent="openLocaleMenuFromKeyboard"
        >
          <svg
            class="site-header__icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.7"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="9" />
            <path
              d="M3 12h18M12 3c2.5 2.5 3.6 5.5 3.6 9S14.5 18.5 12 21M12 3c-2.5 2.5-3.6 5.5-3.6 9S9.5 18.5 12 21"
            />
          </svg>
        </button>

        <Transition name="locale-menu">
          <div
            v-if="localeMenuOpen"
            id="language-menu"
            class="site-header__locale-menu"
            role="menu"
            :aria-label="t('controls.chooseLanguage')"
          >
            <button
              v-for="option in [
                ['zh-CN', t('controls.languageChinese')],
                ['en', t('controls.languageEnglish')],
              ] as const"
              :key="option[0]"
              class="site-header__locale-option"
              :class="{ 'is-selected': locale === option[0] }"
              type="button"
              role="menuitemradio"
              :aria-checked="locale === option[0]"
              @click="chooseLocale(option[0])"
            >
              <span>{{ option[1] }}</span>
              <svg
                v-if="locale === option[0]"
                viewBox="0 0 16 16"
                aria-hidden="true"
              >
                <path d="m3 8 3 3 7-7" />
              </svg>
            </button>
          </div>
        </Transition>
      </div>

      <button
        class="site-header__control"
        type="button"
        :title="themeLabel"
        :aria-label="themeLabel"
        @click="handleThemeToggle"
      >
        <svg
          v-if="isDark"
          class="site-header__icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.7"
          stroke-linecap="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="3.5" />
          <path
            d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.65 17.65l1.42 1.42M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.65 6.35l1.42-1.42"
          />
        </svg>
        <svg
          v-else
          class="site-header__icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.7"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M20.4 15.1A8.5 8.5 0 0 1 8.9 3.6 8.5 8.5 0 1 0 20.4 15.1Z" />
        </svg>
      </button>

      <button
        v-if="showReplay"
        class="site-header__control"
        type="button"
        :title="t('controls.replayIntro')"
        :aria-label="t('controls.replayIntro')"
        @click="emit('replay')"
      >
        <svg
          class="site-header__icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.7"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M4 4v6h6" />
          <path d="M5.7 17.1A8.5 8.5 0 1 0 6 6.2L4 10" />
        </svg>
      </button>
    </div>

    <span
      ref="themeCurtain"
      class="site-header__theme-curtain"
      aria-hidden="true"
    />
  </header>
</template>

<style scoped>
.site-header {
  position: fixed;
  z-index: 40;
  inset-block-start: 0;
  inset-inline: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding-block-start: max(12px, env(safe-area-inset-top));
  padding-inline: max(16px, env(safe-area-inset-left));
  color: var(--color-ink);
  pointer-events: none;
}
.site-header__brand,
.site-header__controls {
  pointer-events: auto;
}
.site-header__brand {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  color: inherit;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-decoration: none;
  text-transform: uppercase;
  white-space: nowrap;
}
.site-header__controls {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface-raised);
  box-shadow: 0 1px 0 rgb(255 255 255 / 8%) inset;
  backdrop-filter: blur(12px);
}
.site-header__control {
  display: inline-grid;
  min-width: 44px;
  min-height: 44px;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 999px;
  color: inherit;
  background: transparent;
  cursor: pointer;
  touch-action: manipulation;
  transition:
    background-color 140ms ease,
    opacity 140ms ease;
}
.site-header__control:hover {
  background: var(--color-control-hover);
}
.site-header__control:active {
  opacity: 0.64;
}
.site-header__control:focus-visible,
.site-header__brand:focus-visible,
.site-header__locale-option:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.site-header__icon {
  width: 20px;
  height: 20px;
}
.site-header__locale-picker {
  position: relative;
}
.site-header__locale-menu {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  display: grid;
  min-width: 148px;
  padding: 6px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  color: var(--color-ink);
  background: var(--color-surface-raised);
  box-shadow: 0 14px 38px rgb(0 0 0 / 16%);
  backdrop-filter: blur(16px);
  transform-origin: top right;
}
.site-header__locale-option {
  display: flex;
  min-height: 42px;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 0 12px;
  border: 0;
  border-radius: 9px;
  color: var(--color-ink-muted);
  background: transparent;
  cursor: pointer;
  text-align: left;
  white-space: nowrap;
}
.site-header__locale-option:hover {
  background: var(--color-control-hover);
}
.site-header__locale-option.is-selected {
  color: var(--color-ink);
}
.site-header__locale-option svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.site-header__theme-curtain {
  position: fixed;
  z-index: 100;
  top: 0;
  left: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  opacity: 0;
  background: #f1ebdd;
  pointer-events: none;
  transform: translate3d(-100px, -100px, 0) scale(0.02);
  transform-origin: center;
  will-change: transform, opacity;
}
.site-header__theme-curtain[data-target-theme='dark'] {
  background: #202124;
}
.locale-menu-enter-active,
.locale-menu-leave-active {
  transition:
    opacity 140ms ease,
    transform 140ms var(--ease-out-expo);
}
.locale-menu-enter-from,
.locale-menu-leave-to {
  opacity: 0;
  transform: translate3d(0, -5px, 0) scale(0.97);
}
@media (min-width: 48rem) {
  .site-header {
    padding-block-start: max(20px, env(safe-area-inset-top));
    padding-inline: max(28px, env(safe-area-inset-left));
  }
  .site-header__brand {
    font-size: 0.78rem;
  }
}
@media (max-width: 22.5rem) {
  .site-header__controls {
    gap: 2px;
  }
  .site-header__brand {
    font-size: 0.65rem;
    letter-spacing: 0.06em;
  }
}
@media (prefers-reduced-motion: reduce) {
  .site-header__control,
  .locale-menu-enter-active,
  .locale-menu-leave-active {
    transition: none;
  }
}
</style>
