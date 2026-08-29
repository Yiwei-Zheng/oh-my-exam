<script setup lang="ts">
import {
  DataAnalysis,
  Document,
  Refresh,
  Search,
  SwitchButton,
  User,
  UserFilled,
} from '@element-plus/icons-vue'
import {
  ElAlert,
  ElButton,
  ElEmpty,
  ElIcon,
  ElInput,
  ElProgress,
  ElSkeleton,
  ElTree,
} from 'element-plus'
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { ApiError, apiRequest } from '../../shared/api'
import { useLocale } from '../../shared/composables/useLocale'
import { useAuthStore } from '../../stores/auth'
const ActivityChart = defineAsyncComponent(() => import('./components/ActivityChart.vue'))

interface Statistics {
  users_total: number
  active_7d: number
  roles: Record<'admin' | 'student' | 'teacher', number>
  activity: Array<{ date: string; count: number }>
}
interface TreeNode {
  id: string
  label: string
  kind: string
  count?: number
  children: TreeNode[]
}
interface UpdateJob {
  id: number
  status: 'running' | 'completed' | 'failed'
  stage: string
  progress: number
  message: string
  started_at: string
  finished_at: string | null
}

const { t } = useI18n()
const { locale, toggleLocale } = useLocale()
const router = useRouter()
const auth = useAuthStore()
const statistics = ref<Statistics | null>(null)
const tree = ref<TreeNode[]>([])
const treeRef = ref<InstanceType<typeof ElTree>>()
const search = ref('')
const loading = ref(true)
const error = ref('')
const updateConfigured = ref(false)
const updateJob = ref<UpdateJob | null>(null)
let pollTimer: number | undefined

const roleCards = computed(
  () =>
    [
      {
        key: 'student',
        value: statistics.value?.roles.student ?? 0,
        icon: User,
        tone: 'blue',
      },
      {
        key: 'teacher',
        value: statistics.value?.roles.teacher ?? 0,
        icon: UserFilled,
        tone: 'yellow',
      },
      {
        key: 'admin',
        value: statistics.value?.roles.admin ?? 0,
        icon: DataAnalysis,
        tone: 'pink',
      },
    ] as const,
)

