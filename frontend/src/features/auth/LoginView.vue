<script setup lang="ts">
import { ArrowRight, Hide, View } from '@element-plus/icons-vue'
import { ElButton, ElIcon, ElInput } from 'element-plus'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '../../shared/api'
import { useLocale } from '../../shared/composables/useLocale'
import { useAuthStore } from '../../stores/auth'

const { t } = useI18n()
const { locale, toggleLocale } = useLocale()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const email = ref('')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const error = ref('')
const canSubmit = computed(
  () => email.value.trim().includes('@') && password.value.length > 0,
)

async function submit() {
  if (!canSubmit.value || loading.value) return
  error.value = ''
  loading.value = true
  try {
    const user = await auth.login(email.value.trim(), password.value)
    const destination =
      typeof route.query.redirect === 'string' ? route.query.redirect : '/admin'
    await router.replace(user.role === 'admin' ? destination : '/login')
  } catch (caught) {
    error.value =
      caught instanceof ApiError && caught.status === 401
        ? t('auth.invalidCredentials')
        : t('auth.unavailable')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main
    class="login-page"
    tabindex="-1"
  >
    <button
      class="language-pill"
      type="button"
      @click="toggleLocale"
    >
      {{ locale === 'zh-CN' ? 'EN' : '中' }}
      <span class="sr-only">{{ t('controls.switchLanguage') }}</span>
    </button>

    <section
      class="login-intro"
      aria-labelledby="product-title"
    >
      <img
        class="app-icon"
        src="/app-icon.png"
        alt="Oh My Exam question paper icon"
        width="220"
        height="220"
      >
      <p class="eyebrow">
        A LEVEL · UK ADMISSIONS
      </p>
      <h1 id="product-title">
        Oh My Exam
      </h1>
      <p>{{ t('auth.intro') }}</p>
      <div
        class="subject-chips"
        aria-hidden="true"
      >
        <span>CAIE</span><span>STEP</span><span>TMUA</span><span>PAT</span>
      </div>
    </section>

    <section
      class="login-card"
      aria-labelledby="login-title"
    >
      <div
        class="paper-tabs"
        aria-hidden="true"
      >
        <span /><span /><span />
      </div>
      <p class="section-index">
        ACCESS / 01
      </p>
      <h2 id="login-title">
        {{ t('auth.title') }}
      </h2>
      <p class="login-note">
        {{ t('auth.registrationClosed') }}
      </p>
      <form @submit.prevent="submit">
        <label for="email">{{ t('auth.email') }}</label>
        <el-input
          id="email"
          v-model.trim="email"
          type="email"
          autocomplete="username"
          size="large"
        />
        <label for="password">{{ t('auth.password') }}</label>
        <el-input
          id="password"
          v-model="password"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="current-password"
          size="large"
          @keyup.enter="submit"
        >
          <template #suffix>
            <button
              class="password-toggle"
              type="button"
              :aria-label="t('auth.togglePassword')"
              @click="showPassword = !showPassword"
            >
              <el-icon><component :is="showPassword ? Hide : View" /></el-icon>
            </button>
          </template>
        </el-input>
        <p
          v-if="error"
          class="form-error"
          role="alert"
        >
          {{ error }}
        </p>
        <el-button
          class="login-button"
          type="primary"
          native-type="submit"
          size="large"
          :loading="loading"
          :disabled="!canSubmit"
        >
          {{ t('auth.signIn')
          }}<el-icon class="el-icon--right">
            <ArrowRight />
          </el-icon>
        </el-button>
      </form>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100dvh;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 520px);
  align-items: center;
  gap: clamp(32px, 7vw, 112px);
  padding: clamp(24px, 5vw, 80px);
  background:
    radial-gradient(circle at 14% 18%, #dfeaff 0, transparent 32%),
    var(--color-bg);
  position: relative;
  overflow: hidden;
}
.login-page::after {
  content: '';
  position: absolute;
  width: 380px;
  height: 380px;
  right: -160px;
  bottom: -180px;
  border-radius: 50%;
  background: #ffd75c;
  opacity: 0.45;
}
.language-pill {
  position: absolute;
  top: 24px;
  right: 24px;
  z-index: 2;
  width: 48px;
  height: 48px;
  border: 1px solid var(--color-line);
  border-radius: 16px;
  background: #fff;
  color: var(--color-ink);
  font: 700 14px var(--font-utility);
  cursor: pointer;
}
.login-intro {
  max-width: 600px;
  position: relative;
  z-index: 1;
}
.app-icon {
  width: clamp(136px, 18vw, 220px);
  height: auto;
  border-radius: 28%;
  filter: drop-shadow(0 18px 24px rgba(43, 88, 164, 0.18));
}
.eyebrow,
.section-index {
  margin: 28px 0 10px;
  color: var(--color-blue-dark);
  font: 700 12px/1.4 var(--font-utility);
  letter-spacing: 0.12em;
}
h1 {
  margin: 0;
  font-size: clamp(48px, 7vw, 92px);
  line-height: 0.92;
  letter-spacing: -0.075em;
  color: var(--color-ink);
}
.login-intro > p:not(.eyebrow) {
  max-width: 540px;
  margin: 24px 0;
  font-size: clamp(18px, 2vw, 24px);
  color: var(--color-muted);
}
.subject-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.subject-chips span {
  padding: 8px 12px;
  border: 1px solid #b9cdf3;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.65);
  color: #315488;
  font: 700 12px var(--font-utility);
}
.login-card {
  position: relative;
  z-index: 1;
  padding: clamp(28px, 5vw, 56px);
  border: 1px solid var(--color-line);
  border-radius: 32px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 24px 70px rgba(39, 73, 130, 0.14);
}
.paper-tabs {
  position: absolute;
  top: 22px;
  right: 28px;
  display: flex;
  gap: 7px;
}
.paper-tabs span {
  width: 13px;
  height: 13px;
  border-radius: 4px;
  background: var(--color-pink);
}
.paper-tabs span:nth-child(2) {
  background: var(--color-yellow);
}
.paper-tabs span:nth-child(3) {
  background: var(--color-blue);
}
.section-index {
  margin-top: 0;
}
h2 {
  margin: 0;
  font-size: clamp(32px, 4vw, 48px);
  letter-spacing: -0.045em;
}
.login-note {
  margin: 12px 0 30px;
  color: var(--color-muted);
}
form {
  display: grid;
  gap: 10px;
}
label {
  margin-top: 8px;
  font-weight: 650;
}
.password-toggle {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border: 0;
  background: transparent;
  color: var(--color-muted);
  cursor: pointer;
}
.form-error {
  margin: 4px 0 0;
  color: var(--color-danger);
  font-size: 14px;
}
.login-button {
  width: 100%;
  margin-top: 16px;
  min-height: 50px;
  font-weight: 700;
}
@media (max-width: 820px) {
  .login-page {
    grid-template-columns: 1fr;
    align-items: start;
    padding-top: 72px;
    overflow: visible;
  }
  .login-intro {
    text-align: center;
    margin: auto;
  }
  .subject-chips {
    justify-content: center;
  }
  .login-intro > p:not(.eyebrow) {
    margin-inline: auto;
  }
  .app-icon {
    width: 132px;
  }
  .login-card {
    max-width: 520px;
    width: 100%;
    margin: 0 auto 40px;
  }
}
</style>
