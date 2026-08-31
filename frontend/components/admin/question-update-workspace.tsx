'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { HugeiconsIcon } from '@hugeicons/react'
import {
  ArrowRight01Icon,
  Database01Icon,
  PauseIcon,
  PlayIcon,
  RefreshIcon,
  Search01Icon,
} from '@hugeicons/core-free-icons'

import { useLocale } from '@/components/locale-provider'
import { ProductHeader } from '@/components/product-header'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { apiRequest } from '@/lib/api'
import { cn } from '@/lib/utils'

interface WorkflowSubject {
  id: string
  code: string
  name: string
  family: string
  status: 'ready'
}

interface UpdateResource {
  id: string
  subject_id: string
  label: string
  year: number | null
  document_type: string
}

interface ProbeResult {
  resource_count: number
  local_count: number
  new_count: number
  new_resources: UpdateResource[]
  errors: { subject_id: string; message: string }[]
  probed_at: string
}

interface UpdateJob {
  id: number
  status: 'running' | 'completed' | 'failed'
  stage: string
  progress: number
  message: string
  action: PipelineAction
  result: ProbeResult | null
  paused: boolean
  elapsed_seconds: number
  eta_seconds: number | null
}

type PipelineAction =
  'probe' | 'all' | 'download' | 'split' | 'inventory' | 'search'
type PipelineStage = Exclude<PipelineAction, 'all'>
type UpdateMode = 'update' | 'overwrite'

