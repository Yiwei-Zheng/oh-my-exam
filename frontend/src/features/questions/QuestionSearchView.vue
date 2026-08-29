<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { apiRequest } from '../../shared/api'
import { useLocale } from '../../shared/composables/useLocale'
import { useAuthStore } from '../../stores/auth'

interface Exam {
  id: string
  display_name: string
  course_code: string
  question_count: number
}

interface Question {
  id: number
  exam_id?: string
  paper_key: string
  question_number: string
  local_key: string
  content: string
  topics?: string[]
  score?: number
  shared_topics?: string[]
}

const { t } = useI18n()
const { locale, toggleLocale } = useLocale()
const auth = useAuthStore()
const router = useRouter()
const exams = ref<Exam[]>([])
const query = ref('')
const examId = ref('')
const results = ref<Question[]>([])
const selected = ref<Question | null>(null)
const similar = ref<Question[]>([])
const loading = ref(false)
const detailLoading = ref(false)
const searched = ref(false)
const error = ref('')

const selectedExamId = computed(() => selected.value?.exam_id || examId.value)
const questionPdf = computed(() => {
  if (!selected.value || !selectedExamId.value) return ''
  return `/api/v1/exams/${encodeURIComponent(selectedExamId.value)}/questions/${selected.value.id}/question.pdf`
})

onMounted(async () => {
  try {
    exams.value = await apiRequest<Exam[]>('/api/v1/exams')
  } catch {
    error.value = t('questions.loadFailed')
  }
})

async function search() {
  if (!query.value.trim() || loading.value) return
  loading.value = true
  searched.value = true
  error.value = ''
  selected.value = null
  similar.value = []
  try {
    const parameters = new URLSearchParams({ query: query.value.trim(), limit: '50' })
    if (examId.value) parameters.set('exam_id', examId.value)
    results.value = await apiRequest<Question[]>(`/api/v1/questions/search?${parameters}`)
  } catch {
    results.value = []
    error.value = t('questions.loadFailed')
  } finally {
    loading.value = false
  }
}

async function selectQuestion(question: Question) {
  const resolvedExamId = question.exam_id || examId.value
  if (!resolvedExamId) return
  selected.value = question
  similar.value = []
  detailLoading.value = true
  try {
    similar.value = await apiRequest<Question[]>(
      `/api/v1/exams/${encodeURIComponent(resolvedExamId)}/questions/${question.id}/similar?limit=8`,
    )
  } catch {
    error.value = t('questions.loadFailed')
  } finally {
    detailLoading.value = false
  }
}

async function signOut() {
  await auth.logout()
  await router.replace('/login')
}

function matchPercent(score = 0) {
  return Math.round(Math.max(0, Math.min(1, score)) * 100)
}
</script>

