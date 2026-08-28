<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'

import { ACADEMIC_ORBIT_SEGMENTS } from '@/i18n/invariantContent'

type BlackHoleStage = 'dormant' | 'forming' | 'ready'

interface CharacterBlackHoleProps {
  stage: BlackHoleStage
  paused: boolean
  reducedMotion: boolean
  compact?: boolean
  label: string
  targetId?: string
}

const props = withDefaults(defineProps<CharacterBlackHoleProps>(), {
  compact: false,
  targetId: undefined,
})

const makeOrbitText = (segments: readonly string[]) => {
  const sequence = segments.join('   ·   ')

  return `${sequence}   ·   ${sequence}   ·   `
}

const orbitBlueprints = [
  {
    path: 'M 275 310 A 125 44 0 1 1 525 310 A 125 44 0 1 1 275 310',
    duration: '24s',
    phase: '-4s',
    revealDelay: '40ms',
    fontSize: 9.6,
    startOffset: '3%',
    content: makeOrbitText(ACADEMIC_ORBIT_SEGMENTS[0]),
  },
  {
    path: 'M 235 310 A 165 61 0 1 1 565 310 A 165 61 0 1 1 235 310',
    duration: '31s',
    phase: '-17s',
    revealDelay: '140ms',
    fontSize: 10,
    startOffset: '18%',
    content: makeOrbitText(ACADEMIC_ORBIT_SEGMENTS[1]),
  },
  {
    path: 'M 193 310 A 207 82 0 1 1 607 310 A 207 82 0 1 1 193 310',
    duration: '39s',
    phase: '-9s',
    revealDelay: '240ms',
    fontSize: 10.4,
    startOffset: '34%',
    content: makeOrbitText(ACADEMIC_ORBIT_SEGMENTS[2]),
  },
  {
    path: 'M 148 310 A 252 106 0 1 1 652 310 A 252 106 0 1 1 148 310',
    duration: '47s',
    phase: '-28s',
    revealDelay: '340ms',
    fontSize: 10.8,
    startOffset: '8%',
    content: makeOrbitText(ACADEMIC_ORBIT_SEGMENTS[3]),
  },
  {
    path: 'M 90 310 A 310 139 0 1 1 710 310 A 310 139 0 1 1 90 310',
    duration: '58s',
    phase: '-41s',
    revealDelay: '440ms',
    fontSize: 11.2,
    startOffset: '24%',
    content: makeOrbitText(ACADEMIC_ORBIT_SEGMENTS[4]),
  },
] as const

const instanceId = useId().replace(/[^a-zA-Z0-9_-]/g, '')
const coreGradientId = `black-hole-${instanceId}-core`
const orbitGradientId = `black-hole-${instanceId}-orbit-ink`
const glowFilterId = `black-hole-${instanceId}-glow`
const orbits = orbitBlueprints.map((orbit, index) => ({
  ...orbit,
  pathId: `black-hole-${instanceId}-orbit-${index + 1}`,
}))

const pixelFragments = [
  { x: 85, y: 256, width: 3, height: 3, opacity: 0.4 },
  { x: 119, y: 402, width: 5, height: 2, opacity: 0.5 },
  { x: 176, y: 151, width: 2, height: 5, opacity: 0.32 },
  { x: 221, y: 495, width: 4, height: 4, opacity: 0.42 },
  { x: 584, y: 128, width: 5, height: 2, opacity: 0.36 },
  { x: 641, y: 464, width: 3, height: 5, opacity: 0.44 },
  { x: 706, y: 236, width: 4, height: 3, opacity: 0.34 },
  { x: 736, y: 371, width: 2, height: 2, opacity: 0.5 },
] as const

const glyphFragments = [
  { x: 108, y: 331, value: '∑', size: 9, opacity: 0.4 },
  { x: 153, y: 206, value: '01', size: 7, opacity: 0.34 },
  { x: 247, y: 115, value: 'λ', size: 8, opacity: 0.46 },
  { x: 535, y: 506, value: '{}', size: 7, opacity: 0.38 },
  { x: 665, y: 174, value: 'Δ', size: 9, opacity: 0.44 },
  { x: 700, y: 415, value: 'π', size: 8, opacity: 0.38 },
] as const