const copy = {
  'zh-CN': {
    eyebrow: '管理后台 / 更新题库',
    title: '更新题库',
    intro:
      '选择科目后一键完成资源嗅探、下载、切题、入库和索引。每一步也可独立更新或覆盖重跑，运行中可随时暂停。',
    back: '返回管理后台',
    choose: '选择科目',
    chooseHint: '勾选本次要检查的科目，可多选。',
    sniff: '嗅探并比较',
    sniffing: '正在嗅探来源…',
    comparison: '嗅探结果',
    found: '来源资源',
    local: '本地已有',
    fresh: '新增资源',
    noNew: '本地已经是最新版本',
    noNewHint:
      '没有发现需要下载的新资源。你仍可以重新运行切题、盘点和索引流程。',
    newFound: '发现可下载的新资源',
    newFoundHint: '确认并发数后开始下载。下载完成后会自动进入后续工作流。',
    concurrency: '流水线并行度',
    concurrencyHint:
      '已按本机逻辑处理器自动设置。范围 1–32，数值越高会并行发现、下载和切分 CIE 资源。',
    start: '下载并进入工作流',
    rerun: '重新盘点并入库',
    backgroundHint: '任务由后端 CLI 在后台运行，启动后可以离开此页。',
    running: '工作流运行中',
    paused: '工作流已暂停',
    complete: '题库更新完成',
    failed: '工作流未完成',
    retry: '重新嗅探',
    currentWork: '当前处理',
    elapsed: '已用时间',
    remaining: '预计剩余',
    estimating: '正在估算',
    pause: '暂停',
    resume: '继续',
    pauseFailed: '未能暂停当前任务，请稍后重试。',
    resumeFailed: '未能继续当前任务，请稍后重试。',
    stageDescriptions: {
      checking: '检查来源和本地资源状态',
      downloading: '发现、下载并校验原始 PDF',
      splitting: '切分题目与答案 JPG',
      cataloging: '盘点资源并写入科目数据库',
      classifying: '建立搜索索引并发布题库',
      completed: '全部处理已经完成',
      failed: '处理已停止，请查看当前信息',
    },
    empty: '请至少选择一个科目',
    unavailable: '更新流水线尚未配置',
    probeFailed: '资源嗅探失败，请检查来源网络后重试。',
    partialProbeFailed: '部分项目嗅探失败，其他项目的结果不受影响。',
    startFailed: '未能启动工作流，请稍后重试。',
    more: '项未展开',
    stages: ['嗅探', '下载', '切题', '盘点入库', '可搜索'],
    stageDetails: [
      '检查远端来源并与本地资源逐项比较',
      '下载并校验所选科目的原始 PDF',
      '重新生成题目与答案图片',
      '扫描本地资源并更新科目数据库',
      '重建分类与全文搜索索引',
    ],
    workflow: '执行步骤',
    stageHint: '每一步都可增量更新或覆盖重跑，也可以一键执行完整流水线。',
    update: '更新',
    overwrite: '覆盖',
    runAll: '一键全部执行',
    overwriteAll: '覆盖全部重跑',
  },
  en: {
    eyebrow: 'Admin / Update library',
    title: 'Update library',
    intro:
      'Select subjects to automate probing, downloading, splitting, inventory, and indexing. Every stage can also be updated or overwritten independently, and paused while running.',
    back: 'Back to admin',
    choose: 'Choose subjects',
    chooseHint: 'Select one or more subjects to inspect.',
    sniff: 'Probe and compare',
    sniffing: 'Probing sources…',
    comparison: 'Probe results',
    found: 'Source resources',
    local: 'Already local',
    fresh: 'New resources',
    noNew: 'The local library is current',
    noNewHint:
      'There is nothing new to download. You can still rerun splitting, inventory, and indexing.',
    newFound: 'New resources are ready to download',
    newFoundHint:
      'Confirm concurrency to begin. The remaining workflow runs automatically after downloading.',
    concurrency: 'Pipeline parallelism',
    concurrencyHint:
      'Automatically matched to this machine. Choose 1–32; higher values parallelize CIE discovery, downloads, and splitting.',
    start: 'Download and continue',
    rerun: 'Rebuild inventory and index',
    backgroundHint:
      'The backend CLI continues in the background, so you can leave after it starts.',
    running: 'Workflow in progress',
    paused: 'Workflow paused',
    complete: 'Library update complete',
    failed: 'Workflow did not complete',
    retry: 'Probe again',
    currentWork: 'Processing now',
    elapsed: 'Elapsed',
    remaining: 'Estimated remaining',
    estimating: 'Estimating',
    pause: 'Pause',
    resume: 'Resume',
    pauseFailed: 'The current task could not be paused. Try again shortly.',
    resumeFailed: 'The current task could not be resumed. Try again shortly.',
    stageDescriptions: {
      checking: 'Checking sources and local resource state',
      downloading: 'Discovering, downloading, and validating source PDFs',
      splitting: 'Splitting question and answer JPGs',
      cataloging: 'Inventorying resources and writing subject databases',
      classifying: 'Building the search index and publishing the library',
      completed: 'All processing is complete',
      failed: 'Processing stopped; review the current details',
    },
    empty: 'Choose at least one subject',
    unavailable: 'The update pipeline is not configured',
    probeFailed:
      'Resource probing failed. Check source connectivity and try again.',
    partialProbeFailed:
      'Some projects could not be probed. Results from other projects are unaffected.',
    startFailed: 'The workflow could not be started. Try again shortly.',
    more: 'more not shown',
    stages: ['Probe', 'Download', 'Split', 'Inventory', 'Searchable'],
    stageDetails: [
      'Compare remote sources with local resources',
      'Download and validate source PDFs for selected subjects',
      'Regenerate question and answer images',
      'Scan local resources and update subject databases',
      'Rebuild classification and full-text search indexes',
    ],
    workflow: 'Workflow stages',
    stageHint:
      'Incrementally update or overwrite any stage, or run the complete pipeline.',
    update: 'Update',
    overwrite: 'Overwrite',
    runAll: 'Run all updates',
    overwriteAll: 'Overwrite and rerun all',
  },
} as const

const stageIndex: Record<string, number> = {
  checking: 0,
  downloading: 1,
  splitting: 2,
  cataloging: 3,
  classifying: 4,
  completed: 4,
}

const actionIndex: Record<PipelineAction, number> = {
  probe: 0,
  all: 4,
  download: 1,
  split: 2,
  inventory: 3,
  search: 4,
}

