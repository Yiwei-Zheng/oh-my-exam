<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElAlert, ElInput, ElSkeleton, ElTree } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { ApiError, apiRequest } from '../../shared/api'
import { useLocale } from '../../shared/composables/useLocale'
import { useAuthStore } from '../../stores/auth'

interface TreeNode {
  id: string
  label: string
  kind: string
  count?: number
  paper_id?: number
  exam_id?: string
  year?: number
  session?: string
  children: TreeNode[]
}

interface QuestionSummary {
  id: number
  exam_id: string
  paper_id: number
  paper_key: string
  local_key: string
  question_number: string
  content: string
}

interface AnswerStructured {
  version: number
  raw_text: string
  markdown: string
  status: string
}

interface QuestionDetail extends QuestionSummary {
  answer_structured: AnswerStructured | null
}

interface UpdateJob {
  id: number
  status: 'running' | 'completed' | 'failed'
  stage: string
  progress: number
  message: string
}

const { t } = useI18n()
const { locale, toggleLocale } = useLocale()
const router = useRouter()
const auth = useAuthStore()

const tree = ref<TreeNode[]>([])
const treeRef = ref<InstanceType<typeof ElTree>>()
const questions = ref<QuestionSummary[]>([])
const selectedPaper = ref<TreeNode | null>(null)
const selectedQuestion = ref<QuestionDetail | null>(null)
const treeSearch = ref('')
const questionSearch = ref('')
const previewMode = ref<'question' | 'answer' | 'text'>('question')
const loading = ref(true)
const questionsLoading = ref(false)
const error = ref('')
const updateConfigured = ref(false)
const updateJob = ref<UpdateJob | null>(null)
const rawText = ref('')
const markdown = ref('')
const saving = ref(false)
let pollTimer: number | undefined

const visibleQuestions = computed(() => {
  const query = questionSearch.value.trim().toLowerCase()
  if (!query) return questions.value
  return questions.value.filter(
    (item) =>
      item.question_number.toLowerCase().includes(query) ||
      item.content.toLowerCase().includes(query),
  )
})

const questionPdf = computed(() => documentUrl('question'))
const answerPdf = computed(() => documentUrl('answer'))
const fullQuestionPdf = computed(() => paperUrl('question'))
const fullAnswerPdf = computed(() => paperUrl('answer'))

function documentUrl(kind: 'question' | 'answer') {
  const question = selectedQuestion.value
  if (!question) return ''
  return `/api/v1/exams/${encodeURIComponent(question.exam_id)}/questions/${question.id}/${kind}.pdf`
}

function paperUrl(kind: 'question' | 'answer') {
  const paper = selectedPaper.value
  if (!paper?.exam_id || !paper.paper_id) return ''
  return `/api/v1/exams/${encodeURIComponent(paper.exam_id)}/papers/${paper.paper_id}/${kind}`
}

function filterTree(value: string, data: TreeNode) {
  return !value || data.label.toLowerCase().includes(value.toLowerCase())
}

async function loadWorkspace() {
  loading.value = true
  error.value = ''
  try {
    const [nodes, update] = await Promise.all([
      apiRequest<TreeNode[]>('/api/v1/admin/question-tree'),
      apiRequest<{ configured: boolean; job: UpdateJob | null }>(
        '/api/v1/admin/question-update',
      ),
    ])
    tree.value = nodes
    updateConfigured.value = update.configured
    updateJob.value = update.job
    schedulePoll()
  } catch (caught) {
    error.value =
      caught instanceof ApiError ? caught.detail : t('admin.loadFailed')
  } finally {
    loading.value = false
  }
}

