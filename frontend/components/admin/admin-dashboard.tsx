'use client'

import { useEffect, useState } from 'react'
import { HugeiconsIcon } from '@hugeicons/react'
import {
  DashboardSquare01Icon,
  Database01Icon,
  Invoice01Icon,
  Menu01Icon,
  Search01Icon,
  UserGroupIcon,
} from '@hugeicons/core-free-icons'

import { useAuth } from '@/components/auth-provider'
import { AccountsPanel } from '@/components/admin/accounts-panel'
import { AssetsPanel } from '@/components/admin/assets-panel'
import { BillingPanel } from '@/components/admin/billing-panel'
import type {
  AdminStats,
  AiBill,
  AssetInventory,
  SystemResources,
} from '@/components/admin/types'
import { useLocale } from '@/components/locale-provider'
import { ProductHeader } from '@/components/product-header'
import { QuestionSearch } from '@/components/question-search'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { apiRequest } from '@/lib/api'
import { cn } from '@/lib/utils'

type Section = 'overview' | 'search' | 'assets' | 'billing' | 'accounts'

export function AdminDashboard() {
  const { user } = useAuth()
  const { t } = useLocale()
  const [section, setSection] = useState<Section>('overview')
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [assets, setAssets] = useState<AssetInventory | null>(null)
  const [bill, setBill] = useState<AiBill | null>(null)
  const [resources, setResources] = useState<SystemResources | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      apiRequest<AdminStats>('/api/v1/admin/statistics'),
      apiRequest<AssetInventory>('/api/v1/admin/assets'),
      apiRequest<AiBill>('/api/v1/admin/ai-usage'),
    ])
      .then(([nextStats, nextAssets, nextBill]) => {
        setStats(nextStats)
        setAssets(nextAssets)
        setBill(nextBill)
      })
      .catch(() => setError(t('loadFailed')))
  }, [t])

  useEffect(() => {
    if (section !== 'overview') return
    let active = true
    const refresh = () =>
      apiRequest<SystemResources>('/api/v1/admin/system-resources')
        .then((next) => {
          if (active) setResources(next)
        })
        .catch(() => undefined)
    void refresh()
    const timer = window.setInterval(refresh, 2000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [section])

  const navigation = [
    {
      id: 'overview' as const,
      label: t('overview'),
      icon: DashboardSquare01Icon,
    },
    { id: 'search' as const, label: t('questions'), icon: Search01Icon },
    { id: 'assets' as const, label: t('assetInventory'), icon: Database01Icon },
    { id: 'billing' as const, label: t('aiBilling'), icon: Invoice01Icon },
    { id: 'accounts' as const, label: t('accounts'), icon: UserGroupIcon },
  ]

  const renderNavigation = () => (
    <nav aria-label="Admin navigation" className="space-y-1">
      {navigation.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => setSection(item.id)}
          className={cn(
            'ui-interactive flex min-h-11 w-full items-center gap-3 rounded-xl px-3 text-sm font-medium transition-colors hover:bg-sidebar-accent',
            section === item.id &&
              'bg-sidebar-primary text-sidebar-primary-foreground hover:bg-sidebar-primary',
          )}
        >
          <HugeiconsIcon icon={item.icon} className="size-4" />
          {item.label}
        </button>
      ))}
    </nav>
  )

  return (
    <div className="min-h-svh bg-muted/25">
      <ProductHeader />
      <div className="mx-auto grid max-w-[1680px] lg:grid-cols-[248px_minmax(0,1fr)]">
        <aside className="sticky top-14 hidden h-[calc(100svh-3.5rem)] border-r bg-sidebar p-4 lg:flex lg:flex-col">
          <div className="mb-6 px-3">
            <p className="font-mono text-[10px] font-bold uppercase tracking-[.18em] text-primary">
              Administrator
            </p>
            <p className="mt-2 truncate text-sm text-muted-foreground">
              {user?.email}
            </p>
          </div>
          {renderNavigation()}
          <div className="mt-auto rounded-xl border bg-background p-3 text-xs text-muted-foreground">
            <span className="mb-2 flex items-center gap-2 font-medium text-foreground">
              <i className="size-2 rounded-full bg-emerald-500" />
              {t('systemReady')}
            </span>
            API v1 · catalog online
          </div>
        </aside>
        <main className="ui-page-enter min-w-0 p-4 md:p-8">
          <div className="mb-6 flex items-start gap-3">
            <Sheet>
              <SheetTrigger
                render={
                  <Button variant="outline" size="icon" className="lg:hidden" />
                }
              >
                <HugeiconsIcon icon={Menu01Icon} />
              </SheetTrigger>
              <SheetContent side="left" className="w-72">
                <SheetHeader>
                  <SheetTitle>{t('controlDesk')}</SheetTitle>
                </SheetHeader>
                <div className="p-4">{renderNavigation()}</div>
              </SheetContent>
            </Sheet>
            <div>
              <p className="font-mono text-xs font-semibold uppercase tracking-[.18em] text-primary">
                Oh My Exam / Admin
              </p>
              <h1 className="mt-1 text-3xl font-semibold tracking-tight">
                {navigation.find((item) => item.id === section)?.label}
              </h1>
              {section === 'overview' && (
                <p className="mt-2 text-muted-foreground">
                  {t('controlDeskHint')}
                </p>
              )}
            </div>
          </div>
          {error && (
            <p
              role="alert"
              className="mb-4 rounded-xl border border-destructive/25 bg-destructive/10 p-3 text-sm text-destructive"
            >
              {error}
            </p>
          )}
          <div key={section} className="ui-section-enter">
            {section === 'overview' && (
              <Overview
                stats={stats}
                assets={assets}
                bill={bill}
                resources={resources}
                onOpen={setSection}
              />
            )}
            {section === 'search' && <QuestionSearch compact />}
            {section === 'assets' && (
              <AssetsPanel inventory={assets} onInventory={setAssets} />
            )}
            {section === 'billing' && <BillingPanel bill={bill} />}
            {section === 'accounts' && <AccountsPanel />}
          </div>
        </main>
      </div>
    </div>
  )
}

