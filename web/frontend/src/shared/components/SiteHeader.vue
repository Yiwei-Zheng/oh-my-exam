<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { BRAND_NAME } from '@/i18n/invariantContent'
import { useLocale } from '@/shared/composables/useLocale'
import { useTheme } from '@/shared/composables/useTheme'

withDefaults(
  defineProps<{
    showReplay?: boolean
    showPause?: boolean
    paused?: boolean
    hidden?: boolean
  }>(),
  {
    showReplay: true,
    showPause: true,
    paused: false,
    hidden: false,
  },
)

const emit = defineEmits<{
  replay: []
  'toggle-pause': []
}>()

const { t } = useI18n({ useScope: 'global' })
const { isChinese, toggleLocale } = useLocale()
const { isDark, toggleTheme } = useTheme()

const themeLabel = computed(() =>
  isDark.value ? t('controls.useLightTheme') : t('controls.useDarkTheme'),
)

function handleThemeToggle(event: MouseEvent) {
  void toggleTheme({ x: event.clientX, y: event.clientY })
}
</script>

<template>
  <header
    v-if="!hidden"
    class="site-header"
  >
    <RouterLink
      class="site-header__brand"
      to="/"
    >
      {{ BRAND_NAME }}
    </RouterLink>

    <div class="site-header__controls">
      <button
        class="site-header__control site-header__locale"
        type="button"
        :title="t('controls.switchLanguage')"
        :aria-label="t('controls.switchLanguage')"
        @click="toggleLocale"
      >
        <span
          lang="zh-CN"
          :class="{ 'is-active': isChinese }"
        >中</span>
        <span aria-hidden="true">/</span>
        <span
          lang="en"
          :class="{ 'is-active': !isChinese }"
        >EN</span>
      </button>

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
          stroke-linejoin="round"
          aria-hidden="true"
          focusable="false"
        >
          <circle
            cx="12"
            cy="12"
            r="3.5"
          />
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
          focusable="false"
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
          focusable="false"
        >
          <path d="M4 4v6h6" />
          <path d="M5.7 17.1A8.5 8.5 0 1 0 6 6.2L4 10" />
        </svg>
      </button>

      <button
        v-if="showPause"
        class="site-header__control"
        type="button"
        :title="paused ? t('controls.resumeMotion') : t('controls.pauseMotion')"
        :aria-label="
          paused ? t('controls.resumeMotion') : t('controls.pauseMotion')
        "
        @click="emit('toggle-pause')"
      >
        <svg
          v-if="paused"
          class="site-header__icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.7"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
          focusable="false"
        >
          <path d="m8 5 11 7-11 7Z" />
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
          focusable="false"
        >
          <path d="M9 5v14M15 5v14" />
        </svg>
      </button>
    </div>
  </header>
</template>

<style scoped>
.site-header {
  --header-ink: #181815;
  --header-panel: rgb(247 242 228 / 76%);
  --header-hover: rgb(24 24 21 / 9%);
  --header-border: rgb(24 24 21 / 14%);

  position: fixed;
  z-index: 40;
  inset-block-start: 0;
  inset-inline: 0;
  box-sizing: border-box;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding-block-start: max(12px, env(safe-area-inset-top));
  padding-inline-start: max(16px, env(safe-area-inset-left));
  padding-inline-end: max(16px, env(safe-area-inset-right));
  color: var(--color-ink, var(--header-ink));
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
  line-height: 1;
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
  border: 1px solid var(--color-border, var(--header-border));
  border-radius: 999px;
  background: var(--color-surface-raised, var(--header-panel));
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
    color 160ms ease,
    background-color 160ms ease,
    opacity 160ms ease;
}

.site-header__control:hover {
  background: var(--color-control-hover, var(--header-hover));
}

.site-header__control:active {
  opacity: 0.64;
}

.site-header__control:focus-visible,
.site-header__brand:focus-visible {
  outline: 2px solid var(--color-focus, currentColor);
  outline-offset: 2px;
}

.site-header__locale {
  display: inline-flex;
  justify-content: center;
  gap: 0.18rem;
  font: inherit;
  font-size: 0.75rem;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.site-header__locale span:not(.is-active) {
  color: var(--color-ink-muted, currentColor);
}

.site-header__icon {
  width: 20px;
  height: 20px;
}

@media (min-width: 48rem) {
  .site-header {
    padding-block-start: max(20px, env(safe-area-inset-top));
    padding-inline-start: max(28px, env(safe-area-inset-left));
    padding-inline-end: max(28px, env(safe-area-inset-right));
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
  .site-header__control {
    transition: none;
  }
}
</style>