async function selectTreeNode(node: TreeNode) {
  if (node.kind !== 'paper' || !node.paper_id) return
  selectedPaper.value = node
  selectedQuestion.value = null
  questionsLoading.value = true
  try {
    questions.value = await apiRequest<QuestionSummary[]>(
      `/api/v1/admin/papers/${node.paper_id}/questions`,
    )
    if (questions.value[0]) await selectQuestion(questions.value[0])
  } catch (caught) {
    error.value =
      caught instanceof ApiError ? caught.detail : t('admin.loadFailed')
  } finally {
    questionsLoading.value = false
  }
}

async function selectQuestion(question: QuestionSummary) {
  previewMode.value = 'question'
  try {
    const detail = await apiRequest<QuestionDetail>(
      `/api/v1/exams/${encodeURIComponent(question.exam_id)}/questions/${question.id}`,
    )
    selectedQuestion.value = { ...detail, exam_id: question.exam_id }
    rawText.value = detail.answer_structured?.raw_text ?? ''
    markdown.value = detail.answer_structured?.markdown ?? ''
  } catch (caught) {
    error.value =
      caught instanceof ApiError ? caught.detail : t('admin.loadFailed')
  }
}

async function saveAnswerRevision() {
  if (!selectedQuestion.value) return
  saving.value = true
  try {
    const result = await apiRequest<{ answer_structured: AnswerStructured }>(
      `/api/v1/admin/questions/${selectedQuestion.value.id}/answer-text`,
      {
        method: 'PATCH',
        body: JSON.stringify({
          raw_text: rawText.value,
          markdown: markdown.value,
        }),
      },
    )
    selectedQuestion.value.answer_structured = result.answer_structured
  } catch (caught) {
    error.value =
      caught instanceof ApiError ? caught.detail : t('admin.saveFailed')
  } finally {
    saving.value = false
  }
}

async function startUpdate() {
  if (!updateConfigured.value || updateJob.value?.status === 'running') return
  try {
    updateJob.value = (
      await apiRequest<{ job: UpdateJob }>('/api/v1/admin/question-update', {
        method: 'POST',
      })
    ).job
    schedulePoll()
  } catch (caught) {
    error.value =
      caught instanceof ApiError ? caught.detail : t('admin.updateFailed')
  }
}

function schedulePoll() {
  if (pollTimer) window.clearTimeout(pollTimer)
  if (updateJob.value?.status !== 'running') return
  pollTimer = window.setTimeout(async () => {
    const payload = await apiRequest<{
      configured: boolean
      job: UpdateJob | null
    }>('/api/v1/admin/question-update')
    updateJob.value = payload.job
    schedulePoll()
  }, 1800)
}

async function logout() {
  await auth.logout()
  await router.replace('/login')
}

onMounted(loadWorkspace)
watch(treeSearch, (value) => treeRef.value?.filter(value))
onBeforeUnmount(() => {
  if (pollTimer) window.clearTimeout(pollTimer)
})
</script>