const parallaxFactors = [0.45, 0.65, 0.85, 1.08, 1.32] as const
const figureRef = ref<HTMLElement | null>(null)

let frameHandle: number | undefined
let latestPointerX = 0
let latestPointerY = 0
let finePointerQuery: MediaQueryList | undefined
let systemReducedMotionQuery: MediaQueryList | undefined

const canUseParallax = () =>
  props.stage === 'ready' &&
  !props.paused &&
  !props.reducedMotion &&
  finePointerQuery?.matches === true &&
  systemReducedMotionQuery?.matches !== true

const setParallax = (x: number, y: number) => {
  const element = figureRef.value

  if (!element) return

  parallaxFactors.forEach((factor, index) => {
    const layer = index + 1
    element.style.setProperty(
      `--parallax-x-${layer}`,
      `${(x * factor).toFixed(2)}px`,
    )
    element.style.setProperty(
      `--parallax-y-${layer}`,
      `${(y * factor).toFixed(2)}px`,
    )
  })
}

const resetParallax = () => {
  if (frameHandle !== undefined) {
    window.cancelAnimationFrame(frameHandle)
    frameHandle = undefined
  }

  figureRef.value?.removeAttribute('data-pointer-active')
  setParallax(0, 0)
}

const handlePointerMove = (event: PointerEvent) => {
  if (event.pointerType !== 'mouse' || !canUseParallax()) return

  latestPointerX = event.clientX
  latestPointerY = event.clientY
  figureRef.value?.setAttribute('data-pointer-active', 'true')

  if (frameHandle !== undefined) return

  frameHandle = window.requestAnimationFrame(() => {
    frameHandle = undefined

    const element = figureRef.value

    if (!element || !canUseParallax()) {
      resetParallax()
      return
    }

    const bounds = element.getBoundingClientRect()

    if (bounds.width === 0 || bounds.height === 0) return

    const normalizedX = Math.max(
      -1,
      Math.min(1, ((latestPointerX - bounds.left) / bounds.width - 0.5) * 2),
    )
    const normalizedY = Math.max(
      -1,
      Math.min(1, ((latestPointerY - bounds.top) / bounds.height - 0.5) * 2),
    )

    setParallax(normalizedX * 3.2, normalizedY * 2.4)
  })
}

const handleMediaChange = () => {
  if (!canUseParallax()) resetParallax()
}

onMounted(() => {
  finePointerQuery = window.matchMedia('(hover: hover) and (pointer: fine)')
  systemReducedMotionQuery = window.matchMedia(
    '(prefers-reduced-motion: reduce)',
  )
  finePointerQuery.addEventListener('change', handleMediaChange)
  systemReducedMotionQuery.addEventListener('change', handleMediaChange)
})

watch(
  () => [props.paused, props.reducedMotion, props.stage] as const,
  () => {
    if (!canUseParallax()) resetParallax()
  },
)

onBeforeUnmount(() => {
  finePointerQuery?.removeEventListener('change', handleMediaChange)
  systemReducedMotionQuery?.removeEventListener('change', handleMediaChange)
  resetParallax()
})
</script>