<template>
  <div class="question-workspace">
    <header class="topbar">
      <RouterLink
        class="brand"
        to="/questions"
      >
        OH MY EXAM <span>/ FIND</span>
      </RouterLink>
      <nav :aria-label="t('questions.title')">
        <RouterLink
          v-if="auth.user?.role === 'admin'"
          to="/admin"
        >
          {{ t('questions.admin') }}
        </RouterLink>
        <button
          type="button"
          @click="toggleLocale"
        >
          {{ locale === 'zh-CN' ? 'EN' : '中' }}
        </button>
        <button
          type="button"
          @click="signOut"
        >
          {{ t('questions.signOut') }}
        </button>
      </nav>
    </header>

    <main tabindex="-1">
      <section
        class="search-stage"
        aria-labelledby="search-title"
      >
        <p class="eyebrow">
          {{ t('questions.eyebrow') }}
        </p>
        <h1 id="search-title">
          {{ t('questions.title') }}
        </h1>
        <p class="subtitle">
          {{ t('questions.subtitle') }}
        </p>
        <form
          class="search-form"
          @submit.prevent="search"
        >
          <div class="query-field">
            <label for="question-query">{{ t('questions.searchLabel') }}</label>
            <input
              id="question-query"
              v-model="query"
              type="search"
              :placeholder="t('questions.searchPlaceholder')"
              autocomplete="off"
            >
          </div>
          <div class="exam-field">
            <label for="question-exam">{{ t('questions.examLabel') }}</label>
            <select
              id="question-exam"
              v-model="examId"
            >
              <option value="">
                {{ t('questions.allExams') }}
              </option>
              <option
                v-for="exam in exams"
                :key="exam.id"
                :value="exam.id"
              >
                {{ exam.display_name }} · {{ exam.course_code }}
              </option>
            </select>
          </div>
          <button
            class="search-button"
            type="submit"
            :disabled="!query.trim() || loading"
          >
            {{ loading ? t('questions.searching') : t('questions.search') }}
          </button>
        </form>
        <p
          v-if="error"
          class="error"
          role="alert"
        >
          {{ error }}
        </p>
      </section>

      <section class="work-grid">
        <aside
          class="results-pane"
          aria-live="polite"
        >
          <div class="pane-heading">
            <h2>{{ searched ? t('questions.results', { count: results.length }) : t('questions.eyebrow') }}</h2>
          </div>
          <p
            v-if="!searched"
            class="empty"
          >
            {{ t('questions.startHint') }}
          </p>
          <p
            v-else-if="!results.length && !loading"
            class="empty"
          >
            {{ t('questions.noResults') }}
          </p>
          <ol
            v-else
            class="result-list"
          >
            <li
              v-for="item in results"
              :key="item.id"
              v-memo="[item.id, selected?.id]"
            >
              <button
                type="button"
                :class="{ selected: selected?.id === item.id }"
                :aria-pressed="selected?.id === item.id"
                @click="selectQuestion(item)"
              >
                <span class="result-meta">{{ item.paper_key }} · {{ t('questions.question', { number: item.question_number || item.local_key }) }}</span>
                <span class="result-copy">{{ item.content || item.local_key }}</span>
                <span
                  v-if="item.topics?.length"
                  class="tags"
                >
                  <span
                    v-for="topic in item.topics.slice(0, 3)"
                    :key="topic"
                  >{{ topic }}</span>
                </span>
              </button>
            </li>
          </ol>
        </aside>

        <section
          class="question-pane"
          aria-live="polite"
        >
          <div
            v-if="!selected"
            class="question-empty"
          >
            <span aria-hidden="true">f(x) → ?</span>
            <p>{{ t('questions.selectHint') }}</p>
          </div>
          <template v-else>
            <div class="question-heading">
              <div>
                <p>{{ selected.paper_key }}</p>
                <h2>{{ t('questions.question', { number: selected.question_number || selected.local_key }) }}</h2>
              </div>
              <a
                :href="questionPdf"
                target="_blank"
                rel="noopener"
              >{{ t('questions.openPdf') }}</a>
            </div>
            <iframe
              :key="questionPdf"
              class="question-pdf"
              :src="questionPdf"
              :title="t('questions.preview')"
            />
            <section
              class="similar-section"
              aria-labelledby="similar-title"
            >
              <div class="similar-heading">
                <div>
                  <h2 id="similar-title">
                    {{ t('questions.similar') }}
                  </h2>
                  <p>{{ t('questions.similarHint') }}</p>
                </div>
              </div>
              <p
                v-if="detailLoading"
                class="empty"
              >
                {{ t('questions.searching') }}
              </p>
              <p
                v-else-if="!similar.length"
                class="empty"
              >
                {{ t('questions.noSimilar') }}
              </p>
              <ol
                v-else
                class="similar-list"
              >
                <li
                  v-for="item in similar"
                  :key="item.id"
                >
                  <button
                    type="button"
                    @click="selectQuestion({ ...item, exam_id: selectedExamId })"
                  >
                    <span><strong>{{ item.paper_key }}</strong> · {{ item.question_number }}</span>
                    <span class="match">{{ t('questions.score', { score: matchPercent(item.score) }) }}</span>
                    <small>{{ item.shared_topics?.join(' · ') }}</small>
                  </button>
                </li>
              </ol>
            </section>
          </template>
        </section>
      </section>
    </main>
  </div>
</template>