<template>
  <main class="workspace">
    <header class="toolbar">
      <div
        class="window-mark"
        aria-hidden="true"
      >
        <span /><span /><span />
      </div>
      <img
        src="/app-icon.png"
        alt=""
        width="34"
        height="34"
      >
      <div class="title-block">
        <strong>{{ t('admin.libraryTitle') }}</strong>
        <span>{{ selectedPaper?.label ?? t('admin.librarySubtitle') }}</span>
      </div>
      <div class="toolbar-actions">
        <div
          v-if="updateJob"
          class="job-pill"
          :class="updateJob.status"
        >
          <span>{{ updateJob.message }}</span>
          <small>{{ updateJob.progress }}%</small>
        </div>
        <button
          class="toolbar-button primary"
          type="button"
          :disabled="!updateConfigured || updateJob?.status === 'running'"
          @click="startUpdate"
        >
          {{ t('admin.runPipeline') }}
        </button>
        <button
          class="toolbar-button"
          type="button"
          @click="toggleLocale"
        >
          {{ locale === 'zh-CN' ? 'EN' : '中文' }}
        </button>
        <button
          class="avatar"
          type="button"
          :title="t('admin.signOut')"
          @click="logout"
        >
          {{ auth.user?.email?.slice(0, 1).toUpperCase() ?? 'A' }}
        </button>
      </div>
    </header>

    <el-alert
      v-if="error"
      class="workspace-error"
      :title="error"
      type="error"
      closable
      show-icon
      @close="error = ''"
    />

    <section
      class="browser"
      :aria-label="t('admin.questionTree')"
    >
      <aside class="source-pane">
        <div class="pane-heading">
          <span>{{ t('admin.sources') }}</span><small>{{ tree.length }}</small>
        </div>
        <el-input
          v-model="treeSearch"
          class="pane-search"
          :placeholder="t('admin.searchTree')"
          clearable
        />
        <div class="tree-scroll">
          <el-skeleton
            v-if="loading"
            :rows="8"
            animated
          />
          <el-tree
            v-else
            ref="treeRef"
            :data="tree"
            node-key="id"
            highlight-current
            :filter-node-method="filterTree"
            :props="{ label: 'label', children: 'children' }"
            @node-click="selectTreeNode"
          >
            <template #default="{ data }">
              <span class="tree-row">
                <span
                  class="node-icon"
                  :class="data.kind"
                  aria-hidden="true"
                />
                <span class="node-label">{{ data.label }}</span>
                <small v-if="data.count !== undefined">{{ data.count }}</small>
              </span>
            </template>
          </el-tree>
        </div>
      </aside>

      <aside class="list-pane">
        <div class="pane-heading">
          <span>{{ t('admin.questions') }}</span><small>{{ questions.length }}</small>
        </div>
        <el-input
          v-model="questionSearch"
          class="pane-search"
          :placeholder="t('admin.searchQuestions')"
          clearable
        />
        <div
          class="question-list"
          :class="{ loading: questionsLoading }"
        >
          <button
            v-for="question in visibleQuestions"
            :key="question.id"
            type="button"
            :class="{ selected: selectedQuestion?.id === question.id }"
            @click="selectQuestion(question)"
          >
            <strong>{{
              t('admin.questionNumber', { number: question.question_number })
            }}</strong>
            <span>{{ question.content || question.local_key }}</span>
          </button>
          <div
            v-if="!questionsLoading && !questions.length"
            class="empty-state"
          >
            <strong>{{ t('admin.choosePaper') }}</strong>
            <span>{{ t('admin.choosePaperHint') }}</span>
          </div>
        </div>
      </aside>

      <article class="preview-pane">
        <template v-if="selectedQuestion">
          <div class="preview-toolbar">
            <div
              class="segmented"
              role="tablist"
            >
              <button
                type="button"
                :class="{ active: previewMode === 'question' }"
                @click="previewMode = 'question'"
              >
                {{ t('admin.questionPdf') }}
              </button>
              <button
                type="button"
                :class="{ active: previewMode === 'answer' }"
                @click="previewMode = 'answer'"
              >
                {{ t('admin.answerPdf') }}
              </button>
              <button
                type="button"
                :class="{ active: previewMode === 'text' }"
                @click="previewMode = 'text'"
              >
                {{ t('admin.structuredText') }}
              </button>
            </div>
            <div class="document-links">
              <a
                :href="fullQuestionPdf"
                target="_blank"
              >{{
                t('admin.fullQuestionPaper')
              }}</a>
              <a
                :href="fullAnswerPdf"
                target="_blank"
              >{{
                t('admin.fullAnswerPaper')
              }}</a>
            </div>
          </div>
          <iframe
            v-if="previewMode === 'question'"
            :key="questionPdf"
            :src="questionPdf"
            :title="t('admin.questionPdf')"
          />
          <iframe
            v-else-if="previewMode === 'answer'"
            :key="answerPdf"
            :src="answerPdf"
            :title="t('admin.answerPdf')"
          />
          <div
            v-else
            class="text-editor"
          >
            <div class="editor-heading">
              <div>
                <strong>{{ t('admin.answerRevision') }}</strong>
                <span>{{
                  t('admin.version', {
                    version: selectedQuestion.answer_structured?.version ?? 0,
                  })
                }}</span>
              </div>
              <button
                class="toolbar-button primary"
                type="button"
                :disabled="saving"
                @click="saveAnswerRevision"
              >
                {{ saving ? t('admin.saving') : t('admin.saveRevision') }}
              </button>
            </div>
            <label>{{ t('admin.rawText')
            }}<el-input
              v-model="rawText"
              type="textarea"
              :rows="9"
            /></label>
            <label>{{ t('admin.markdown')
            }}<el-input
              v-model="markdown"
              type="textarea"
              :rows="12"
            /></label>
          </div>
        </template>
        <div
          v-else
          class="preview-empty"
        >
          <div
            class="paper-glyph"
            aria-hidden="true"
          />
          <strong>{{ t('admin.previewTitle') }}</strong>
          <span>{{ t('admin.previewHint') }}</span>
        </div>
      </article>
    </section>
  </main>
