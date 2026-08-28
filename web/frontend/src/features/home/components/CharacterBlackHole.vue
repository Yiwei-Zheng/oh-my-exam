<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'

import { ACADEMIC_ORBIT_SEGMENTS } from '@/i18n/invariantContent'

const props = withDefaults(
  defineProps<{
    stage: 'dormant' | 'forming' | 'ready'
    paused: boolean
    reducedMotion: boolean
    compact?: boolean
    label: string
    targetId?: string
  }>(),
  { compact: false, targetId: undefined },
)

const svg = ref<SVGSVGElement>()
const streams = ACADEMIC_ORBIT_SEGMENTS.map((segments, index) => ({
  id: `academic-stream-${index}`,
  text: `${segments.join('  ·  ')}  ·  `.repeat(3),
  duration: `${24 + index * 3}s`,
  begin: `${index * -4.7}s`,
}))

function syncAnimationState() {
  void nextTick(() => {
    const graphic = svg.value
    if (!graphic || typeof graphic.pauseAnimations !== 'function') return

    if (props.paused || props.reducedMotion || props.stage === 'dormant') {
      graphic.pauseAnimations()
    } else {
      graphic.unpauseAnimations()
    }
  })
}

watch(
  () => [props.paused, props.reducedMotion, props.stage],
  syncAnimationState,
)
onMounted(syncAnimationState)
</script>

<template>
  <figure
    class="black-hole"
    :class="[
      `black-hole--${stage}`,
      { 'black-hole--paused': paused, 'black-hole--reduced': reducedMotion },
    ]"
    :data-stage="stage"
    role="img"
    :aria-label="label"
  >
    <svg
      ref="svg"
      class="black-hole__svg"
      viewBox="0 0 900 620"
      aria-hidden="true"
    >
      <defs>
        <radialGradient
          id="hole-core"
          cx="45%"
          cy="40%"
        >
          <stop
            offset="0"
            stop-color="#020306"
          />
          <stop
            offset="72%"
            stop-color="#06070a"
          />
          <stop
            offset="100%"
            stop-color="#000"
          />
        </radialGradient>
        <linearGradient
          id="disk-hot"
          x1="0"
          y1="0"
          x2="1"
          y2="0"
        >
          <stop
            offset="0"
            stop-color="var(--color-hole-hot)"
            stop-opacity="0"
          />
          <stop
            offset=".18"
            stop-color="var(--color-hole-hot)"
            stop-opacity=".72"
          />
          <stop
            offset=".47"
            stop-color="var(--color-hole-white)"
          />
          <stop
            offset=".68"
            stop-color="var(--color-hole-hot)"
            stop-opacity=".9"
          />
          <stop
            offset="1"
            stop-color="var(--color-hole-hot)"
            stop-opacity="0"
          />
        </linearGradient>
        <filter
          id="soft-glow"
          x="-35%"
          y="-70%"
          width="170%"
          height="240%"
          color-interpolation-filters="sRGB"
        >
          <feGaussianBlur stdDeviation="13" />
        </filter>
        <filter
          id="rim-glow"
          x="-40%"
          y="-40%"
          width="180%"
          height="180%"
          color-interpolation-filters="sRGB"
        >
          <feGaussianBlur
            stdDeviation="7"
            result="blur"
          />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <mask id="stream-visibility">
          <rect
            width="900"
            height="620"
            fill="white"
          />
          <ellipse
            cx="450"
            cy="310"
            rx="114"
            ry="111"
            fill="black"
          />
        </mask>
        <path
          id="academic-stream-0"
          d="M120 310 A330 190 0 1 1 780 310 A330 190 0 1 1 120 310"
        />
        <path
          id="academic-stream-1"
          d="M153 310 A297 158 0 1 1 747 310 A297 158 0 1 1 153 310"
        />
        <path
          id="academic-stream-2"
          d="M188 310 A262 130 0 1 1 712 310 A262 130 0 1 1 188 310"
        />
        <path
          id="academic-stream-3"
          d="M220 310 A230 104 0 1 1 680 310 A230 104 0 1 1 220 310"
        />
        <path
          id="academic-stream-4"
          d="M90 310 A360 220 0 1 1 810 310 A360 220 0 1 1 90 310"
        />
      </defs>

      <g
        class="black-hole__system"
        transform="rotate(16 450 310)"
      >
        <ellipse
          class="black-hole__outer-haze"
          cx="450"
          cy="310"
          rx="374"
          ry="142"
        />
        <ellipse
          class="black-hole__rear-disk black-hole__rear-disk--wide"
          cx="450"
          cy="310"
          rx="365"
          ry="70"
        />
        <ellipse
          class="black-hole__rear-disk"
          cx="450"
          cy="310"
          rx="319"
          ry="46"
        />

        <g
          class="black-hole__streams"
          mask="url(#stream-visibility)"
        >
          <text
            v-for="(stream, index) in streams"
            :key="stream.id"
            class="black-hole__stream"
            :class="`black-hole__stream--${index + 1}`"
          >
            <textPath
              :href="`#${stream.id}`"
              startOffset="0%"
            >
              {{ stream.text }}
              <animate
                v-if="!reducedMotion"
                attributeName="startOffset"
                from="0%"
                to="-100%"
                :dur="stream.duration"
                :begin="stream.begin"
                repeatCount="indefinite"
              />
            </textPath>
          </text>
        </g>

        <ellipse
          class="black-hole__lens black-hole__lens--hot"
          cx="450"
          cy="310"
          rx="155"
          ry="151"
        />
        <ellipse
          class="black-hole__lens black-hole__lens--cool"
          cx="450"
          cy="310"
          rx="128"
          ry="126"
        />
        <ellipse
          class="black-hole__core"
          cx="450"
          cy="310"
          rx="114"
          ry="111"
        />
        <path
          class="black-hole__front-glow"
          d="M62 350 Q450 244 838 350"
        />
        <path
          class="black-hole__front-band"
          d="M48 354 Q450 250 852 354"
        />
        <path
          class="black-hole__front-thread"
          d="M73 368 Q450 270 827 368"
        />
      </g>
    </svg>

    <span
      :id="targetId"
      class="black-hole__target"
      aria-hidden="true"
    />
  </figure>
