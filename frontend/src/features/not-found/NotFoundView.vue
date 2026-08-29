<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
const { t } = useI18n()
</script>

<template>
  <main
    class="not-found"
    tabindex="-1"
  >
    <img
      src="/app-icon.png"
      alt=""
      width="360"
      height="360"
    >
    <section>
      <p>404 / ARCHIVE GAP</p>
      <h1>{{ t('notFound.title') }}</h1>
      <p>{{ t('notFound.description') }}</p>
      <RouterLink to="/">
        {{ t('notFound.backHome') }}
      </RouterLink>
    </section>
  </main>
</template>

<style scoped>
.not-found {
  min-height: 100dvh;
  display: grid;
  grid-template-columns: minmax(240px, 420px) minmax(280px, 560px);
  place-content: center;
  align-items: center;
  gap: clamp(24px, 7vw, 100px);
  padding: 32px;
  background: var(--color-bg);
}
.not-found img {
  width: 100%;
  height: auto;
  border-radius: 28%;
  filter: drop-shadow(0 20px 30px rgba(37, 84, 160, 0.16));
}
.not-found section > p:first-child {
  color: var(--color-blue-dark);
  font: 700 12px var(--font-utility);
  letter-spacing: 0.12em;
}
.not-found h1 {
  margin: 10px 0;
  font-size: clamp(42px, 6vw, 76px);
  line-height: 1;
  letter-spacing: -0.055em;
}
.not-found section > p:not(:first-child) {
  color: var(--color-muted);
  font-size: 18px;
}
.not-found a {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  margin-top: 16px;
  color: var(--color-blue-dark);
  font-weight: 700;
  text-underline-offset: 5px;
}
@media (max-width: 700px) {
  .not-found {
    grid-template-columns: 1fr;
    text-align: center;
  }
  .not-found img {
    width: min(66vw, 280px);
    justify-self: center;
  }
}
</style>