</template>

<style scoped>
.workspace {
  min-width: 320px;
  min-height: 100dvh;
  padding: 18px;
  background: #e9eaec;
  color: #1d1d1f;
}
.toolbar {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 14px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-bottom: 0;
  border-radius: 14px 14px 0 0;
  background: rgba(250, 250, 252, 0.84);
  backdrop-filter: blur(24px) saturate(160%);
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.12);
}
.window-mark {
  display: flex;
  gap: 7px;
  margin-right: 5px;
}
.window-mark span {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #ff5f57;
}
.window-mark span:nth-child(2) {
  background: #febc2e;
}
.window-mark span:nth-child(3) {
  background: #28c840;
}
.toolbar img {
  border-radius: 9px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
}
.title-block {
  min-width: 0;
  display: grid;
  line-height: 1.2;
}
.title-block strong {
  font-size: 14px;
}
.title-block span {
  max-width: 44vw;
  overflow: hidden;
  color: #6e6e73;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.toolbar-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}
.toolbar-button,
.avatar {
  min-height: 32px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.8);
  color: #1d1d1f;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.toolbar-button {
  padding: 0 12px;
}
.toolbar-button.primary {
  border-color: #0071e3;
  background: #0071e3;
  color: #fff;
}
.toolbar-button:disabled {
  opacity: 0.46;
  cursor: default;
}
.avatar {
  width: 32px;
  border-radius: 50%;
  background: linear-gradient(#8e8e93, #636366);
  color: white;
}
.job-pill {
  max-width: 220px;
  display: flex;
  gap: 8px;
  padding: 6px 9px;
  border-radius: 8px;
  background: #e8f2ff;
  color: #0066cc;
  font-size: 11px;
}
.job-pill span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.job-pill.failed {
  background: #fff0f0;
  color: #c22323;
}
.workspace-error {
  margin: 0;
  border-radius: 0;
}
.browser {
  height: calc(100dvh - 100px);
  min-height: 560px;
  display: grid;
  grid-template-columns: minmax(240px, 300px) minmax(230px, 290px) minmax(
      440px,
      1fr
    );
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 0 0 14px 14px;
  background: #fff;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.12);
}
.source-pane,
.list-pane {
  min-width: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #d2d2d7;
  background: rgba(246, 246, 248, 0.9);
}
.list-pane {
  background: #fff;
}
.pane-heading {
  height: 38px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  color: #6e6e73;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.pane-heading small {
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.07);
}
.pane-search {
  width: auto;
  margin: 0 10px 9px;
}
.tree-scroll,
.question-list {
  min-height: 0;
  overflow: auto;
  padding: 0 7px 12px;
}
.tree-row {
  min-width: 0;
  width: 100%;
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
}
.node-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tree-row small {
  margin-left: auto;
  color: #8e8e93;
}
.node-icon {
  width: 14px;
  height: 11px;
  flex: 0 0 auto;
  border-radius: 2px;
  background: #5aa7f8;
  box-shadow: inset 0 2px rgba(255, 255, 255, 0.35);
}
.node-icon.paper {
  height: 15px;
  border: 1px solid #b8b8bd;
  background: #fff;
  box-shadow: none;
}
.question-list button {
  width: 100%;
  display: grid;
  gap: 5px;
  padding: 11px 12px;
  border: 0;
  border-bottom: 1px solid #ededf0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.question-list button:hover {
  background: #f5f5f7;
}
.question-list button.selected {
  border-radius: 7px;
  background: #0071e3;
  color: #fff;
}
.question-list button strong {
  font-size: 13px;
}
.question-list button span {
  display: -webkit-box;
  overflow: hidden;
  color: #6e6e73;
  font-size: 11px;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.question-list button.selected span {
  color: rgba(255, 255, 255, 0.78);
}
.empty-state,
.preview-empty {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 7px;
  color: #86868b;
  text-align: center;
}
.empty-state {
  min-height: 220px;
  padding: 20px;
}
.empty-state span,
.preview-empty span {
  max-width: 320px;
  font-size: 12px;
}
.preview-pane {
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #d7d7da;
}
.preview-toolbar {
  min-height: 48px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  border-bottom: 1px solid #c7c7cc;
  background: rgba(246, 246, 248, 0.92);
}
.segmented {
  display: flex;
  padding: 2px;
  border-radius: 8px;
  background: rgba(118, 118, 128, 0.14);
}
.segmented button {
  min-height: 28px;
  padding: 0 11px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #3a3a3c;
  font-size: 11px;
  cursor: pointer;
}
.segmented button.active {
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
}
.document-links {
  display: flex;
  gap: 10px;
}
.document-links a {
  color: #0066cc;
  font-size: 11px;
  text-decoration: none;
}
.preview-pane iframe {
  width: 100%;
  min-height: 0;
  flex: 1;
  border: 0;
  background: #737373;
}
.preview-empty {
  height: 100%;
}
.paper-glyph {
  width: 76px;
  height: 96px;
  border-radius: 7px;
  background: linear-gradient(135deg, #fff 0 78%, #e5e5ea 78%);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.14);
}
.text-editor {
  min-height: 0;
  overflow: auto;
  display: grid;
  gap: 18px;
  padding: clamp(18px, 3vw, 36px);
  background: #f5f5f7;
}
.editor-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.editor-heading div {
  display: grid;
}
.editor-heading span {
  color: #86868b;
  font-size: 11px;
}
.text-editor label {
  display: grid;
  gap: 7px;
  color: #6e6e73;
  font-size: 11px;
  font-weight: 700;
}
@media (max-width: 1050px) {
  .browser {
    grid-template-columns: 240px 250px minmax(420px, 1fr);
    overflow-x: auto;
  }
  .job-pill {
    display: none;
  }
}
@media (max-width: 720px) {
  .workspace {
    padding: 0;
  }
  .toolbar {
    position: sticky;
    top: 0;
    z-index: 2;
    height: auto;
    min-height: 58px;
    border-radius: 0;
  }
  .window-mark,
  .title-block span {
    display: none;
  }
  .toolbar-actions {
    gap: 5px;
  }
  .toolbar-button {
    padding: 0 8px;
  }
  .browser {
    height: auto;
    min-height: calc(100dvh - 58px);
    grid-template-columns: 100%;
    overflow: visible;
    border-radius: 0;
  }
  .source-pane,
  .list-pane {
    min-height: 280px;
    max-height: 46dvh;
    border-right: 0;
    border-bottom: 1px solid #d2d2d7;
  }
  .preview-pane {
    min-height: 70dvh;
  }
  .preview-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
  .document-links {
    width: 100%;
    justify-content: space-between;
  }
  .preview-pane iframe {
    min-height: 62dvh;
  }
}
</style>
