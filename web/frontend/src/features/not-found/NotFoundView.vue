<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import CharacterBlackHole from '@/features/home/components/CharacterBlackHole.vue'
import SiteHeader from '@/shared/components/SiteHeader.vue'

const { t } = useI18n()
</script>

<template>
  <div class="not-found-page">
    <a
      class="not-found__skip-link"
      href="#main-content"
    >
      {{ t('controls.skipToContent') }}
    </a>

    <SiteHeader
      :show-replay="false"
      :show-pause="false"
    />

    <main
      id="main-content"
      class="not-found"
      tabindex="-1"
    >
      <div class="not-found__visual">
        <CharacterBlackHole
          stage="ready"
          :paused="true"
          :reduced-motion="true"
          compact
          :label="t('home.blackHoleAriaLabel')"
        />
      </div>

      <section
        class="not-found__copy"
        aria-labelledby="not-found-title"
      >
        <p class="not-found__label">
          {{ t('notFound.label') }}
        </p>
        <h1 id="not-found-title">
          {{ t('notFound.title') }}
        </h1>
        <p class="not-found__description">
          {{ t('notFound.description') }}
        </p>
        <RouterLink
          class="not-found__link"
          to="/"
        >
          <span>{{ t('notFound.backHome') }}</span>
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            focusable="false"
          >
            <path d="m5 12 5-5m-5 5 5 5m-5-5h14" />
          </svg>
        </RouterLink>
      </section>
    </main>
  </div>
</template>

<style scoped>
.not-found-page {
  min-height: 100dvh;
  overflow: hidden;
  color: var(--color-ink, #171714);
  background: var(--color-surface, #f2eee4);
}

.not-found__skip-link {
  position: fixed;
  z-index: 60;
  top: 10px;
  left: 10px;
  padding: 12px 16px;
  color: var(--color-surface);
  background: var(--color-ink);
  border-radius: 4px;
  transform: translateY(-150%);
  transition: transform 180ms var(--ease-out-expo);
}

.not-found__skip-link:focus {
  transform: translateY(0);
}

.not-found {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(18rem, 0.9fr);
  align-items: center;
  min-height: 100dvh;
  padding: clamp(6rem, 11vh, 9rem) clamp(1.5rem, 5vw, 5rem)
    clamp(2rem, 5vw, 5rem);
}

.not-found__visual {
  display: grid;
  place-items: center;
  width: min(48vw, 42rem);
  aspect-ratio: 1;
  justify-self: center;
}

.not-found__copy {
  position: relative;
  z-index: 1;
  width: min(100%, 38rem);
}

.not-found__label {
  margin: 0 0 1rem;
  color: var(--color-ink-muted, currentColor);
  font-size: clamp(0.75rem, 1vw, 0.875rem);
  font-weight: 600;
  letter-spacing: 0.14em;
}

.not-found h1 {
  max-width: 12ch;
  margin: 0;
  font-size: clamp(2.5rem, 6vw, 6.5rem);
  line-height: 0.95;
  letter-spacing: -0.055em;
  text-wrap: balance;
}

.not-found__description {
  max-width: 42ch;
  margin: clamp(1.5rem, 3vw, 2.5rem) 0;
  color: var(--color-ink-muted, currentColor);
  font-size: clamp(1rem, 1.4vw, 1.125rem);
  line-height: 1.65;
}

.not-found__link {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  gap: 0.75rem;
  color: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-underline-offset: 0.35em;
  text-decoration-thickness: 1px;
  touch-action: manipulation;
  transition: opacity 180ms ease;
}

.not-found__link svg {
  width: 1.25rem;
  height: 1.25rem;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.5;
  transition: transform 180ms ease;
}

.not-found__link:hover {
  opacity: 0.68;
}

.not-found__link:hover svg {
  transform: translateX(-0.2rem);
}

.not-found__link:focus-visible {
  border-radius: 0.125rem;
  outline: 2px solid currentColor;
  outline-offset: 0.35rem;
}

@media (max-width: 47.99rem),
  (orientation: landscape) and (max-height: 500px) and (max-width: 1024px) {
  .not-found {
    grid-template-columns: minmax(0, 1fr);
    align-content: center;
    padding-inline: clamp(1.25rem, 7vw, 2rem);
  }

  .not-found__visual {
    position: absolute;
    inset: 50% auto auto 50%;
    width: min(125vw, 34rem);
    opacity: 0.26;
    filter: blur(2px);
    transform: translate(-50%, -50%);
  }

  .not-found__copy {
    justify-self: center;
  }

  .not-found h1 {
    max-width: 11ch;
  }
}

@media (prefers-reduced-motion: reduce) {
  .not-found__link,
  .not-found__link svg {
    transition: none;
  }
}
</style>