function Overview({
  stats,
  assets,
  bill,
  resources,
  onOpen,
}: {
  stats: AdminStats | null
  assets: AssetInventory | null
  bill: AiBill | null
  resources: SystemResources | null
  onOpen: (section: Section) => void
}) {
  const { t } = useLocale()
  if (!stats || !assets || !bill)
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[1, 2, 3, 4].map((item) => (
          <Skeleton key={item} className="h-36" />
        ))}
      </div>
    )
  const cards = [
    {
      label: t('totalQuestions'),
      value: assets.questions.toLocaleString(),
      hint: `${assets.papers.toLocaleString()} ${t('totalPapers')}`,
      section: 'assets' as const,
    },
    {
      label: t('searchableCoverage'),
      value: `${Math.round(assets.searchable_coverage * 100)}%`,
      hint: `${assets.searchable_questions.toLocaleString()} / ${assets.questions.toLocaleString()}`,
      section: 'assets' as const,
    },
    {
      label: t('userTotal'),
      value: stats.users_total.toLocaleString(),
      hint: `${stats.active_7d} ${t('activeWeek')}`,
      section: 'accounts' as const,
    },
    {
      label: t('aiBilling'),
      value: `$${(bill.cost_microusd / 1_000_000).toFixed(2)}`,
      hint: `${bill.calls} ${t('calls')} · ${bill.month}`,
      section: 'billing' as const,
    },
  ]
  return (
    <div className="space-y-6">
      <div className="ui-stagger grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((item, index) => (
          <button
            key={item.label}
            type="button"
            onClick={() => onOpen(item.section)}
            className="ui-interactive text-left"
            data-motion-item
            style={{ '--motion-index': index } as React.CSSProperties}
          >
            <Card className="h-full transition-colors hover:border-primary/40">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {item.label}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="font-mono text-3xl font-semibold tracking-tight">
                  {item.value}
                </p>
                <p className="mt-2 text-xs text-muted-foreground">
                  {item.hint}
                </p>
              </CardContent>
            </Card>
          </button>
        ))}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{t('examPrograms')}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {assets.by_exam.map((exam) => (
            <div
              key={exam.id}
              className="flex items-center justify-between rounded-xl border p-4"
            >
              <div>
                <p className="font-semibold">
                  {exam.course_code.toUpperCase()}
                </p>
                <p className="text-xs text-muted-foreground">
                  {exam.display_name}
                </p>
              </div>
              <Badge variant="secondary">{exam.question_count}</Badge>
            </div>
          ))}
        </CardContent>
      </Card>
      <SystemResourcesPanel resources={resources} />
    </div>
  )
}