</template>

<style scoped>
.black-hole {
  position: relative;
  width: min(64vw, 900px);
  aspect-ratio: 900 / 620;
  margin: 0;
  color: var(--color-ink);
  contain: layout paint;
}
.black-hole__svg {
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
}
.black-hole__system {
  transition: opacity 620ms ease;
}
.black-hole__outer-haze {
  fill: none;
  stroke: var(--color-hole-hot);
  stroke-width: 40;
  opacity: 0.13;
  filter: url(#soft-glow);
}
.black-hole__rear-disk {
  fill: none;
  stroke: url(#disk-hot);
  stroke-width: 17;
  opacity: 0.66;
  filter: url(#soft-glow);
}
.black-hole__rear-disk--wide {
  stroke-width: 34;
  opacity: 0.28;
}
.black-hole__lens {
  fill: none;
  transform-box: fill-box;
  transform-origin: center;
}
.black-hole__lens--hot {
  stroke: var(--color-hole-hot);
  stroke-width: 22;
  opacity: 0.55;
  filter: url(#soft-glow);
}
.black-hole__lens--cool {
  stroke: var(--color-hole-cool);
  stroke-width: 11;
  opacity: 0.98;
  filter: url(#rim-glow);
}
.black-hole__core {
  fill: url(#hole-core);
}
.black-hole__front-glow,
.black-hole__front-band,
.black-hole__front-thread {
  fill: none;
  stroke-linecap: round;
}
.black-hole__front-glow {
  stroke: var(--color-hole-hot);
  stroke-width: 44;
  opacity: 0.38;
  filter: url(#soft-glow);
}
.black-hole__front-band {
  stroke: url(#disk-hot);
  stroke-width: 15;
  filter: url(#rim-glow);
}
.black-hole__front-thread {
  stroke: var(--color-hole-white);
  stroke-width: 2.6;
  opacity: 0.72;
}
.black-hole__stream {
  fill: var(--color-ink);
  font-size: 14px;
  font-weight: 400;
  letter-spacing: 0.055em;
  opacity: 0.67;
}
.black-hole__stream--2,
.black-hole__stream--4 {
  fill: var(--color-hole-hot);
  opacity: 0.82;
}
.black-hole__stream--3 {
  fill: var(--color-hole-cool);
  opacity: 0.9;
}
.black-hole__target {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 25%;
  aspect-ratio: 1;
  border-radius: 50%;
  transform: translate3d(-50%, -50%, 0);
  pointer-events: none;
}
.black-hole--dormant .black-hole__system {
  opacity: 0;
}
.black-hole--forming .black-hole__system {
  opacity: 1;
}
.black-hole--ready .black-hole__system {
  opacity: 1;
}
.black-hole--forming .black-hole__lens--cool {
  animation: photon-arrival 900ms var(--ease-out-expo) both;
}
.black-hole--ready:not(.black-hole--paused):not(.black-hole--reduced)
  .black-hole__lens--hot {
  animation: lens-breathe 5.8s ease-in-out infinite alternate;
}
@keyframes photon-arrival {
  from {
    opacity: 0;
    scale: 0.52;
  }
  to {
    opacity: 0.98;
    scale: 1;
  }
}
@keyframes lens-breathe {
  from {
    opacity: 0.42;
    scale: 0.985;
  }
  to {
    opacity: 0.68;
    scale: 1.025;
  }
}
@media (max-width: 767px) {
  .black-hole {
    width: min(142vw, 820px);
  }
  .black-hole__stream {
    font-size: 15px;
    opacity: 0.78;
  }
}
@media (prefers-reduced-motion: reduce) {
  .black-hole__system,
  .black-hole__lens {
    transition: none;
    animation: none !important;
  }
}
</style>