<template>
  <figure
    ref="figureRef"
    class="black-hole"
    :class="{
      'black-hole--compact': compact,
      'black-hole--paused': paused,
      'black-hole--reduced': reducedMotion,
      [`black-hole--${stage}`]: true,
    }"
    role="img"
    :aria-label="label"
    :data-stage="stage"
    @pointerleave="resetParallax"
    @pointermove.passive="handlePointerMove"
  >
    <svg
      class="black-hole__svg"
      viewBox="0 0 800 620"
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <radialGradient
          :id="coreGradientId"
          cx="46%"
          cy="42%"
          fx="44%"
          fy="40%"
          r="67%"
        >
          <stop
            class="black-hole__core-stop black-hole__core-stop--center"
            offset="0"
          />
          <stop
            class="black-hole__core-stop black-hole__core-stop--edge"
            offset="1"
          />
        </radialGradient>

        <linearGradient
          :id="orbitGradientId"
          x1="0"
          y1="126"
          x2="0"
          y2="494"
          gradientUnits="userSpaceOnUse"
        >
          <stop
            class="black-hole__orbit-stop black-hole__orbit-stop--back"
            offset="0"
          />
          <stop
            class="black-hole__orbit-stop black-hole__orbit-stop--middle"
            offset="0.48"
          />
          <stop
            class="black-hole__orbit-stop black-hole__orbit-stop--front"
            offset="1"
          />
        </linearGradient>

        <filter
          :id="glowFilterId"
          x="-70%"
          y="-180%"
          width="240%"
          height="460%"
        >
          <feGaussianBlur stdDeviation="12" />
        </filter>

        <path
          v-for="orbit in orbits"
          :id="orbit.pathId"
          :key="orbit.pathId"
          :d="orbit.path"
        />
      </defs>

      <ellipse
        class="black-hole__well"
        cx="400"
        cy="324"
        rx="313"
        ry="116"
        shape-rendering="geometricPrecision"
      />

      <g class="black-hole__debris-field">
        <rect
          v-for="(fragment, index) in pixelFragments"
          :key="`pixel-${index}`"
          class="black-hole__pixel"
          :x="fragment.x"
          :y="fragment.y"
          :width="fragment.width"
          :height="fragment.height"
          :opacity="fragment.opacity"
        />
        <text
          v-for="(fragment, index) in glyphFragments"
          :key="`glyph-${index}`"
          class="black-hole__fragment"
          :x="fragment.x"
          :y="fragment.y"
          :font-size="fragment.size"
          :opacity="fragment.opacity"
        >
          {{ fragment.value }}
        </text>
      </g>

      <g
        v-for="(orbit, index) in orbits"
        :key="orbit.pathId"
        class="black-hole__parallax"
        :class="`black-hole__parallax--${index + 1}`"
      >
        <g
          class="black-hole__ring"
          :style="{
            '--reveal-delay': orbit.revealDelay,
          }"
        >
          <g
            class="black-hole__orbit"
            :style="{
              '--orbit-duration': orbit.duration,
              '--orbit-phase': orbit.phase,
            }"
          >
            <path
              class="black-hole__guide"
              :d="orbit.path"
              pathLength="100"
              vector-effect="non-scaling-stroke"
            />
            <text
              class="black-hole__orbit-text"
              :fill="`url(#${orbitGradientId})`"
              :font-size="orbit.fontSize"
            >
              <textPath
                :href="`#${orbit.pathId}`"
                :startOffset="orbit.startOffset"
              >
                {{ orbit.content }}
              </textPath>
            </text>
          </g>
        </g>
      </g>

      <g class="black-hole__core">
        <ellipse
          class="black-hole__aura black-hole__aura--wide"
          cx="400"
          cy="310"
          rx="124"
          ry="70"
          :filter="`url(#${glowFilterId})`"
        />
        <ellipse
          class="black-hole__aura black-hole__aura--tight"
          cx="400"
          cy="310"
          rx="103"
          ry="60"
        />
        <ellipse
          class="black-hole__core-shadow"
          cx="400"
          cy="315"
          rx="96"
          ry="58"
        />
        <ellipse
          class="black-hole__core-disc"
          cx="400"
          cy="310"
          rx="88"
          ry="54"
          :fill="`url(#${coreGradientId})`"
        />
        <ellipse
          class="black-hole__core-rim"
          cx="400"
          cy="310"
          rx="88"
          ry="54"
        />
        <path
          class="black-hole__front-caustic"
          d="M 304 319 C 347 372 453 372 496 319"
        />
      </g>
    </svg>

    <span
      :id="targetId"
      class="black-hole__target"
      aria-hidden="true"
      data-black-hole-target="true"
    />
  </figure>
</template>

