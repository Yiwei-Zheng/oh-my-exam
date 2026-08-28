<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{
  phrases: readonly string[]
  paused: boolean
  reducedMotion: boolean
}>()

type TypingStage = 'typing' | 'underline' | 'holding' | 'deleting'

const phraseIndex = ref(0)
const visibleCharacters = ref(0)
const stage = ref<TypingStage>('typing')
let timer: number | undefined

const activePhrase = computed(() => props.phrases[phraseIndex.value] ?? '')
const visiblePhrase = computed(() =>
  activePhrase.value.slice(0, visibleCharacters.value),
)
const underlineVisible = computed(
  () => stage.value === 'underline' || stage.value === 'holding',
)

function clearTimer() {
  if (timer !== undefined) {
    window.clearTimeout(timer)
    timer = undefined
  }
}

function schedule(callback: () => void, delay: number) {
  clearTimer()
  timer = window.setTimeout(callback, delay)
}

function typingDelay(character: string) {
  return 55 + (character.charCodeAt(0) % 4) * 10
}

function runStep() {
  if (props.reducedMotion || props.phrases.length === 0) {
    showStaticPhrase()
    return
  }

  if (props.paused) {
    schedule(runStep, 80)
    return
  }

  if (stage.value === 'typing') {
    if (visibleCharacters.value < activePhrase.value.length) {
      const nextCharacter = activePhrase.value[visibleCharacters.value] ?? ' '
      visibleCharacters.value += 1
      schedule(runStep, typingDelay(nextCharacter))
      return
    }

    stage.value = 'underline'
    schedule(runStep, 480)
    return
  }

  if (stage.value === 'underline') {
    stage.value = 'holding'
    schedule(runStep, 1140)
    return
  }

  if (stage.value === 'holding') {
    stage.value = 'deleting'
    schedule(runStep, 160)
    return
  }

  if (visibleCharacters.value > 0) {
    visibleCharacters.value -= 1
    schedule(runStep, 32)
    return
  }

  phraseIndex.value = (phraseIndex.value + 1) % props.phrases.length
  stage.value = 'typing'
  schedule(runStep, 210)
}

function showStaticPhrase() {
  clearTimer()
  phraseIndex.value = 0
  visibleCharacters.value = activePhrase.value.length
  stage.value = 'holding'
}

function restart() {
  clearTimer()
  phraseIndex.value = 0
  visibleCharacters.value = props.reducedMotion ? activePhrase.value.length : 0
  stage.value = props.reducedMotion ? 'holding' : 'typing'
  if (!props.reducedMotion) {
    schedule(runStep, 260)
  }
}

watch(
  () => props.reducedMotion,
  (reducedMotion) => {
    if (reducedMotion) {
      showStaticPhrase()
    } else {
      restart()
    }
  },
)

watch(
  () => props.phrases,
  () => restart(),
)

onMounted(restart)
onBeforeUnmount(clearTimer)
</script>

<template>
  <span
    class="typewriter"
    :class="{
      'typewriter--paused': paused,
      'typewriter--reduced': reducedMotion,
    }"
    aria-hidden="true"
  >
    <span
      class="typewriter__word"
      :class="{ 'typewriter__word--underlined': underlineVisible }"
    >
      {{ visiblePhrase }}
    </span>
    <span
      class="typewriter__cursor"
      :class="`typewriter__cursor--${stage}`"
    />
  </span>
</template>

<style scoped>
.typewriter {
  display: inline-flex;
  min-height: 1.2em;
  align-items: baseline;
  white-space: nowrap;
}

.typewriter__word {
  position: relative;
  display: inline-block;
  min-width: 0.62em;
}

.typewriter__word::after {
  position: absolute;
  right: 0;
  bottom: -0.14em;
  left: 0;
  height: max(2px, 0.045em);
  content: '';
  background: currentColor;
  transform: scaleX(0);
  transform-origin: left center;
}

.typewriter__word--underlined::after {
  animation: underline-reveal 480ms var(--ease-out-expo) both;
}

.typewriter__cursor {
  display: inline-block;
  width: max(2px, 0.045em);
  height: 0.92em;
  margin-left: 0.12em;
  background: currentColor;
  transform: translateY(0.08em);
}

.typewriter__cursor--holding {
  animation: cursor-blink 380ms step-end infinite;
}

.typewriter--paused .typewriter__cursor,
.typewriter--paused .typewriter__word::after {
  animation-play-state: paused;
}

.typewriter--reduced .typewriter__cursor {
  display: none;
}

@keyframes cursor-blink {
  50% {
    opacity: 0;
  }
}

@keyframes underline-reveal {
  from {
    transform: scaleX(0);
  }

  to {
    transform: scaleX(1);
  }
}
</style>
