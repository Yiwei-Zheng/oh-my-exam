<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { BRAND_NAME } from '@/i18n/invariantContent'

const props = defineProps<{
  targetId: string
}>()

const emit = defineEmits<{
  formation: []
  complete: []
}>()

type IntroPhase = 'glitch' | 'flight' | 'formation'

const { t } = useI18n()
const phase = ref<IntroPhase>('glitch')
const originLetter = ref<HTMLElement>()
const skipButton = ref<HTMLButtonElement>()
const timers = new Set<number>()
let flightAnimation: Animation | undefined
let completed = false

function wait(duration: number) {
  return new Promise<void>((resolve) => {
    const timer = window.setTimeout(() => {
      timers.delete(timer)
      resolve()
    }, duration)
    timers.add(timer)
  })
}

function clearTimers() {
  timers.forEach((timer) => window.clearTimeout(timer))
  timers.clear()
}

function finish() {
  if (completed) {
    return
  }

  completed = true
  clearTimers()
  flightAnimation?.cancel()
  emit('complete')
}

function skip() {
  emit('formation')
  finish()
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    skip()
  }
}

async function flyOriginToTarget() {
  await nextTick()
  await wait(180)

  if (completed) {
    return
  }

  const origin = originLetter.value
  const target = document.getElementById(props.targetId)

  if (!origin || !target) {
    await wait(1150)
    return
  }

  const originBounds = origin.getBoundingClientRect()
  const targetBounds = target.getBoundingClientRect()
  const deltaX =
    targetBounds.left +
    targetBounds.width / 2 -
    (originBounds.left + originBounds.width / 2)
  const deltaY =
    targetBounds.top +
    targetBounds.height / 2 -
    (originBounds.top + originBounds.height / 2)
  const targetScale = Math.max(
    3,
    (targetBounds.width / Math.max(originBounds.width, 1)) * 0.74,
  )
  const arcLift = Math.min(96, Math.max(40, window.innerHeight * 0.085))
  const middleScale = 1 + (targetScale - 1) * 0.48

  flightAnimation = origin.animate(
    [
      { offset: 0, transform: 'translate3d(0, 0, 0) scale(1)' },
      {
        offset: 0.14,
        transform: `translate3d(${deltaX * -0.035}px, ${deltaY * -0.025}px, 0) scale(0.96)`,
      },
      {
        offset: 0.5,
        transform: `translate3d(${deltaX * 0.48}px, ${deltaY * 0.48 - arcLift}px, 0) scale(${middleScale})`,
      },
      {
        offset: 0.82,
        transform: `translate3d(${deltaX * 0.9}px, ${deltaY * 0.9 - arcLift * 0.24}px, 0) scale(${targetScale * 1.04})`,
      },
      {
        offset: 1,
        transform: `translate3d(${deltaX}px, ${deltaY}px, 0) scale(${targetScale})`,
      },
    ],
    {
      duration: 1150,
      easing: 'cubic-bezier(0.16, 1, 0.3, 1)',
      fill: 'forwards',
    },
  )

  await flightAnimation.finished.catch(() => undefined)
}

async function play() {
  await wait(2200)
  if (completed) {
    return
  }

  phase.value = 'flight'
  await flyOriginToTarget()
  if (completed) {
    return
  }

  phase.value = 'formation'
  emit('formation')
  await wait(1200)
  finish()
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  void nextTick(() => skipButton.value?.focus())
  void play()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  clearTimers()
  flightAnimation?.cancel()
})
</script>

<template>
  <div
    class="intro"
    :class="`intro--${phase}`"
    role="dialog"
    aria-modal="true"
    aria-labelledby="intro-title"
  >
    <h2
      id="intro-title"
      class="sr-only"
      v-text="BRAND_NAME"
    />
    <button
      ref="skipButton"
      class="intro__skip"
      type="button"
      @click="skip"
    >
      {{ t('controls.skipIntro') }}
    </button>

    <div
      class="intro__scanline"
      aria-hidden="true"
    />
    <div
      class="intro__title-stack"
      aria-hidden="true"
    >
      <span
        class="intro__line intro__line--replica intro__line--replica-top"
        v-text="BRAND_NAME"
      />
      <span class="intro__line intro__line--main">
        <span
          ref="originLetter"
          class="intro__letter intro__letter--origin"
        >O</span>
        <span
          class="intro__letter intro__letter--fading"
          v-text="BRAND_NAME.slice(1)"
        />
      </span>
      <span
        class="intro__line intro__line--replica intro__line--replica-bottom"
        v-text="BRAND_NAME"
      />
    </div>
  </div>
</template>

<style scoped>
.intro {
  position: fixed;
  z-index: 50;
  inset: 0;
  display: grid;
  overflow: hidden;
  width: 100%;
  min-width: 320px;
  min-height: 100dvh;
  place-items: center;
  color: #f0eeec;
  background: #1a1828;
  isolation: isolate;
  animation: intro-background 2200ms steps(1, end) both;
}

