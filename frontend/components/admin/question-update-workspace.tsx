'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { HugeiconsIcon } from '@hugeicons/react'
import {
  ArrowRight01Icon,
  Database01Icon,
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
}

type PipelineAction =
  'probe' | 'all' | 'download' | 'split' | 'inventory' | 'search'
type PipelineStage = Exclude<PipelineAction, 'all'>
type UpdateMode = 'update' | 'overwrite'

const copy = {
  'zh-CN': {
    eyebrow: '题库维护 / 资源流水线',
    title: '让新试卷沿着一条轨迹进入题库',
    intro:
      '只显示已有完整工作流的科目。先嗅探来源并和本地逐项比较，确认后再下载、切题、盘点和建立搜索索引。',
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
    concurrency: '并发下载数',
    concurrencyHint: '范围 1–12。来源限流时建议使用 2–4。',
    start: '下载并进入工作流',
    rerun: '重新盘点并入库',
    backgroundHint: '任务由后端 CLI 在后台运行，启动后可以离开此页。',
    running: '工作流运行中',
    complete: '题库更新完成',
    failed: '工作流未完成',
    retry: '重新嗅探',
    empty: '请至少选择一个科目',
    unavailable: '更新流水线尚未配置',
    probeFailed: '资源嗅探失败，请检查来源网络后重试。',
    partialProbeFailed: '部分项目嗅探失败，其他项目的结果不受影响。',
    startFailed: '未能启动工作流，请稍后重试。',
    more: '项未展开',
    stages: ['嗅探', '下载', '切题', '盘点入库', '可搜索'],
    stageHint: '每一步都可增量更新或覆盖重跑，也可以一键执行完整流水线。',
    update: '更新',
    overwrite: '覆盖',
    runAll: '一键全部执行',
    overwriteAll: '覆盖全部重跑',
  },
  en: {
    eyebrow: 'Library maintenance / resource pipeline',
    title: 'Move new papers into the library on one clear track',
    intro:
      'Only subjects with a complete workflow appear here. Probe sources, compare locally, then download, split, inventory, and index.',
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
    concurrency: 'Concurrent downloads',
    concurrencyHint: 'Choose 1–12. Use 2–4 when a source rate-limits requests.',
    start: 'Download and continue',
    rerun: 'Rebuild inventory and index',
    backgroundHint:
      'The backend CLI continues in the background, so you can leave after it starts.',
    running: 'Workflow in progress',
    complete: 'Library update complete',
    failed: 'Workflow did not complete',
    retry: 'Probe again',
    empty: 'Choose at least one subject',
    unavailable: 'The update pipeline is not configured',
    probeFailed:
      'Resource probing failed. Check source connectivity and try again.',
    partialProbeFailed:
      'Some projects could not be probed. Results from other projects are unaffected.',
    startFailed: 'The workflow could not be started. Try again shortly.',
    more: 'more not shown',
    stages: ['Probe', 'Download', 'Split', 'Inventory', 'Searchable'],
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
      workflows: WorkflowSubject[]
      job: UpdateJob | null
    }>('/api/v1/admin/question-update')
      .then((result) => {
        setConfigured(result.configured)
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

  return (
    <div className="min-h-svh bg-[radial-gradient(circle_at_12%_0%,color-mix(in_oklch,var(--primary),transparent_88%),transparent_38%)]">
      <ProductHeader />
      <main className="update-page-enter mx-auto w-full max-w-6xl px-4 py-8 md:px-8 md:py-12">
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <p className="font-mono text-xs font-semibold uppercase tracking-[.18em] text-primary">
              {c.eyebrow}
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-[-.035em] text-balance md:text-5xl">
              {c.title}
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">
              {c.intro}
            </p>
          </div>
          <Button variant="outline" render={<Link href="/admin" />}>
            {c.back}
          </Button>
        </div>

        <WorkflowTrack
          stages={c.stages}
          active={activeStage}
          failed={job?.status === 'failed'}
          hint={c.stageHint}
          updateLabel={c.update}
          overwriteLabel={c.overwrite}
          runAllLabel={c.runAll}
          overwriteAllLabel={c.overwriteAll}
          disabled={
            busy || !configured || !selected.length || job?.status === 'running'
          }
          onRun={runStage}
          onRunAll={(mode) => void start('all', mode)}
        />

        {error && (
          <Alert variant="destructive" className="mt-6">
            <AlertTitle>{error}</AlertTitle>
          </Alert>
        )}
        {!configured && (
          <Alert className="mt-6">
            <AlertTitle>{c.unavailable}</AlertTitle>
          </Alert>
        )}

        <section className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,.85fr)]">
          <Card
            className="update-card-enter overflow-hidden"
            style={{ animationDelay: '90ms' }}
          >
            <CardContent className="p-5 md:p-6">
              <div className="mb-5">
                <h2 className="text-lg font-semibold">{c.choose}</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {c.chooseHint}
                </p>
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
              />
              <Button
                className="mt-5 h-11 w-full sm:w-auto"
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
                <div className="grid min-h-64 place-items-center text-center text-sm text-muted-foreground">
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
                  <div>
                    <label
                      htmlFor="download-concurrency"
                      className="text-sm font-medium"
                    >
                      {c.concurrency}
                    </label>
                    <div className="mt-2 flex items-center gap-3">
                      <Input
                        id="download-concurrency"
                        type="number"
                        min={1}
                        max={12}
                        value={concurrency}
                        onChange={(event) =>
                          setConcurrency(
                            Math.max(
                              1,
                              Math.min(12, Number(event.target.value) || 1),
                            ),
                          )
                        }
                        className="h-11 w-24 font-mono"
                      />
                      <p className="text-xs leading-5 text-muted-foreground">
                        {c.concurrencyHint}
                      </p>
                    </div>
                  </div>
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

        {job && (
          <section
            aria-live="polite"
            className="update-card-enter mt-6 rounded-3xl border bg-card p-5 md:p-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-semibold">
                  {job.status === 'completed'
                    ? c.complete
                    : job.status === 'failed'
                      ? c.failed
                      : c.running}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {job.message}
                </p>
              </div>
              <span className="font-mono text-2xl font-semibold tabular-nums">
                {job.progress}%
              </span>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-transform duration-300 ease-out"
                style={{
                  transform: `scaleX(${job.progress / 100})`,
                  transformOrigin: 'left',
                }}
              />
            </div>
            {job.status === 'failed' && (
              <Button
                variant="outline"
                className="mt-4"
                onClick={() => void sniff('update')}
              >
                {c.retry}
              </Button>
            )}
          </section>
        )}
      </main>
    </div>
  )
}