<style scoped>
.black-hole {
  --black-hole-core: var(--color-void, #090a0c);
  --black-hole-ink: var(--color-ink, #22211f);
  --black-hole-muted: var(--color-ink-muted, #75716a);
  --black-hole-surface: var(--color-surface, #f4efe4);
  --black-hole-accent: var(--color-accent, var(--black-hole-ink));
  --black-hole-glow: var(--color-glow, var(--black-hole-accent));

  position: relative;
  display: grid;
  width: 100%;
  max-width: 100%;
  aspect-ratio: 40 / 31;
  margin: 0;
  overflow: clip;
  color: var(--black-hole-ink);
  contain: layout paint;
  isolation: isolate;
  user-select: none;
}

.black-hole--compact {
  aspect-ratio: 1;
}

.black-hole__svg {
  display: block;
  grid-area: 1 / 1;
  width: 100%;
  height: 100%;
  overflow: visible;
  transform-origin: center;
}

.black-hole--compact .black-hole__svg {
  transform: scale(1.04);
}

.black-hole__core-stop--center,
.black-hole__core-stop--edge {
  stop-color: var(--black-hole-core);
}

.black-hole__core-stop--center {
  stop-opacity: 0.97;
}

.black-hole__core-stop--edge {
  stop-opacity: 1;
}

.black-hole__orbit-stop--back {
  stop-color: var(--black-hole-muted);
  stop-opacity: 0.52;
}

.black-hole__orbit-stop--middle {
  stop-color: var(--black-hole-ink);
  stop-opacity: 0.78;
}

.black-hole__orbit-stop--front {
  stop-color: var(--black-hole-ink);
  stop-opacity: 0.98;
}

.black-hole__well {
  fill: var(--black-hole-muted);
  opacity: 0.045;
  transform-box: view-box;
  transform-origin: center;
}

.black-hole__debris-field {
  transform-box: view-box;
  transform-origin: center;
  animation: debris-drift 18s ease-in-out infinite alternate;
}

.black-hole__pixel,
.black-hole__fragment {
  fill: var(--black-hole-muted);
}

.black-hole__fragment {
  font-family: var(--font-mono, 'IBM Plex Mono', 'Cascadia Mono', monospace);
  font-weight: 500;
  text-anchor: middle;
}

.black-hole__parallax {
  transform-box: view-box;
  transform-origin: center;
  transition: transform 720ms cubic-bezier(0.16, 1, 0.3, 1);
  will-change: transform;
}

.black-hole[data-pointer-active='true'] .black-hole__parallax {
  transition-duration: 80ms;
  transition-timing-function: linear;
}

.black-hole__parallax--1 {
  transform: translate3d(var(--parallax-x-1, 0), var(--parallax-y-1, 0), 0);
}

.black-hole__parallax--2 {
  transform: translate3d(var(--parallax-x-2, 0), var(--parallax-y-2, 0), 0);
}

.black-hole__parallax--3 {
  transform: translate3d(var(--parallax-x-3, 0), var(--parallax-y-3, 0), 0);
}

.black-hole__parallax--4 {
  transform: translate3d(var(--parallax-x-4, 0), var(--parallax-y-4, 0), 0);
}

.black-hole__parallax--5 {
  transform: translate3d(var(--parallax-x-5, 0), var(--parallax-y-5, 0), 0);
}

.black-hole__ring,
.black-hole__orbit,
.black-hole__core {
  transform-box: view-box;
  transform-origin: center;
}

.black-hole__orbit {
  animation: orbit-clockwise var(--orbit-duration) linear var(--orbit-phase)
    infinite;
  will-change: transform;
}

.black-hole__guide {
  fill: none;
  stroke: var(--black-hole-muted);
  stroke-width: 0.72;
  stroke-dasharray: 1.5 7;
  opacity: 0.17;
  vector-effect: non-scaling-stroke;
}

.black-hole__orbit-text {
  font-family: var(--font-mono, 'IBM Plex Mono', 'Cascadia Mono', monospace);
  font-weight: 500;
  letter-spacing: 0.075em;
  paint-order: stroke fill;
  stroke: var(--black-hole-surface);
  stroke-width: 0.22;
  stroke-opacity: 0.12;
  text-rendering: geometricPrecision;
}

.black-hole__core {
  filter: drop-shadow(
    0 8px 14px color-mix(in srgb, var(--black-hole-core) 35%, transparent)
  );
}

.black-hole__aura {
  fill: none;
  stroke: var(--black-hole-glow);
  vector-effect: non-scaling-stroke;
}

.black-hole__aura--wide {
  stroke-width: 13;
  opacity: 0.2;
  animation: aura-breathe 5.4s ease-in-out infinite alternate;
}

.black-hole__aura--tight {
  stroke-width: 1.3;
  opacity: 0.58;
}

.black-hole__core-shadow {
  fill: var(--black-hole-core);
  opacity: 0.28;
  transform: translateY(9px);
}

.black-hole__core-disc {
  stroke: var(--black-hole-core);
  stroke-width: 2;
}

.black-hole__core-rim {
  fill: none;
  stroke: var(--black-hole-surface);
  stroke-width: 0.8;
  opacity: 0.2;
  vector-effect: non-scaling-stroke;
}

.black-hole__front-caustic {
  fill: none;
  stroke: var(--black-hole-glow);
  stroke-width: 1.2;
  stroke-linecap: round;
  opacity: 0.44;
  vector-effect: non-scaling-stroke;
}

.black-hole__target {
  position: absolute;
  top: 50%;
  left: 50%;
  width: clamp(3rem, 20%, 8.75rem);
  height: clamp(1.875rem, 13%, 5.5rem);
  pointer-events: none;
  opacity: 0;
  transform: translate(-50%, -50%);
}

.black-hole--dormant .black-hole__well,
.black-hole--dormant .black-hole__debris-field,
.black-hole--dormant .black-hole__ring,
.black-hole--dormant .black-hole__core {
  opacity: 0;
}

.black-hole--dormant .black-hole__ring {
  transform: scale(0.42) rotate(-18deg);
}

.black-hole--dormant .black-hole__core {
  transform: scale(0.12);
}

.black-hole--dormant .black-hole__orbit,
.black-hole--dormant .black-hole__debris-field {
  animation-play-state: paused;
}

.black-hole--forming .black-hole__well {
  animation: well-reveal 800ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

.black-hole--forming .black-hole__core {
  animation: core-form 720ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

.black-hole--forming .black-hole__ring {
  animation: ring-accrete 720ms cubic-bezier(0.16, 1, 0.3, 1)
    var(--reveal-delay) both;
}

.black-hole--forming .black-hole__debris-field {
  animation:
    debris-reveal 620ms cubic-bezier(0.16, 1, 0.3, 1) 500ms both,
    debris-drift 18s ease-in-out 1.2s infinite alternate;
}

.black-hole--paused *,
.black-hole--paused *::before,
.black-hole--paused *::after {
  animation-play-state: paused !important;
}

.black-hole--paused .black-hole__parallax {
  transition: none;
}

.black-hole--reduced .black-hole__debris-field,
.black-hole--reduced .black-hole__orbit,
.black-hole--reduced .black-hole__aura--wide,
.black-hole--reduced.black-hole--forming .black-hole__well,
.black-hole--reduced.black-hole--forming .black-hole__core,
.black-hole--reduced.black-hole--forming .black-hole__ring {
  animation: none;
}

.black-hole--reduced .black-hole__parallax {
  transition: none;
}

@keyframes orbit-clockwise {
  to {
    transform: rotate(1turn);
  }
}

@keyframes ring-accrete {
  from {
    opacity: 0;
    transform: scale(0.48) rotate(-22deg);
  }

  68% {
    opacity: 0.9;
  }

  to {
    opacity: 1;
    transform: scale(1) rotate(0);
  }
}

@keyframes core-form {
  from {
    opacity: 0;
    transform: scale(0.12);
  }

  72% {
    opacity: 1;
    transform: scale(1.06);
  }

  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes well-reveal {
  from {
    opacity: 0;
    transform: scaleX(0.35);
  }

  to {
    opacity: 0.045;
    transform: scaleX(1);
  }
}

@keyframes debris-reveal {
  from {
    opacity: 0;
    transform: scale(0.84);
  }

  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes debris-drift {
  from {
    transform: translate3d(-1.5px, 1px, 0) rotate(-0.18deg);
  }

  to {
    transform: translate3d(1.5px, -1px, 0) rotate(0.18deg);
  }
}

@keyframes aura-breathe {
  from {
    opacity: 0.13;
  }

  to {
    opacity: 0.24;
  }
}

@media (prefers-reduced-motion: reduce) {
  .black-hole__debris-field,
  .black-hole__orbit,
  .black-hole__aura--wide,
  .black-hole--forming .black-hole__well,
  .black-hole--forming .black-hole__core,
  .black-hole--forming .black-hole__ring {
    animation: none;
  }

  .black-hole__parallax {
    transition: none;
  }
}
</style>
