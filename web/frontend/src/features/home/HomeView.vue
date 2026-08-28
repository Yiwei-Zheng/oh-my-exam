<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import CharacterBlackHole from '@/features/home/components/CharacterBlackHole.vue'
import IntroSequence from '@/features/home/components/IntroSequence.vue'
import TypewriterHeadline from '@/features/home/components/TypewriterHeadline.vue'
import { HERO_PHRASES, HERO_PREFIX } from '@/i18n/invariantContent'
import SiteHeader from '@/shared/components/SiteHeader.vue'
import { useReducedMotion } from '@/shared/composables/useReducedMotion'

type BlackHoleStage = 'dormant' | 'forming' | 'ready'

const INTRO_SESSION_KEY = 'oh-my-exam.intro-seen'
const BLACK_HOLE_TARGET_ID = 'home-black-hole-target'
const { t } = useI18n()
const { prefersReducedMotion } = useReducedMotion()
const introPlaying = ref(false)
const introKey = ref(0)
const blackHoleStage = ref<BlackHoleStage>('dormant')
const manuallyPaused = ref(false)
const documentHidden = ref(false)

const motionPaused = computed(
  () =>
    manuallyPaused.value || documentHidden.value || prefersReducedMotion.value,
)
const headlinePaused = computed(() => motionPaused.value || introPlaying.value)
const heroContentVisible = computed(() => blackHoleStage.value !== 'dormant')

function hasSeenIntro() {
  try {
    return window.sessionStorage.getItem(INTRO_SESSION_KEY) === 'true'
  } catch {
    return false
  }
}

function rememberIntro() {
  try {
    window.sessionStorage.setItem(INTRO_SESSION_KEY, 'true')
  } catch {
    // The intro remains functional when session storage is unavailable.
  }
}

function startInitialExperience() {
  if (prefersReducedMotion.value || hasSeenIntro()) {
    if (prefersReducedMotion.value) {
      rememberIntro()
    }

    blackHoleStage.value = 'ready'
    introPlaying.value = false
    return
  }

  blackHoleStage.value = 'dormant'
  introPlaying.value = true
}

function replayIntro() {
  if (prefersReducedMotion.value) {
    return
  }

  manuallyPaused.value = false
  blackHoleStage.value = 'dormant'
  introKey.value += 1
  introPlaying.value = true
}

function beginFormation() {
  blackHoleStage.value = 'forming'
}

function completeIntro() {
  blackHoleStage.value = 'ready'
  introPlaying.value = false
  rememberIntro()
  void nextTick(() => {
    document.getElementById('home-content')?.focus({ preventScroll: true })
  })
}

function togglePause() {
  manuallyPaused.value = !manuallyPaused.value
}

function syncDocumentVisibility() {
  documentHidden.value = document.visibilityState === 'hidden'
}

watch(prefersReducedMotion, (reducedMotion) => {
  if (reducedMotion && introPlaying.value) {
    completeIntro()
  }
})

onMounted(() => {
  document.addEventListener('visibilitychange', syncDocumentVisibility)
  syncDocumentVisibility()
  startInitialExperience()
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', syncDocumentVisibility)
})
</script>

<template>
  <div class="home">
    <a
      v-if="!introPlaying"
      class="home__skip-link"
      href="#home-content"
    >
      {{ t('controls.skipToContent') }}
    </a>

    <SiteHeader
      :hidden="introPlaying"
      :paused="motionPaused"
      :show-replay="!prefersReducedMotion"
      :show-pause="!prefersReducedMotion"
      @replay="replayIntro"
      @toggle-pause="togglePause"
    />

    <main
      id="home-content"
      class="home__hero"
      tabindex="-1"
      :inert="introPlaying"
    >
      <div
        class="home__visual"
        aria-hidden="false"
      >
        <CharacterBlackHole
          :stage="blackHoleStage"
          :paused="motionPaused"
          :reduced-motion="prefersReducedMotion"
          :label="t('home.blackHoleAriaLabel')"
          :target-id="BLACK_HOLE_TARGET_ID"
        />
      </div>

      <section
        class="home__copy"
        :class="{ 'home__copy--visible': heroContentVisible }"
        aria-labelledby="home-headline"
      >
        <h1
          id="home-headline"
          class="home__headline"
          :aria-label="t('home.accessibleHeadline')"
        >
          <span
            class="home__prefix"
            aria-hidden="true"
          >
            {{ HERO_PREFIX }}
          </span>
          <TypewriterHeadline
            :key="introKey"
            class="home__typewriter"
            :phrases="HERO_PHRASES"
            :paused="headlinePaused"
            :reduced-motion="prefersReducedMotion"
          />
        </h1>
      </section>
    </main>

    <IntroSequence
      v-if="introPlaying"
      :key="introKey"
      :target-id="BLACK_HOLE_TARGET_ID"
      @formation="beginFormation"
      @complete="completeIntro"
    />
  </div>
