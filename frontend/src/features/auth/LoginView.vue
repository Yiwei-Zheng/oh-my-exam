<script setup lang="ts">
import { ArrowRight, Hide, View } from '@element-plus/icons-vue'
import { ElButton, ElIcon, ElInput } from 'element-plus'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { ApiError, apiRequest } from '../../shared/api'
import { useLocale } from '../../shared/composables/useLocale'
import { useAuthStore } from '../../stores/auth'

const { t } = useI18n()
const { locale, toggleLocale } = useLocale()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const email = ref('')
const password = ref('')
const invitationCode = ref('')
const mode = ref<'login' | 'register'>('login')
const showPassword = ref(false)
const loading = ref(false)
const error = ref('')
const canSubmit = computed(
  () =>
    email.value.trim().includes('@') &&
    (mode.value === 'login'
      ? password.value.length > 0
      : password.value.length >= 15) &&
    (mode.value === 'login' || invitationCode.value.trim().length >= 8),
)

async function submit() {
  if (!canSubmit.value || loading.value) return
  error.value = ''
  loading.value = true
  try {
    if (mode.value === 'register') {
      await apiRequest('/api/v1/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          email: email.value.trim(),
          password: password.value,
          invitation_code: invitationCode.value.trim(),
        }),
      })
    }
    const user = await auth.login(email.value.trim(), password.value)
    const fallback = user.role === 'admin' ? '/admin' : '/questions'
    const destination =
      typeof route.query.redirect === 'string' ? route.query.redirect : fallback
    await router.replace(destination)
  } catch (caught) {
    if (
      caught instanceof ApiError &&
      caught.detail === 'invalid_or_expired_invitation'
    ) {
      error.value = t('auth.invalidInvitation')
    } else if (
      caught instanceof ApiError &&
      caught.detail === 'email_already_exists'
    ) {
      error.value = t('auth.emailExists')
    } else if (caught instanceof ApiError && caught.status === 401) {
      error.value = t('auth.invalidCredentials')
    } else if (caught instanceof ApiError && caught.status === 429) {
      error.value = t('auth.rateLimited')
    } else {
      error.value = t('auth.unavailable')
    }
  } finally {
    loading.value = false
  }
}

function toggleMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  error.value = ''
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
        QUESTION INTELLIGENCE / STEM
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
        ACCESS NODE
      </p>
      <h2 id="login-title">
        {{ mode === 'login' ? t('auth.title') : t('auth.registerTitle') }}
      </h2>
      <p class="login-note">
        {{
          mode === 'login'
            ? t('auth.registrationClosed')
            : t('auth.registrationHint')
        }}
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
        <template v-if="mode === 'register'">
          <label for="invitation-code">{{ t('auth.invitationCode') }}</label>
          <el-input
            id="invitation-code"
            v-model.trim="invitationCode"
            autocomplete="one-time-code"
            size="large"
            placeholder="OME-XXXXXX-XXXXXX-XXXXXX"
          />
          <p class="field-hint">
            {{ t('auth.passwordRule') }}
          </p>
        </template>
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
          {{ mode === 'login' ? t('auth.signIn') : t('auth.createAccount')
          }}<el-icon class="el-icon--right">
            <ArrowRight />
          </el-icon>
        </el-button>
        <button
          class="mode-switch"
          type="button"
          @click="toggleMode"
        >
          {{
            mode === 'login' ? t('auth.useInvitation') : t('auth.backToLogin')
          }}
        </button>
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
  background-color: var(--color-bg);
  background-image:
    linear-gradient(rgba(32, 55, 82, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(32, 55, 82, 0.045) 1px, transparent 1px);
  background-size: 32px 32px;
  position: relative;
  overflow: hidden;
}
.language-pill {
  position: absolute;
  top: 24px;
  right: 24px;
  z-index: 2;
  width: 48px;
  height: 48px;
  border: 1px solid var(--color-line);
  border-radius: 10px;
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
  border-radius: 24%;
  filter: grayscale(0.15) drop-shadow(0 16px 24px rgba(20, 32, 48, 0.14));
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
  border: 1px solid var(--color-line);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--color-muted);
  font: 700 12px var(--font-utility);
}
.login-card {
  position: relative;
  z-index: 1;
  padding: clamp(28px, 5vw, 56px);
  border: 1px solid var(--color-line);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 24px 70px rgba(20, 32, 48, 0.1);
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
  border-radius: 2px;
  background: var(--color-line);
}
.paper-tabs span:nth-child(2) {
  background: var(--color-line-strong);
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
.field-hint {
  margin: 0;
  color: var(--color-muted);
  font-size: 13px;
}
.mode-switch {
  min-height: 44px;
  border: 0;
  background: transparent;
  color: var(--color-blue-dark);
  font-weight: 650;
  cursor: pointer;
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