function SystemResourcesPanel({
  resources,
}: {
  resources: SystemResources | null
}) {
  const { locale, t } = useLocale()
  if (!resources) return <Skeleton className="h-72 w-full rounded-3xl" />
  const meters = [
    { label: t('cpu'), percent: resources.cpu.percent, detail: `${resources.cpu.percent.toFixed(1)}%` },
    {
      label: t('memory'),
      percent: resources.memory.percent,
      detail: `${formatBytes(resources.memory.used_bytes)} / ${formatBytes(resources.memory.total_bytes)}`,
    },
    {
      label: t('disk'),
      percent: resources.disk.percent,
      detail: `${formatBytes(resources.disk.used_bytes)} / ${formatBytes(resources.disk.total_bytes)}`,
    },
  ]
  const categories = [
    [t('codeStorage'), resources.storage.categories.code],
    [t('databaseStorage'), resources.storage.categories.databases],
    [t('paperStorage'), resources.storage.categories.papers],
    [t('otherDataStorage'), resources.storage.categories.other_data],
  ] as const

  return (
    <Card aria-label={t('systemResources')}>
      <CardHeader className="flex-row items-center justify-between gap-3">
        <div>
          <CardTitle>{t('systemResources')}</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            {t('lastUpdated')} ·{' '}
            {new Intl.DateTimeFormat(locale, { timeStyle: 'medium' }).format(
              resources.sampled_at * 1000,
            )}
          </p>
        </div>
        <Badge variant="secondary" className="gap-2">
          <i className="size-2 rounded-full bg-emerald-500" aria-hidden="true" />
          {t('live')}
        </Badge>
      </CardHeader>
      <CardContent className="grid gap-6 xl:grid-cols-[1.1fr_.9fr]">
        <div className="grid gap-4 sm:grid-cols-3">
          {meters.map((meter) => (
            <div key={meter.label} className="rounded-2xl border bg-muted/20 p-4">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm font-medium">{meter.label}</span>
                <span className="font-mono text-xl font-semibold tabular-nums">
                  {meter.percent.toFixed(1)}%
                </span>
              </div>
              <div
                className="mt-4 h-2 overflow-hidden rounded-full bg-muted"
                role="meter"
                aria-label={meter.label}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={meter.percent}
              >
                <div
                  className="h-full origin-left rounded-full bg-primary transition-transform duration-500 ease-out"
                  style={{ transform: `scaleX(${Math.min(100, meter.percent) / 100})` }}
                />
              </div>
              <p className="mt-3 font-mono text-[11px] tabular-nums text-muted-foreground">
                {meter.detail}
              </p>
            </div>
          ))}
        </div>
        <div className="rounded-2xl border p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <span className="text-sm font-medium">{t('projectStorage')}</span>
            <span className="font-mono text-sm font-semibold tabular-nums">
              {formatBytes(resources.storage.project_bytes)}
            </span>
          </div>
          <dl className="space-y-2">
            {categories.map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-4 text-sm">
                <dt className="text-muted-foreground">{label}</dt>
                <dd className="font-mono tabular-nums">{formatBytes(value)}</dd>
              </div>
            ))}
          </dl>
        </div>
      </CardContent>
    </Card>
  )
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let size = value / 1024
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(size >= 100 ? 0 : 1)} ${units[index]}`
}