export function QuestionUpdateWorkspace() {
  const { locale } = useLocale()
  const c = copy[locale]
  const [configured, setConfigured] = useState(true)
  const [subjects, setSubjects] = useState<WorkflowSubject[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [expandedFamilies, setExpandedFamilies] = useState<Set<string>>(
    new Set(),
  )
  const [probe, setProbe] = useState<ProbeResult | null>(null)
  const [job, setJob] = useState<UpdateJob | null>(null)
  const [concurrency, setConcurrency] = useState(4)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    apiRequest<{
      configured: boolean
      recommended_concurrency: number
      workflows: WorkflowSubject[]
      job: UpdateJob | null
    }>('/api/v1/admin/question-update')
      .then((result) => {
        setConfigured(result.configured)
        setConcurrency(result.recommended_concurrency)
        setSubjects(result.workflows)
        setSelected(result.workflows.map((item) => item.id))
        setExpandedFamilies(
          new Set(result.workflows.map((item) => item.family)),
        )
        acceptJob(result.job)
      })
      .catch(() => setError(c.probeFailed))
  }, [c.probeFailed])

  useEffect(() => {
    if (job?.status !== 'running') return
    const timer = window.setInterval(() => {
      apiRequest<{ job: UpdateJob | null }>('/api/v1/admin/question-update')
        .then((result) => acceptJob(result.job))
        .catch(() => undefined)
    }, 1200)
    return () => window.clearInterval(timer)
  }, [job?.status])

  const activeStage = useMemo(() => {
    if (job?.status === 'completed') return actionIndex[job.action] ?? 4
    if (job?.status === 'running') {
      return job.action === 'all'
        ? (stageIndex[job.stage] ?? 0)
        : (actionIndex[job.action] ?? 0)
    }
    if (job?.status === 'failed') return actionIndex[job.action] ?? 0
    if (probe) return 0
    return -1
  }, [job, probe])

  function acceptJob(next: UpdateJob | null) {
    setJob(next)
    if (next?.action === 'probe' && next.result) setProbe(next.result)
  }

  function toggleSubject(id: string) {
    if (busy || job?.status === 'running') return
    setSelected((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    )
    setProbe(null)
    setError('')
  }

  function toggleFamily(ids: string[]) {
    if (busy || job?.status === 'running') return
    setSelected((current) => {
      const allSelected = ids.every((id) => current.includes(id))
      return allSelected
        ? current.filter((id) => !ids.includes(id))
        : [...new Set([...current, ...ids])]
    })
    setProbe(null)
    setError('')
  }

  async function sniff(mode: UpdateMode = 'update') {
    if (!selected.length) {
      setError(c.empty)
      return
    }
    setBusy(true)
    setError('')
    if (mode === 'overwrite') setProbe(null)
    try {
      const result = await apiRequest<{ job: UpdateJob }>(
        '/api/v1/admin/question-update/probe',
        {
          method: 'POST',
          body: JSON.stringify({ subjects: selected }),
        },
      )
      acceptJob(result.job)
    } catch {
      setError(c.probeFailed)
    } finally {
      setBusy(false)
    }
  }

  async function start(
    stage: Exclude<PipelineAction, 'probe'> = 'all',
    mode: UpdateMode = 'update',
  ) {
    if (!selected.length) {
      setError(c.empty)
      return
    }
    setBusy(true)
    setError('')
    try {
      const result = await apiRequest<{ job: UpdateJob }>(
        '/api/v1/admin/question-update',
        {
          method: 'POST',
          body: JSON.stringify({
            subjects: selected,
            concurrency,
            stage,
            mode,
          }),
        },
      )
      acceptJob(result.job)
    } catch {
      setError(c.startFailed)
    } finally {
      setBusy(false)
    }
  }

  function runStage(stage: PipelineStage, mode: UpdateMode) {
    if (stage === 'probe') void sniff(mode)
    else void start(stage, mode)
  }

  async function togglePause() {
    if (!job || job.status !== 'running') return
    const nextPaused = !job.paused
    setBusy(true)
    setError('')
    try {
      const result = await apiRequest<{ job: UpdateJob }>(
        `/api/v1/admin/question-update/${job.id}/${nextPaused ? 'pause' : 'resume'}`,
        { method: 'POST' },
      )
      acceptJob(result.job)
    } catch {
      setError(nextPaused ? c.pauseFailed : c.resumeFailed)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-svh bg-background">
      <ProductHeader />
      <main className="update-page-enter mx-auto w-full max-w-7xl px-4 py-6 md:px-8 md:py-10">
        <header className="mb-6 flex flex-wrap items-start justify-between gap-4 border-b pb-6">
          <div className="max-w-2xl">
            <p className="font-mono text-xs font-semibold uppercase tracking-[.18em] text-primary">
              {c.eyebrow}
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-[-.03em] text-balance md:text-4xl">
              {c.title}
            </h1>
            <p className="mt-3 text-sm leading-6 text-muted-foreground md:text-base">
              {c.intro}
            </p>
          </div>
          <Button variant="ghost" render={<Link href="/admin" />}>
            {c.back}
          </Button>
        </header>

        {error && (
          <Alert variant="destructive" className="mb-5">
            <AlertTitle>{error}</AlertTitle>
          </Alert>
        )}
        {!configured && (
          <Alert className="mb-5">
            <AlertTitle>{c.unavailable}</AlertTitle>
          </Alert>
        )}

        {job && (
          <section
            aria-live="polite"
            className="update-card-enter mb-5 rounded-3xl border bg-card p-5 shadow-sm md:p-6"
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold">
                    {job.status === 'completed'
                      ? c.complete
                      : job.status === 'failed'
                        ? c.failed
                        : c.running}
                  </p>
                  {job.paused && <Badge variant="secondary">{c.paused}</Badge>}
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {c.stageDescriptions[
                    job.stage as keyof typeof c.stageDescriptions
                  ] || job.stage}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono text-2xl font-semibold tabular-nums">
                  {job.progress}%
                </span>
                {job.status === 'running' && (
                  <Button
                    variant={job.paused ? 'default' : 'outline'}
                    className="h-11"
                    onClick={() => void togglePause()}
                    disabled={busy}
                  >
                    <HugeiconsIcon
                      icon={job.paused ? PlayIcon : PauseIcon}
                      data-icon="inline-start"
                    />
                    {job.paused ? c.resume : c.pause}
                  </Button>
                )}
              </div>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-transform duration-300 ease-out motion-reduce:transition-none"
                style={{
                  transform: `scaleX(${job.progress / 100})`,
                  transformOrigin: 'left',
                }}
              />
            </div>
            <div className="mt-4 grid gap-2 sm:grid-cols-3">
              <StatusDetail label={c.currentWork} value={job.message} />
              <StatusDetail
                label={c.elapsed}
                value={formatDuration(job.elapsed_seconds, locale)}
              />
              <StatusDetail
                label={c.remaining}
                value={
                  job.status === 'completed'
                    ? '—'
                    : job.paused
                      ? c.paused
                      : job.eta_seconds === null
                        ? c.estimating
                        : formatDuration(job.eta_seconds, locale)
                }
              />
            </div>
            {job.status === 'failed' && (
              <Button
                variant="outline"
                className="mt-4 h-11"
                onClick={() => void sniff('update')}
              >
                {c.retry}
              </Button>
            )}
          </section>
        )}

        <WorkflowStages
          title={c.workflow}
          stages={c.stages}
          details={c.stageDetails}
          active={activeStage}
          failed={job?.status === 'failed'}
          hint={c.stageHint}
          updateLabel={c.update}
          overwriteLabel={c.overwrite}
          runAllLabel={c.runAll}
          overwriteAllLabel={c.overwriteAll}
          concurrencyLabel={c.concurrency}
          concurrencyHint={c.concurrencyHint}
          concurrency={concurrency}
          onConcurrencyChange={setConcurrency}
          disabled={
            busy || !configured || !selected.length || job?.status === 'running'
          }
          onRun={runStage}
          onRunAll={(mode) => void start('all', mode)}
        />

        <section className="mt-5 grid items-start gap-5 lg:grid-cols-[minmax(300px,.9fr)_minmax(0,1.1fr)]">
          <Card
            className="update-card-enter overflow-hidden"
            style={{ animationDelay: '90ms' }}
          >
            <CardContent className="p-5 md:p-6">
              <div className="mb-5 flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">{c.choose}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {c.chooseHint}
                  </p>
                </div>
                <Badge variant="secondary" className="font-mono">
                  {selected.length}/{subjects.length}
                </Badge>
              </div>
              <WorkflowSubjectTree
                subjects={subjects}
                selected={selected}
                expanded={expandedFamilies}
                onToggleExpanded={(family) =>
                  setExpandedFamilies((current) => {
                    const next = new Set(current)
                    if (next.has(family)) next.delete(family)
                    else next.add(family)
                    return next
                  })
                }
                onToggleFamily={toggleFamily}
                onToggleSubject={toggleSubject}
                disabled={busy || job?.status === 'running'}
              />
              <Button
                variant="outline"
                className="mt-5 h-11 w-full"
                onClick={() => void sniff('update')}
                disabled={busy || !configured || job?.status === 'running'}
              >
                <HugeiconsIcon icon={Search01Icon} data-icon="inline-start" />
                {busy && !probe ? c.sniffing : c.sniff}
              </Button>
            </CardContent>
          </Card>

          <Card
            className="update-card-enter overflow-hidden"
            style={{ animationDelay: '150ms' }}
          >
            <CardContent className="p-5 md:p-6">
              <h2 className="text-lg font-semibold">{c.comparison}</h2>
              {!probe ? (
                <div className="grid min-h-72 place-items-center text-center text-sm text-muted-foreground">
                  <div>
                    <HugeiconsIcon
                      icon={RefreshIcon}
                      className={cn(
                        'mx-auto mb-3 size-7',
                        busy && 'animate-spin',
                      )}
                    />
                    <p>{busy ? c.sniffing : c.sniff}</p>
                  </div>
                </div>
              ) : (
                <div className="mt-5 space-y-5">
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      [c.found, probe.resource_count],
                      [c.local, probe.local_count],
                      [c.fresh, probe.new_count],
                    ].map(([label, value]) => (
                      <div
                        key={String(label)}
                        className="rounded-2xl bg-muted/70 p-3"
                      >
                        <p className="font-mono text-2xl font-semibold tabular-nums">
                          {value}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {label}
                        </p>
                      </div>
                    ))}
                  </div>
                  <Alert>
                    <HugeiconsIcon
                      icon={probe.new_count ? RefreshIcon : Database01Icon}
                    />
                    <AlertTitle>
                      {probe.new_count ? c.newFound : c.noNew}
                    </AlertTitle>
                    <AlertDescription>
                      {probe.new_count ? c.newFoundHint : c.noNewHint}
                    </AlertDescription>
                  </Alert>
                  {probe.errors.length > 0 && (
                    <Alert variant="destructive">
                      <AlertTitle>{c.partialProbeFailed}</AlertTitle>
                      <AlertDescription>
                        {probe.errors
                          .map((item) => `${item.subject_id}: ${item.message}`)
                          .join('\n')}
                      </AlertDescription>
                    </Alert>
                  )}
                  {probe.new_resources.length > 0 && (
                    <div className="max-h-44 space-y-1 overflow-y-auto rounded-2xl border p-2">
                      {probe.new_resources.slice(0, 12).map((resource) => (
                        <div
                          key={`${resource.subject_id}:${resource.id}`}
                          className="flex items-center justify-between gap-3 rounded-xl px-3 py-2 text-sm"
                        >
                          <span className="truncate font-mono text-xs">
                            {resource.label}
                          </span>
                          <Badge variant="outline">
                            {resource.document_type.toUpperCase()}
                          </Badge>
                        </div>
                      ))}
                      {probe.new_resources.length > 12 && (
                        <p className="px-3 py-2 text-xs text-muted-foreground">
                          +{probe.new_resources.length - 12} {c.more}
                        </p>
                      )}
                    </div>
                  )}
                  <Button
                    className="h-11 w-full"
                    onClick={() => void start('all', 'update')}
                    disabled={busy || job?.status === 'running'}
                  >
                    <HugeiconsIcon
                      icon={RefreshIcon}
                      data-icon="inline-start"
                    />
                    {probe.new_count ? c.start : c.rerun}
                  </Button>
                  <p className="text-xs leading-5 text-muted-foreground">
                    {c.backgroundHint}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </section>
      </main>
    </div>
  )
}

function StatusDetail({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-2xl bg-muted/55 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 truncate text-sm font-medium" title={value}>
        {value}
      </p>
    </div>
  )
}

function formatDuration(seconds: number, locale: 'zh-CN' | 'en') {
  const roundedMinutes = Math.max(1, Math.round(seconds / 60))
  if (roundedMinutes < 60) {
    return locale === 'zh-CN'
      ? `约 ${roundedMinutes} 分钟`
      : `about ${roundedMinutes} min`
  }
  const hours = Math.floor(roundedMinutes / 60)
  const minutes = roundedMinutes % 60
  return locale === 'zh-CN'
    ? `约 ${hours} 小时${minutes ? ` ${minutes} 分钟` : ''}`
    : `about ${hours} hr${minutes ? ` ${minutes} min` : ''}`
}

function WorkflowSubjectTree({
  subjects,
  selected,
  expanded,
  onToggleExpanded,
  onToggleFamily,
  onToggleSubject,
  disabled,
}: {
  subjects: WorkflowSubject[]
  selected: string[]
  expanded: Set<string>
  onToggleExpanded: (family: string) => void
  onToggleFamily: (ids: string[]) => void
  onToggleSubject: (id: string) => void
  disabled: boolean
}) {
  const families = useMemo(() => {
    const grouped = new Map<string, WorkflowSubject[]>()
    for (const subject of subjects) {
      grouped.set(subject.family, [
        ...(grouped.get(subject.family) || []),
        subject,
      ])
    }
    return [...grouped.entries()]
  }, [subjects])

  return (
    <div
      role="tree"
      className="max-h-[34rem] overflow-y-auto rounded-2xl border"
    >
      {families.map(([family, items]) => {
        const ids = items.map((item) => item.id)
        const selectedCount = ids.filter((id) => selected.includes(id)).length
        const checked = selectedCount === ids.length
        const partial = selectedCount > 0 && !checked
        const isExpanded = expanded.has(family)
        return (
          <div
            key={family}
            role="treeitem"
            aria-expanded={isExpanded}
            aria-selected={partial || checked}
          >
            <div className="flex min-h-12 items-center border-b bg-muted/35 px-2">
              <button
                type="button"
                className="grid size-11 shrink-0 place-items-center rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                onClick={() => onToggleExpanded(family)}
                aria-label={family}
                disabled={disabled}
              >
                <HugeiconsIcon
                  icon={ArrowRight01Icon}
                  className={cn(
                    'size-4 transition-transform duration-200',
                    isExpanded && 'rotate-90',
                  )}
                />
              </button>
              <label className="flex min-h-11 min-w-0 flex-1 cursor-pointer items-center gap-3 px-2 font-semibold">
                <input
                  type="checkbox"
                  checked={checked}
                  ref={(element) => {
                    if (element) element.indeterminate = partial
                  }}
                  onChange={() => onToggleFamily(ids)}
                  disabled={disabled}
                  className="size-5 accent-[var(--primary)]"
                />
                <span className="min-w-0 flex-1 truncate">{family}</span>
                <Badge variant="secondary" className="font-mono">
                  {selectedCount}/{ids.length}
                </Badge>
              </label>
            </div>
            {isExpanded && (
              <div role="group" className="ui-tree-enter divide-y">
                {items.map((subject) => (
                  <label
                    key={subject.id}
                    className={cn(
                      'flex min-h-14 cursor-pointer items-center gap-3 py-2 pl-14 pr-4 transition-colors hover:bg-muted/50',
                      selected.includes(subject.id) && 'bg-primary/[.06]',
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={selected.includes(subject.id)}
                      onChange={() => onToggleSubject(subject.id)}
                      disabled={disabled}
                      className="size-5 accent-[var(--primary)]"
                    />
                    <strong className="font-mono text-sm">
                      {subject.code}
                    </strong>
                    <span className="min-w-0 truncate text-sm text-muted-foreground">
                      {subject.name}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function WorkflowStages({
  title,
  stages,
  details,
  active,
  failed,
  hint,
  updateLabel,
  overwriteLabel,
  runAllLabel,
  overwriteAllLabel,
  concurrencyLabel,
  concurrencyHint,
  concurrency,
  onConcurrencyChange,
  disabled,
  onRun,
  onRunAll,
}: {
  title: string
  stages: readonly string[]
  details: readonly string[]
  active: number
  failed: boolean
  hint: string
  updateLabel: string
  overwriteLabel: string
  runAllLabel: string
  overwriteAllLabel: string
  concurrencyLabel: string
  concurrencyHint: string
  concurrency: number
  onConcurrencyChange: (value: number) => void
  disabled: boolean
  onRun: (stage: PipelineStage, mode: UpdateMode) => void
  onRunAll: (mode: UpdateMode) => void
}) {
  const actions: PipelineStage[] = [
    'probe',
    'download',
    'split',
    'inventory',
    'search',
  ]
  return (
    <section
      aria-label={title}
      className="update-track overflow-hidden rounded-3xl border bg-card shadow-sm"
    >
      <div className="flex flex-col gap-5 border-b p-5 md:flex-row md:items-end md:justify-between md:p-6">
        <div className="max-w-2xl">
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">{hint}</p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="sm:max-w-72">
            <label
              htmlFor="pipeline-concurrency"
              className="text-xs font-medium text-muted-foreground"
            >
              {concurrencyLabel}
            </label>
            <div className="mt-1 flex items-center gap-2">
              <Input
                id="pipeline-concurrency"
                type="number"
                min={1}
                max={32}
                value={concurrency}
                disabled={disabled}
                onChange={(event) =>
                  onConcurrencyChange(
                    Math.max(1, Math.min(32, Number(event.target.value) || 1)),
                  )
                }
                aria-describedby="pipeline-concurrency-hint"
                className="h-11 w-20 font-mono"
              />
              <p
                id="pipeline-concurrency-hint"
                className="line-clamp-2 text-xs leading-4 text-muted-foreground"
              >
                {concurrencyHint}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              className="h-11 flex-1 sm:flex-none"
              disabled={disabled}
              onClick={() => onRunAll('update')}
            >
              <HugeiconsIcon icon={RefreshIcon} data-icon="inline-start" />
              {runAllLabel}
            </Button>
            <Button
              variant="outline"
              className="h-11 flex-1 sm:flex-none"
              disabled={disabled}
              onClick={() => onRunAll('overwrite')}
            >
              {overwriteAllLabel}
            </Button>
          </div>
        </div>
      </div>
      <ol className="divide-y">
        {stages.map((label, index) => (
          <li
            key={label}
            className={cn(
              'grid min-h-20 gap-3 px-5 py-4 transition-colors duration-200 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center md:px-6',
              index === active && 'bg-primary/[.055]',
              failed && index === active && 'bg-destructive/[.055]',
            )}
          >
            <span
              className={cn(
                'grid size-8 shrink-0 place-items-center rounded-full border bg-background font-mono text-xs font-semibold text-muted-foreground',
                index <= active &&
                  'border-primary bg-primary text-primary-foreground',
                failed &&
                  index === active &&
                  'border-destructive bg-destructive text-destructive-foreground',
              )}
            >
              {index + 1}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold">{label}</p>
              <p className="mt-0.5 text-xs leading-5 text-muted-foreground">
                {details[index]}
              </p>
            </div>
            <div className="ml-11 flex gap-2 sm:ml-0">
              <Button
                size="sm"
                variant={index === active ? 'default' : 'secondary'}
                className="h-11 flex-1 sm:flex-none"
                disabled={disabled}
                onClick={() => onRun(actions[index], 'update')}
              >
                {updateLabel}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-11 flex-1 sm:flex-none"
                disabled={disabled}
                onClick={() => onRun(actions[index], 'overwrite')}
              >
                {overwriteLabel}
              </Button>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
