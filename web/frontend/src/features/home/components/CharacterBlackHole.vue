<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type {
  BlackHoleRenderer,
  BlackHoleStage,
} from '@/features/home/components/blackHoleRenderer'
import { ACADEMIC_ORBIT_SEGMENTS } from '@/i18n/invariantContent'
import { useTheme } from '@/shared/composables/useTheme'

const props = withDefaults(
  defineProps<{
    stage: BlackHoleStage
    paused: boolean
    reducedMotion: boolean
    compact?: boolean
    label: string
    targetId?: string
  }>(),
  { compact: false, targetId: undefined },
)

const { isDark } = useTheme()
const host = ref<HTMLElement>()
const gpuReady = ref(false)
const gpuFailed = ref(false)
const fallbackText = ACADEMIC_ORBIT_SEGMENTS.map((segments) =>
  `${segments.join('  ·  ')}  ·  `.repeat(2),
)
let renderer: BlackHoleRenderer | undefined
let resizeObserver: ResizeObserver | undefined
let initializationId = 0

const rendererState = computed(() => ({
  stage: props.stage,
  paused: props.paused,
  reducedMotion: props.reducedMotion,
  dark: isDark.value,
}))

function supportsWebGl2() {
  return (
    typeof window !== 'undefined' &&
    typeof window.WebGL2RenderingContext !== 'undefined'
  )
}

async function initializeRenderer() {
  if (!host.value || props.reducedMotion || !supportsWebGl2()) return

  const currentInitialization = ++initializationId

  try {
    const { createBlackHoleRenderer } =
      await import('@/features/home/components/blackHoleRenderer')
    if (!host.value || currentInitialization !== initializationId) return

    renderer = await createBlackHoleRenderer(host.value, rendererState.value)
    if (currentInitialization !== initializationId) {
      renderer.destroy()
      renderer = undefined
      return
    }

    renderer.canvas.addEventListener(
      'webglcontextlost',
      (event) => {
        event.preventDefault()
        gpuReady.value = false
        gpuFailed.value = true
      },
      { once: true },
    )
    resizeObserver = new ResizeObserver(() => renderer?.resize())
    resizeObserver.observe(host.value)
    gpuReady.value = true
  } catch (error) {
    gpuFailed.value = true
    if (import.meta.env.DEV) {
      console.warn(
        'Black-hole GPU renderer unavailable; using SVG fallback.',
        error,
      )
    }
  }
}

watch(rendererState, (state) => renderer?.setState(state), { deep: true })

onMounted(() => {
  void initializeRenderer()
})

onBeforeUnmount(() => {
  initializationId += 1
  resizeObserver?.disconnect()
  renderer?.destroy()
})
</script>

<template>
  <figure
    ref="host"
    class="black-hole"
    :class="[
      `black-hole--${stage}`,
      {
        'black-hole--gpu-ready': gpuReady,
        'black-hole--gpu-failed': gpuFailed,
        'black-hole--reduced': reducedMotion,
      },
    ]"
    :data-stage="stage"
    :data-renderer="gpuReady ? 'webgl' : 'svg'"
    role="img"
    :aria-label="label"
  >
    <svg
      class="black-hole__fallback"
      viewBox="0 0 1000 700"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <radialGradient id="fallback-core" cx="42%" cy="38%">
          <stop offset="0" stop-color="#111522" />
          <stop offset="64%" stop-color="#050609" />
          <stop offset="100%" stop-color="#000" />
        </radialGradient>
        <filter id="fallback-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="8" />
        </filter>
        <path
          id="fallback-upper"
          d="M-80 15 C65 75 120 145 190 235 C235 292 316 287 348 260 C395 220 348 175 276 196 C190 220 179 333 244 375"
        />
        <path
          id="fallback-lower"
          d="M-100 710 C2 607 83 544 155 451 C205 387 294 338 360 302 C417 270 428 230 369 207 C302 181 226 240 229 319 C232 420 337 467 398 399"
        />
        <path
          id="fallback-right"
          d="M1080 705 C835 666 664 611 493 493 C399 429 339 362 300 306 C270 262 273 217 318 203 C370 187 410 230 397 278 C381 337 314 355 273 321"
        />
      </defs>

      <ellipse
        class="black-hole__fallback-space"
        cx="240"
        cy="266"
        rx="330"
        ry="285"
      />

      <g class="black-hole__fallback-streams">
        <text
          v-for="index in 5"
          :key="`upper-${index}`"
          :class="`black-hole__fallback-text tone-${index % 3}`"
        >
          <textPath
            href="#fallback-upper"
            :startOffset="`${(index - 1) * 17}%`"
          >
            {{ fallbackText[index % fallbackText.length] }}
          </textPath>
        </text>
        <text
          v-for="index in 7"
          :key="`lower-${index}`"
          :class="`black-hole__fallback-text tone-${index % 3}`"
        >
          <textPath
            href="#fallback-lower"
            :startOffset="`${(index - 1) * 13}%`"
          >
            {{ fallbackText[(index + 1) % fallbackText.length] }}
          </textPath>
        </text>
        <text
          v-for="index in 4"
          :key="`right-${index}`"
          :class="`black-hole__fallback-text tone-${index % 3}`"
        >
          <textPath href="#fallback-right" :startOffset="`${index * 18}%`">
            {{ fallbackText[(index + 2) % fallbackText.length] }}
          </textPath>
        </text>
      </g>

      <path
        class="black-hole__fallback-disk"
        d="M-80 438 C95 356 174 300 240 266 C346 211 505 155 722 74"
      />
      <ellipse
        class="black-hole__fallback-halo"
        cx="240"
        cy="266"
        rx="105"
        ry="85"
        transform="rotate(-19 240 266)"
      />
      <ellipse
        class="black-hole__fallback-ring"
        cx="240"
        cy="266"
        rx="87"
        ry="69"
        transform="rotate(-19 240 266)"
      />
      <ellipse
        class="black-hole__fallback-core"
        cx="240"
        cy="266"
        rx="80"
        ry="63"
        transform="rotate(-19 240 266)"
      />
    </svg>

    <span :id="targetId" class="black-hole__target" aria-hidden="true" />
  </figure>