</template>

<style scoped>
.home {
  position: relative;
  min-width: 320px;
  min-height: 100dvh;
  overflow: hidden;
  background:
    radial-gradient(circle at 22% 47%, var(--color-glow), transparent 32%),
    var(--color-surface);
  color: var(--color-ink);
  transition:
    color 220ms ease,
    background-color 220ms ease;
}

.home__skip-link {
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

.home__skip-link:focus {
  transform: translateY(0);
}

.home__hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 58fr) minmax(0, 42fr);
  width: 100%;
  min-height: 100dvh;
  padding: var(--header-height) var(--page-gutter) 0;
  outline: none;
}

.home__visual {
  position: relative;
  z-index: 1;
  display: grid;
  align-self: stretch;
  min-width: 0;
  place-items: center;
}

.home__copy {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  min-width: 0;
  padding: 0 clamp(8px, 2.4vw, 48px) 4vh clamp(20px, 3.4vw, 72px);
  visibility: hidden;
  opacity: 0;
  transform: translate3d(24px, 0, 0);
}

.home__copy--visible {
  visibility: visible;
  opacity: 1;
  transform: translate3d(0, 0, 0);
  transition:
    opacity 620ms var(--ease-out-expo),
    transform 720ms var(--ease-out-expo),
    visibility 0ms;
}

.home__headline {
  width: 100%;
  margin: 0;
  font-size: inherit;
  font-weight: 400;
}

.home__prefix {
  display: block;
  margin-bottom: clamp(18px, 2.4vh, 32px);
  font-size: clamp(1.05rem, 1.55vw, 1.65rem);
  font-weight: 400;
  line-height: 1.2;
  letter-spacing: 0.18em;
}

.home__typewriter {
  font-size: clamp(1.75rem, 2.55vw, 3.4rem);
  font-weight: 700;
  line-height: 1.08;
  letter-spacing: -0.045em;
}

@media (min-width: 768px) {
  .home__visual {
    transform: translate3d(-7%, 0, 0) scale(1.16);
  }
}

@media (max-width: 1023px) {
  .home__hero {
    grid-template-columns: minmax(0, 54fr) minmax(0, 46fr);
  }

  .home__copy {
    padding-right: 0;
    padding-left: 24px;
  }

  .home__typewriter {
    font-size: clamp(1.4rem, 3vw, 2.35rem);
  }
}

@media (max-width: 767px),
  (orientation: landscape) and (max-height: 500px) and (max-width: 1024px) {
  .home {
    min-height: 100dvh;
    overflow-y: auto;
    background:
      radial-gradient(circle at 50% 52%, var(--color-glow), transparent 43%),
      var(--color-surface);
  }

  .home__hero {
    display: flex;
    min-height: 100dvh;
    align-items: center;
    justify-content: center;
    padding: calc(var(--header-height) + 16px) var(--page-gutter)
      max(32px, env(safe-area-inset-bottom));
  }

  .home__visual {
    position: absolute;
    z-index: 1;
    top: 50%;
    left: 50%;
    width: min(142vw, 820px);
    height: min(108vw, 700px);
    opacity: 0.35;
    filter: blur(2.5px);
    transform: translate3d(-50%, -50%, 0);
    pointer-events: none;
  }

  .home__copy {
    z-index: 2;
    width: 100%;
    max-width: 560px;
    padding: 0;
    align-items: center;
  }

  .home__headline {
    width: 100%;
  }

  .home__prefix {
    margin-bottom: 18px;
    font-size: clamp(1rem, 4.4vw, 1.3rem);
  }

  .home__typewriter {
    max-width: 100%;
    font-size: clamp(1.18rem, 5.55vw, 2rem);
    letter-spacing: -0.055em;
  }
}

@media (orientation: landscape) and (max-height: 500px) and (max-width: 1024px) {
  .home__hero {
    min-height: 100dvh;
    padding-top: calc(var(--header-height) + 8px);
  }

  .home__visual {
    width: min(78vw, 620px);
    height: min(68vw, 520px);
  }

  .home__copy {
    max-width: 72vw;
  }
}

@media (prefers-reduced-motion: reduce) {
  .home__copy,
  .home__copy--visible {
    transform: none;
  }
}
</style>