async function loadDashboard() {
  loading.value = true
  error.value = ''
  try {
    const [stats, nodes, update] = await Promise.all([
      apiRequest<Statistics>('/api/v1/admin/statistics'),
      apiRequest<TreeNode[]>('/api/v1/admin/question-tree'),
      apiRequest<{ configured: boolean; job: UpdateJob | null }>(
        '/api/v1/admin/question-update',
      ),
    ])
    statistics.value = stats
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

function filterTree(value: string, data: TreeNode) {
  return !value || data.label.toLowerCase().includes(value.toLowerCase())
}
function applyFilter() {
  treeRef.value?.filter(search.value)
}

async function startUpdate() {
  if (!updateConfigured.value || updateJob.value?.status === 'running') return
  try {
    const payload = await apiRequest<{ job: UpdateJob }>(
      '/api/v1/admin/question-update',
      { method: 'POST' },
    )
    updateJob.value = payload.job
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
onMounted(loadDashboard)
onBeforeUnmount(() => {
  if (pollTimer) window.clearTimeout(pollTimer)
})
</script>

<template>
  <div class="admin-shell">
    <aside class="admin-sidebar">
      <div class="brand-lockup">
        <img
          src="/app-icon.png"
          alt=""
          width="52"
          height="52"
        >
        <div><strong>Oh My Exam</strong><span>CONTROL DESK</span></div>
      </div>
      <nav :aria-label="t('admin.navigation')">
        <a
          class="active"
          href="#overview"
        ><el-icon><DataAnalysis /></el-icon>{{ t('admin.overview') }}</a><a href="#questions"><el-icon><Document /></el-icon>{{ t('admin.questionBank') }}</a>
      </nav>
      <div class="sidebar-footer">
        <button
          type="button"
          @click="toggleLocale"
        >
          {{ locale === 'zh-CN' ? 'English' : '中文' }}
        </button><button
          type="button"
          @click="logout"
        >
          <el-icon><SwitchButton /></el-icon>{{ t('admin.signOut') }}
        </button>
      </div>
    </aside>

    <main
      id="overview"
      class="admin-main"
      tabindex="-1"
    >
      <header class="admin-header">
        <div>
          <p class="eyebrow">
            {{ t('admin.eyebrow') }}
          </p>
          <h1>{{ t('admin.title') }}</h1>
          <p>{{ t('admin.welcome', { email: auth.user?.email }) }}</p>
        </div>
        <div class="status-chip">
          <span />{{ t('admin.systemOnline') }}
        </div>
      </header>
      <el-alert
        v-if="error"
        :title="error"
        type="error"
        show-icon
        closable
        @close="error = ''"
      />

      <section
        class="metrics-grid"
        :aria-label="t('admin.userStatistics')"
      >
        <article class="metric-card total">
          <span>{{ t('admin.usersTotal') }}</span><strong>{{ statistics?.users_total ?? '—' }}</strong><small>{{ t('admin.accounts') }}</small>
        </article>
        <article class="metric-card active-users">
          <span>{{ t('admin.active7d') }}</span><strong>{{ statistics?.active_7d ?? '—' }}</strong><small>{{ t('admin.uniqueUsers') }}</small>
        </article>
        <article
          v-for="item in roleCards"
          :key="item.key"
          class="metric-card role-card"
          :class="item.tone"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <div>
            <span>{{ t(`roles.${item.key}`) }}</span><strong>{{ item.value }}</strong>
          </div>
        </article>
      </section>

      <section class="dashboard-grid">
        <article class="panel activity-panel">
          <div class="panel-heading">
            <div>
              <p class="section-index">
                ACTIVITY / 14D
              </p>
              <h2>{{ t('admin.activityTitle') }}</h2>
            </div>
          </div>
          <el-skeleton
            v-if="loading"
            :rows="5"
            animated
          /><template v-else>
            <ActivityChart :data="statistics?.activity ?? []" />
            <table class="sr-only">
              <caption>
                {{
                  t('admin.activityTitle')
                }}
              </caption>
              <tbody>
                <tr
                  v-for="item in statistics?.activity"
                  :key="item.date"
                >
                  <th>{{ item.date }}</th>
                  <td>{{ item.count }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </article>

        <article class="panel update-panel">
          <div class="update-icon">
            <el-icon><Refresh /></el-icon>
          </div>
          <p class="section-index">
            SYNC / PIPELINE
          </p>
          <h2>{{ t('admin.updateTitle') }}</h2>
          <p>{{ t('admin.updateDescription') }}</p>
          <div
            class="pipeline-stages"
            aria-hidden="true"
          >
            <span
              v-for="stage in [
                'checking',
                'downloading',
                'splitting',
                'cataloging',
                'classifying',
              ]"
              :key="stage"
              :class="{
                done:
                  updateJob && ['completed', stage].includes(updateJob.stage),
                current: updateJob?.stage === stage,
              }"
            />
          </div>
          <div
            v-if="updateJob"
            class="job-status"
            aria-live="polite"
          >
            <strong>{{ t(`updateStatus.${updateJob.status}`) }}</strong><span>{{ updateJob.message }}</span><el-progress
              :percentage="updateJob.progress"
              :status="
                updateJob.status === 'failed'
                  ? 'exception'
                  : updateJob.status === 'completed'
                    ? 'success'
                    : undefined
              "
            />
          </div>
          <p
            v-else-if="!updateConfigured"
            class="config-note"
          >
            {{ t('admin.updateNeedsConfig') }}
          </p>
          <el-button
            type="primary"
            size="large"
            :icon="Refresh"
            :loading="updateJob?.status === 'running'"
            :disabled="!updateConfigured"
            @click="startUpdate"
          >
            {{ t('admin.updateButton') }}
          </el-button>
        </article>
      </section>

      <section
        id="questions"
        class="panel question-panel"
      >
        <div class="panel-heading">
          <div>
            <p class="section-index">
              LIBRARY / TREE
            </p>
            <h2>{{ t('admin.questionTree') }}</h2>
          </div>
          <el-input
            v-model="search"
            class="tree-search"
            :placeholder="t('admin.searchQuestions')"
            clearable
            @input="applyFilter"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        <div class="tree-spine">
          <el-empty
            v-if="!loading && tree.length === 0"
            :description="t('admin.noQuestions')"
          /><el-tree
            v-else
            ref="treeRef"
            :data="tree"
            node-key="id"
            :filter-node-method="filterTree"
            :props="{ label: 'label', children: 'children' }"
            :default-expanded-keys="tree.slice(0, 1).map((node) => node.id)"
          >
            <template #default="{ data }">
              <span class="tree-node"><span>{{ data.label }}</span><small v-if="data.count !== undefined">{{ data.count }} {{ t('admin.questions') }}</small></span>
            </template>
          </el-tree>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.admin-shell {
  min-height: 100dvh;
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr);
  background: var(--color-bg);
}
.admin-sidebar {
  position: sticky;
  top: 0;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  padding: 24px 18px;
  background: #163158;
  color: #fff;
}
.brand-lockup {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 6px 28px;
}
.brand-lockup img {
  border-radius: 16px;
}
.brand-lockup strong,
.brand-lockup span {
  display: block;
}
.brand-lockup strong {
  font-size: 17px;
}
.brand-lockup span {
  margin-top: 3px;
  color: #9db8e1;
  font: 700 10px var(--font-utility);
  letter-spacing: 0.12em;
}
nav {
  display: grid;
  gap: 8px;
}
nav a {
  min-height: 48px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 14px;
  border-radius: 14px;
  color: #bad0ef;
  text-decoration: none;
  font-weight: 650;
}
nav a:hover,
nav a.active {
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
}
nav a.active::before {
  content: '';
  width: 4px;
  height: 20px;
  margin-left: -14px;
  border-radius: 0 4px 4px 0;
  background: var(--color-pink);
}
.sidebar-footer {
  margin-top: auto;
  display: grid;
  gap: 4px;
}
.sidebar-footer button {
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  border: 0;
  border-radius: 12px;
  background: transparent;
  color: #bad0ef;
  text-align: left;
  cursor: pointer;
}
.sidebar-footer button:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}
.admin-main {
  min-width: 0;
  padding: clamp(24px, 4vw, 56px);
}
.admin-header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
  margin-bottom: 32px;
}
.eyebrow,
.section-index {
  margin: 0 0 8px;
  color: var(--color-blue-dark);
  font: 700 11px var(--font-utility);
  letter-spacing: 0.12em;
}
.admin-header h1 {
  margin: 0;
  font-size: clamp(36px, 5vw, 64px);
  letter-spacing: -0.055em;
}
.admin-header p:last-child {
  margin: 10px 0 0;
  color: var(--color-muted);
}
.status-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid #cfe0d7;
  border-radius: 999px;
  background: #f5fff9;
  color: #277247;
  font-size: 13px;
  font-weight: 700;
}
.status-chip span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #38a169;
  box-shadow: 0 0 0 4px #dff5e8;
}
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin: 24px 0;
}
.metric-card,
.panel {
  border: 1px solid var(--color-line);
  border-radius: 22px;
  background: #fff;
  box-shadow: 0 9px 28px rgba(52, 83, 132, 0.06);
}
.metric-card {
  min-height: 132px;
  padding: 20px;
}
.metric-card span,
.metric-card small {
  display: block;
  color: var(--color-muted);
}
.metric-card strong {
  display: block;
  margin: 10px 0 2px;
  font: 700 clamp(30px, 3vw, 44px) var(--font-utility);
  color: var(--color-ink);
}
.total {
  background: #2f6fd8;
}
.total span,
.total small,
.total strong {
  color: #fff;
}
.active-users {
  background: #fff5c9;
}
.role-card {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 96px;
}
.role-card .el-icon {
  flex: 0 0 auto;
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: #edf4ff;
  color: var(--color-blue);
  font-size: 20px;
}
.role-card strong {
  margin: 4px 0 0;
  font-size: 28px;
}
.role-card.yellow .el-icon {
  background: #fff4bd;
  color: #a66c00;
}
.role-card.pink .el-icon {
  background: #ffe7ef;
  color: #c43f6a;
}
.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.75fr);
  gap: 18px;
}
.panel {
  padding: 24px;
}
.panel-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
}
.panel h2 {
  margin: 0;
  font-size: 24px;
  letter-spacing: -0.025em;
}
.update-panel {
  position: relative;
  overflow: hidden;
}
.update-panel::after {
  content: '';
  position: absolute;
  right: -30px;
  top: -34px;
  width: 120px;
  height: 120px;
  border-radius: 40px;
  background: #dce9ff;
  transform: rotate(16deg);
}
.update-icon {
  position: relative;
  z-index: 1;
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  margin-bottom: 22px;
  border-radius: 16px;
  background: var(--color-blue);
  color: #fff;
  font-size: 22px;
}
.update-panel > p:not(.section-index):not(.config-note) {
  min-height: 48px;
  color: var(--color-muted);
}
.pipeline-stages {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 6px;
  margin: 22px 0;
}
.pipeline-stages span {
  height: 6px;
  border-radius: 999px;
  background: #e3e9f2;
}
.pipeline-stages .current,
.pipeline-stages .done {
  background: var(--color-blue);
}
.job-status {
  display: grid;
  gap: 6px;
  margin: 12px 0 18px;
}
.job-status span,
.config-note {
  color: var(--color-muted);
  font-size: 13px;
}
.update-panel .el-button {
  width: 100%;
  min-height: 48px;
}
.question-panel {
  margin-top: 18px;
}
.tree-search {
  max-width: 340px;
}
.tree-spine {
  min-height: 280px;
  margin-top: 22px;
  padding: 10px 10px 10px 20px;
  border-left: 5px solid #a9c6f7;
  border-radius: 4px;
}
.tree-node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-right: 8px;
}
.tree-node small {
  color: var(--color-muted);
  font: 600 11px var(--font-utility);
}
@media (max-width: 1100px) {
  .metrics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .metrics-grid .role-card:last-child {
    grid-column: span 2;
  }
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 760px) {
  .admin-shell {
    display: block;
  }
  .admin-sidebar {
    position: static;
    width: 100%;
    height: auto;
    padding: 14px 16px;
    flex-direction: row;
    align-items: center;
    gap: 12px;
  }
  .brand-lockup {
    padding: 0;
  }
  .brand-lockup img {
    width: 44px;
    height: 44px;
  }
  .brand-lockup div {
    display: none;
  }
  nav {
    display: flex;
  }
  nav a {
    min-height: 44px;
    padding: 0 10px;
    font-size: 14px;
  }
  nav a.active::before {
    display: none;
  }
  .sidebar-footer {
    margin: 0 0 0 auto;
    display: flex;
  }
  .sidebar-footer button {
    width: 44px;
    overflow: hidden;
    white-space: nowrap;
    padding: 0 12px;
  }
  .admin-main {
    padding: 24px 16px 40px;
  }
  .admin-header {
    display: block;
  }
  .status-chip {
    width: max-content;
    margin-top: 18px;
  }
  .metrics-grid {
    grid-template-columns: 1fr 1fr;
  }
  .role-card {
    min-height: 88px;
  }
  .metrics-grid .role-card:last-child {
    grid-column: auto;
  }
  .panel-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .tree-search {
    max-width: none;
    width: 100%;
  }
}
@media (max-width: 450px) {
  .metrics-grid {
    grid-template-columns: 1fr;
  }
  .metrics-grid .role-card:last-child {
    grid-column: auto;
  }
  nav a .el-icon {
    display: none;
  }
  .sidebar-footer button:first-child {
    display: none;
  }
}
</style>