<style scoped>
.question-workspace {
  --search-navy: #17233f;
  --search-blue: #0071e3;
  --search-cyan: #dff5ff;
  min-height: 100dvh;
  background: linear-gradient(180deg, #eef8ff 0, var(--color-bg) 32rem);
}
.topbar { min-height: 64px; padding: 0 4vw; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(23, 35, 63, .12); background: rgba(255,255,255,.78); backdrop-filter: blur(18px); }
.brand { color: var(--search-navy); font: 700 14px/1 var(--font-utility); letter-spacing: .08em; text-decoration: none; }
.brand span { color: var(--search-blue); }
.topbar nav { display: flex; align-items: center; gap: 8px; }
.topbar nav a, .topbar nav button { min-height: 44px; padding: 0 14px; border: 0; border-radius: 12px; color: var(--search-navy); background: transparent; text-decoration: none; cursor: pointer; }
.topbar nav a:hover, .topbar nav button:hover { background: #e8f2ff; }
main { width: min(1440px, 100%); margin: 0 auto; padding: 48px 4vw 72px; }
.search-stage { position: relative; max-width: 1040px; }
.search-stage::after { content: '∫  Σ  π'; position: absolute; right: 0; top: -24px; color: rgba(0,113,227,.09); font: 700 clamp(64px, 9vw, 132px)/1 Georgia, serif; pointer-events: none; }
.eyebrow { margin: 0 0 12px; color: var(--search-blue); font: 700 12px/1 var(--font-utility); letter-spacing: .12em; }
h1 { position: relative; max-width: 780px; margin: 0; color: var(--search-navy); font-size: clamp(36px, 5vw, 72px); line-height: .98; letter-spacing: -.055em; }
.subtitle { position: relative; max-width: 680px; margin: 20px 0 32px; color: #526078; font-size: 18px; }
.search-form { position: relative; display: grid; grid-template-columns: minmax(280px, 1fr) minmax(180px, 260px) auto; gap: 12px; align-items: end; padding: 12px; border: 1px solid rgba(0,113,227,.18); border-radius: 20px; background: var(--color-paper); box-shadow: 0 18px 55px rgba(23,35,63,.1); }
.search-form label { display: block; margin: 0 0 6px 4px; color: #526078; font-size: 13px; font-weight: 600; }
.search-form input, .search-form select { width: 100%; min-height: 50px; padding: 0 14px; border: 1px solid var(--color-line); border-radius: 12px; color: var(--search-navy); background: #fff; font-size: 16px; }
.search-button { min-height: 50px; padding: 0 22px; border: 0; border-radius: 12px; color: #fff; background: var(--search-blue); font-weight: 700; cursor: pointer; }
.search-button:disabled { opacity: .45; cursor: not-allowed; }
.error { color: var(--color-danger); }
.work-grid { display: grid; grid-template-columns: minmax(300px, 430px) minmax(0, 1fr); gap: 24px; margin-top: 48px; align-items: start; }
.results-pane, .question-pane { border: 1px solid rgba(23,35,63,.12); border-radius: 20px; background: rgba(255,255,255,.94); box-shadow: 0 12px 36px rgba(23,35,63,.07); overflow: hidden; }
.pane-heading, .question-heading, .similar-heading { padding: 20px 24px; border-bottom: 1px solid #e8ebf0; }
.pane-heading h2, .question-heading h2, .similar-heading h2 { margin: 0; color: var(--search-navy); font-size: 19px; }
.empty { margin: 0; padding: 32px 24px; color: #68758c; }
.result-list, .similar-list { margin: 0; padding: 0; list-style: none; }
.result-list { max-height: 70dvh; overflow-y: auto; }
.result-list button, .similar-list button { width: 100%; padding: 18px 24px; border: 0; border-bottom: 1px solid #edf0f4; color: var(--search-navy); background: transparent; text-align: left; cursor: pointer; transition: background .2s ease; }
.result-list button:hover, .result-list button.selected, .similar-list button:hover { background: #edf7ff; }
.result-list button.selected { box-shadow: 4px 0 0 var(--search-blue) inset; }
.result-meta { display: block; margin-bottom: 8px; color: var(--search-blue); font: 600 12px/1.3 var(--font-utility); }
.result-copy { display: -webkit-box; overflow: hidden; color: #3f4b61; line-height: 1.5; -webkit-box-orient: vertical; -webkit-line-clamp: 3; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
.tags span { padding: 3px 8px; border-radius: 999px; color: #174a70; background: var(--search-cyan); font-size: 11px; }
.question-empty { min-height: 520px; display: grid; place-content: center; padding: 40px; color: #68758c; text-align: center; }
.question-empty span { color: rgba(0,113,227,.16); font: 700 clamp(48px, 8vw, 96px)/1 Georgia, serif; }
.question-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.question-heading p { margin: 0 0 4px; color: var(--search-blue); font: 600 12px/1 var(--font-utility); }
.question-heading a { min-height: 44px; display: inline-flex; align-items: center; padding: 0 14px; border-radius: 12px; color: var(--search-blue); background: #edf7ff; text-decoration: none; }
.question-pdf { width: 100%; min-height: 480px; border: 0; background: #f2f4f7; }
.similar-section { border-top: 1px solid #e8ebf0; }
.similar-heading p { margin: 5px 0 0; color: #68758c; font-size: 14px; }
.similar-list button { display: grid; grid-template-columns: 1fr auto; gap: 6px 12px; }
.similar-list small { grid-column: 1 / -1; color: #68758c; }
.match { color: #17643b; font-size: 13px; font-weight: 700; }
@media (max-width: 820px) {
  main { padding-top: 32px; }
  .search-stage::after { display: none; }
  .search-form { grid-template-columns: 1fr; }
  .work-grid { grid-template-columns: 1fr; }
  .result-list { max-height: none; }
  .question-pdf { min-height: 58dvh; }
}
@media (max-width: 520px) {
  .topbar { padding: 0 16px; }
  .topbar nav a { display: none; }
  .topbar nav a, .topbar nav button { padding: 0 9px; }
  main { padding-inline: 16px; }
  h1 { font-size: 42px; }
  .subtitle { font-size: 16px; }
  .work-grid { margin-top: 32px; }
  .question-heading { align-items: flex-start; }
}
</style>