.intro__skip {
  position: fixed;
  z-index: 3;
  top: max(16px, env(safe-area-inset-top));
  right: max(16px, env(safe-area-inset-right));
  min-width: 72px;
  min-height: 44px;
  padding: 0 16px;
  color: currentColor;
  cursor: pointer;
  background: rgb(10 10 12 / 18%);
  border: 1px solid currentColor;
  border-radius: 999px;
  transition:
    color 180ms ease,
    background-color 180ms ease,
    transform 180ms var(--ease-out-expo);
}

.intro__skip:hover {
  color: #1a1828;
  background: #f0eeec;
}

.intro__skip:focus-visible {
  outline-color: currentColor;
}

.intro__skip:active {
  transform: scale(0.96);
}

.intro__title-stack {
  position: relative;
  z-index: 2;
  display: grid;
  place-items: center;
  width: min(88vw, 1400px);
  min-height: 32vh;
  font-size: clamp(2.25rem, 6.2vw, 8rem);
  font-weight: 700;
  line-height: 0.92;
  letter-spacing: clamp(0.08em, 1.2vw, 0.18em);
  text-transform: uppercase;
}

.intro__line {
  position: absolute;
  white-space: nowrap;
}

.intro__line--main {
  display: flex;
  animation: intro-main-glitch 2200ms steps(1, end) both;
}

.intro__line--replica {
  opacity: 0;
  animation: intro-replica 2200ms steps(1, end) both;
}

.intro__line--replica-top {
  --replica-y: -1.02em;
}

.intro__line--replica-bottom {
  --replica-y: 1.02em;
}

.intro__letter {
  display: inline-block;
  will-change: transform, opacity, filter;
}

.intro__letter--origin {
  position: relative;
  z-index: 2;
  transform-origin: center;
}

.intro--flight .intro__letter--fading {
  opacity: 0;
  filter: blur(7px);
  transform: translate3d(22px, 0, 0);
  transition:
    opacity 220ms ease-in,
    filter 260ms ease-in,
    transform 260ms ease-in;
}

.intro--flight .intro__line--main {
  clip-path: none;
  transform: none;
  animation: none;
}

.intro--flight .intro__line--replica {
  opacity: 0 !important;
}

.intro--formation {
  pointer-events: none;
  opacity: 0;
  transition: opacity 900ms var(--ease-out-expo);
}

.intro--formation .intro__skip {
  opacity: 0;
}

.intro__scanline {
  position: absolute;
  z-index: 1;
  top: 0;
  left: -10%;
  width: 120%;
  height: 2px;
  opacity: 0;
  background: currentColor;
  box-shadow: 0 0 24px currentColor;
  animation: intro-scanline 2200ms steps(1, end) both;
}

@keyframes intro-background {
  0%,
  33% {
    color: #f0eeec;
    background: #1a1828;
  }

  34%,
  61% {
    color: #1a1828;
    background: #f0eeec;
  }

  62%,
  71% {
    color: #f0eeec;
    background: #02099a;
  }

  72%,
  100% {
    color: #1a1828;
    background: #f0eeec;
  }
}

@keyframes intro-main-glitch {
  0%,
  9% {
    clip-path: inset(0);
    transform: translate3d(0, 0, 0) scale(1);
  }

  10% {
    clip-path: inset(42% 0 38% 0);
    transform: translate3d(0.04em, 0, 0) scaleX(1.04);
  }

  12%,
  33% {
    clip-path: inset(0);
    transform: translate3d(0, 0, 0) scale(1);
  }

  34%,
  42% {
    transform: translate3d(0, 0, 0) scale(1.08);
  }

  43% {
    clip-path: inset(8% 0 55% 0);
    transform: translate3d(-0.05em, 0, 0) scaleX(0.98);
  }

  46%,
  100% {
    clip-path: inset(0);
    transform: translate3d(0, 0, 0) scale(1);
  }
}

@keyframes intro-replica {
  0%,
  11% {
    opacity: 0;
    transform: translate3d(0, 0, 0);
  }

  12%,
  33% {
    opacity: 1;
    transform: translate3d(0, var(--replica-y), 0);
  }

  34%,
  41% {
    opacity: 1;
    transform: translate3d(0, var(--replica-y), 0) scale(1.08);
  }

  42%,
  100% {
    opacity: 0;
    transform: translate3d(0, 0, 0);
  }
}

@keyframes intro-scanline {
  0%,
  9% {
    top: 18%;
    opacity: 0;
  }

  10% {
    top: 48%;
    opacity: 0.85;
  }

  13%,
  100% {
    top: 82%;
    opacity: 0;
  }
}

@media (max-width: 767px) {
  .intro__title-stack {
    width: 94vw;
    font-size: clamp(1.55rem, 7.2vw, 3.2rem);
    letter-spacing: 0.08em;
  }

  .intro__skip {
    top: max(12px, env(safe-area-inset-top));
    right: max(12px, env(safe-area-inset-right));
  }
}
</style>