function WorkflowSubjectTree({
  subjects,
  selected,
  expanded,
  onToggleExpanded,
  onToggleFamily,
  onToggleSubject,
}: {
  subjects: WorkflowSubject[]
  selected: string[]
  expanded: Set<string>
  onToggleExpanded: (family: string) => void
  onToggleFamily: (ids: string[]) => void
  onToggleSubject: (id: string) => void
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
    <div role="tree" className="overflow-hidden rounded-2xl border">
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

function WorkflowTrack({
  stages,
  active,
  failed,
  hint,
  updateLabel,
  overwriteLabel,
  runAllLabel,
  overwriteAllLabel,
  disabled,
  onRun,
  onRunAll,
}: {
  stages: readonly string[]
  active: number
  failed: boolean
  hint: string
  updateLabel: string
  overwriteLabel: string
  runAllLabel: string
  overwriteAllLabel: string
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
      aria-label="Update workflow"
      className="update-track relative overflow-hidden rounded-3xl border bg-card/80 px-4 py-6 backdrop-blur md:px-8 md:py-8"
    >
      <div className="relative z-10 mb-6 flex flex-wrap items-center justify-between gap-4">
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
          {hint}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            className="h-11"
            disabled={disabled}
            onClick={() => onRunAll('update')}
          >
            {runAllLabel}
          </Button>
          <Button
            variant="outline"
            className="h-11"
            disabled={disabled}
            onClick={() => onRunAll('overwrite')}
          >
            {overwriteAllLabel}
          </Button>
        </div>
      </div>
      <svg
        aria-hidden="true"
        viewBox="0 0 1000 120"
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-x-8 top-5 hidden h-24 w-[calc(100%-4rem)] md:block"
      >
        <path
          d="M42 78 C180 8 286 108 430 52 S710 18 958 68"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-border"
        />
        <path
          d="M42 78 C180 8 286 108 430 52 S710 18 958 68"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          pathLength="1"
          className="update-track-path text-primary"
        />
      </svg>
      <ol className="relative grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5 lg:gap-5">
        {stages.map((label, index) => (
          <li
            key={label}
            className={cn(
              'flex min-h-36 flex-col justify-between gap-3 rounded-2xl border bg-background/95 p-3 transition-all duration-300',
              index <= active && 'border-primary/50 text-primary',
              failed &&
                index === active &&
                'border-destructive/50 text-destructive',
            )}
          >
            <div className="flex items-center gap-3">
              <span
                className={cn(
                  'grid size-7 shrink-0 place-items-center rounded-full border bg-background font-mono text-xs font-semibold',
                  index <= active &&
                    'border-primary bg-primary text-primary-foreground',
                )}
              >
                {index + 1}
              </span>
              <span className="text-sm font-semibold">{label}</span>
            </div>
            <div className="grid grid-cols-2 gap-2 lg:grid-cols-1">
              <Button
                size="sm"
                className="h-11"
                disabled={disabled}
                onClick={() => onRun(actions[index], 'update')}
              >
                {updateLabel}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-11"
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