</template>

<style scoped>
.black-hole {
  position: relative;
  width: 100%;
  height: 100%;
  margin: 0;
  overflow: hidden;
  contain: strict;
  isolation: isolate;
}

.black-hole :deep(.black-hole__canvas) {
  position: absolute;
  z-index: 2;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
  opacity: 0;
  transition: opacity 260ms ease;
}

.black-hole--gpu-ready :deep(.black-hole__canvas) {
  opacity: 1;
}

.black-hole__fallback {
  position: absolute;
  z-index: 1;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 1;
  transition: opacity 260ms ease;
}

.black-hole--gpu-ready .black-hole__fallback {
  opacity: 0;
}

.black-hole__fallback-streams,
.black-hole__fallback-space,
.black-hole__fallback-disk,
.black-hole__fallback-halo,
.black-hole__fallback-ring,
.black-hole__fallback-core {
  opacity: 0;
  transition: opacity 500ms ease;
}

.black-hole--forming .black-hole__fallback-streams,
.black-hole--forming .black-hole__fallback-space,
.black-hole--forming .black-hole__fallback-disk,
.black-hole--forming .black-hole__fallback-halo,
.black-hole--forming .black-hole__fallback-ring,
.black-hole--forming .black-hole__fallback-core,
.black-hole--ready .black-hole__fallback-streams,
.black-hole--ready .black-hole__fallback-space,
.black-hole--ready .black-hole__fallback-disk,
.black-hole--ready .black-hole__fallback-halo,
.black-hole--ready .black-hole__fallback-ring,
.black-hole--ready .black-hole__fallback-core {
  opacity: 1;
}

.black-hole__fallback-text {
  fill: var(--color-ink);
  font-family: 'IBM Plex Mono', monospace;
  font-size: 14px;
  letter-spacing: 0.055em;
  opacity: 0.72;
}

.black-hole__fallback-text.tone-1 {
  fill: var(--color-hole-hot);
}

.black-hole__fallback-text.tone-2 {
  fill: color-mix(in srgb, var(--color-ink), white 28%);
}

.black-hole__fallback-space {
  fill: rgb(2 4 8 / 78%);
  filter: url('#fallback-glow');
}

.black-hole__fallback-disk {
  fill: none;
  stroke: #ff8b30;
  stroke-width: 13;
  filter: url('#fallback-glow');
}

.black-hole__fallback-halo {
  fill: none;
  stroke: var(--color-hole-hot);
  stroke-width: 32;
  filter: url('#fallback-glow');
}

.black-hole__fallback-ring {
  fill: none;
  stroke: #ffd29a;
  stroke-width: 6;
  filter: url('#fallback-glow');
}

.black-hole__fallback-core {
  fill: url('#fallback-core');
}

.black-hole__target {
  position: absolute;
  z-index: 3;
  top: 38%;
  left: 24%;
  width: 23vmin;
  max-width: 230px;
  min-width: 112px;
  aspect-ratio: 1;
  border-radius: 50%;
  transform: translate3d(-50%, -50%, 0);
  pointer-events: none;
}

@media (max-width: 767px),
  (orientation: landscape) and (max-height: 500px) and (max-width: 1024px) {
  .black-hole__target {
    top: 43%;
    left: 42%;
    width: 30vmin;
    min-width: 96px;
  }

  .black-hole__fallback {
    transform: translate3d(18%, 5%, 0) scale(0.9);
    transform-origin: center;
  }
}

@media (prefers-reduced-motion: reduce) {
  .black-hole :deep(.black-hole__canvas),
  .black-hole__fallback,
  .black-hole__fallback-streams,
  .black-hole__fallback-space,
  .black-hole__fallback-disk,
  .black-hole__fallback-halo,
  .black-hole__fallback-ring,
  .black-hole__fallback-core {
    transition: none;
  }
}
</style>
