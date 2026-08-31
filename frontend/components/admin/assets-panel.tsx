'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { HugeiconsIcon } from '@hugeicons/react'
import {
  ArrowRight01Icon,
  RefreshIcon,
  Search01Icon,
} from '@hugeicons/core-free-icons'

import type { AssetInventory } from '@/components/admin/types'
import { useLocale } from '@/components/locale-provider'
import { QuestionPreview } from '@/components/question-preview-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { apiRequest } from '@/lib/api'
import type { Question, TreeNode } from '@/lib/types'

interface PaperChoice {
  id: number
  examId: string
  label: string
}

function filterTree(nodes: TreeNode[], query: string): TreeNode[] {
  if (!query.trim()) return nodes
  const normalized = query.trim().toLocaleLowerCase()
  return nodes.flatMap((node) => {
    const children = filterTree(node.children || [], query)
    return node.label.toLocaleLowerCase().includes(normalized) ||
      children.length
      ? [{ ...node, children }]
      : []
  })
}

function expandableIds(nodes: TreeNode[], depth = Infinity): string[] {
  return nodes.flatMap((node) =>
    node.children?.length
      ? [node.id, ...(depth > 0 ? expandableIds(node.children, depth - 1) : [])]
      : [],
  )
}

function AssetTreeNode({
  node,
  depth,
  expanded,
  selectedPaperId,
  questions,
  selectedQuestionId,
  onToggle,
  onPaper,
  onQuestion,
}: {
  node: TreeNode
  depth: number
  expanded: Set<string>
  selectedPaperId?: number
  questions: Question[]
  selectedQuestionId?: number
  onToggle: (id: string) => void
  onPaper: (paper: PaperChoice) => void
  onQuestion: (question: Question) => void
}) {
  const isBranch = Boolean(node.children?.length)
  const isPaper = node.kind === 'paper' && node.paper_id && node.exam_id
  const isExpanded = isPaper
    ? selectedPaperId === node.paper_id
    : expanded.has(node.id)
  const isExpandable = isBranch || Boolean(isPaper)
  return (
    <div
      role="treeitem"
      aria-expanded={isExpandable ? isExpanded : undefined}
      aria-selected={isPaper ? selectedPaperId === node.paper_id : false}
    >
      <button
        type="button"
        onClick={() =>
          isPaper
            ? onPaper({
                id: node.paper_id!,
                examId: node.exam_id!,
                label: node.label,
              })
            : isBranch && onToggle(node.id)
        }
        className={`ui-interactive flex min-h-11 w-full items-center gap-2 rounded-lg pr-2 text-left text-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${selectedPaperId === node.paper_id ? 'bg-primary/10 text-primary' : ''}`}
        style={{ paddingLeft: `${8 + depth * 16}px` }}
      >
        <HugeiconsIcon
          icon={ArrowRight01Icon}
          className={`size-4 shrink-0 transition-transform ${isExpanded ? 'rotate-90' : ''} ${isExpandable ? '' : 'opacity-25'}`}
        />
        <span className="min-w-0 flex-1 truncate font-medium">
          {node.label}
        </span>
        {node.kind === 'program' && (
          <span className="grid w-28 shrink-0 grid-cols-2 gap-1 font-mono text-[11px] tabular-nums text-muted-foreground">
            <span className="text-right">{node.paper_count || 0}</span>
            <span className="text-right">{node.question_count || 0}</span>
          </span>
        )}
        {node.count !== undefined && (
          <Badge variant="secondary" className="shrink-0 font-mono text-[10px]">
            {node.count}
          </Badge>
        )}
      </button>
      {isBranch && isExpanded && (
        <div role="group" className="ui-tree-enter">
          {node.children.map((child) => (
            <AssetTreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              selectedPaperId={selectedPaperId}
              questions={questions}
              selectedQuestionId={selectedQuestionId}
              onToggle={onToggle}
              onPaper={onPaper}
              onQuestion={onQuestion}
            />
          ))}
        </div>
      )}
      {isPaper && isExpanded && (
        <div role="group" className="ui-tree-enter">
          {questions.map((question) => (
            <div
              key={question.id}
              role="treeitem"
              aria-selected={selectedQuestionId === question.id}
            >
              <button
                type="button"
                onClick={() => onQuestion(question)}
                className={`ui-interactive min-h-11 w-full rounded-lg pr-2 text-left font-mono text-xs transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${selectedQuestionId === question.id ? 'bg-primary/10 text-primary' : 'text-muted-foreground'}`}
                style={{ paddingLeft: `${24 + (depth + 1) * 16}px` }}
              >
                Q{question.question_number}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function AssetsPanel({
  inventory,
  onInventory,
}: {
  inventory: AssetInventory | null
  onInventory: (value: AssetInventory) => void
}) {
  const { t } = useLocale()
  const [tree, setTree] = useState<TreeNode[]>([])
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [filter, setFilter] = useState('')
  const [selectedPaper, setSelectedPaper] = useState<PaperChoice | null>(null)
  const [questions, setQuestions] = useState<Question[]>([])
  const [selected, setSelected] = useState<Question | null>(null)
  const [rawText, setRawText] = useState('')
  const [markdown, setMarkdown] = useState('')
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    apiRequest<TreeNode[]>('/api/v1/admin/question-tree').then((nodes) => {
      setTree(nodes)
      setExpanded(new Set(expandableIds(nodes, 1)))
    })
  }, [])

  const visibleTree = useMemo(() => filterTree(tree, filter), [filter, tree])
  const visibleExpanded = useMemo(
    () => (filter.trim() ? new Set(expandableIds(visibleTree)) : expanded),
    [expanded, filter, visibleTree],
  )

  function toggleNode(id: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function choosePaper(paper: PaperChoice) {
    setSelectedPaper(paper)
    setSelected(null)
    const next = await apiRequest<Question[]>(
      `/api/v1/admin/papers/${paper.id}/questions`,
    )
    setQuestions(next)
  }

  async function chooseQuestion(
    question: Question,
    examId = selectedPaper?.examId || '',
  ) {
    const detail = await apiRequest<Question>(
      `/api/v1/exams/${encodeURIComponent(examId)}/questions/${question.id}`,
    )
    const resolved = { ...detail, exam_id: examId }
    setSelected(resolved)
    setRawText(resolved.answer_structured?.raw_text || '')
    setMarkdown(resolved.answer_structured?.markdown || '')
  }

  async function saveRevision() {
    if (!selected) return
    setSaving(true)
    try {
      const payload = await apiRequest<{
        answer_structured: NonNullable<Question['answer_structured']>
      }>(`/api/v1/admin/questions/${selected.id}/answer-text`, {
        method: 'PATCH',
        body: JSON.stringify({ raw_text: rawText, markdown }),
      })
      setSelected({ ...selected, answer_structured: payload.answer_structured })
    } finally {
      setSaving(false)
    }
  }

  async function refreshInventory() {
    onInventory(await apiRequest<AssetInventory>('/api/v1/admin/assets'))
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-muted-foreground">{t('assetsHint')}</p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={refreshInventory}>
            <HugeiconsIcon icon={RefreshIcon} data-icon="inline-start" />
            Refresh
          </Button>
          <Button render={<Link href="/admin/update" />}>
            <HugeiconsIcon icon={RefreshIcon} data-icon="inline-start" />
            {t('updateLibrary')}
          </Button>
        </div>
      </div>
      {inventory && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            [t('totalQuestions'), inventory.questions],
            [t('totalPapers'), inventory.papers],
            [t('sourceDocuments'), inventory.source_documents],
            [
              t('answerCoverage'),
              `${Math.round(inventory.answer_coverage * 100)}%`,
            ],
          ].map(([label, value]) => (
            <Card key={String(label)}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-muted-foreground">
                  {label}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="font-mono text-3xl font-semibold">{value}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <Card>
        <CardHeader>
          <CardTitle>{t('questionLibrary')}</CardTitle>
        </CardHeader>
        <CardContent className="grid min-h-[680px] gap-4 p-4 xl:grid-cols-[380px_minmax(0,1fr)]">
          <div className="min-w-0 rounded-xl border">
            <div className="relative border-b p-3">
              <HugeiconsIcon
                icon={Search01Icon}
                className="absolute left-6 top-6 size-4 text-muted-foreground"
              />
              <Input
                className="pl-9"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder={t('filterLibrary')}
              />
            </div>
            <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
              <div className="flex gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setExpanded(new Set(expandableIds(tree)))}
                >
                  {t('expandAll')}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setExpanded(new Set())}
                >
                  {t('collapseAll')}
                </Button>
              </div>
            </div>
            <div className="grid grid-cols-[minmax(0,1fr)_56px_56px] items-center border-b px-3 py-2 text-[11px] font-semibold text-muted-foreground">
              <span>{t('assetTree')}</span>
              <span className="text-right">{t('totalPapers')}</span>
              <span className="text-right">{t('totalQuestions')}</span>
            </div>
            <div
              role="tree"
              aria-label={t('assetTree')}
              className="max-h-[620px] overflow-y-auto p-2"
            >
              {visibleTree.map((node) => (
                <AssetTreeNode
                  key={node.id}
                  node={node}
                  depth={0}
                  expanded={visibleExpanded}
                  selectedPaperId={selectedPaper?.id}
                  questions={questions}
                  selectedQuestionId={selected?.id}
                  onToggle={toggleNode}
                  onPaper={choosePaper}
                  onQuestion={chooseQuestion}
                />
              ))}
            </div>
          </div>
          <div className="min-w-0 overflow-hidden rounded-xl border">
            {selected ? (
              <QuestionPreview
                question={selected}
                textPanel={
                  <div className="space-y-4">
                    <div className="flex justify-between gap-4">
                      <div>
                        <p className="font-semibold">{t('structuredText')}</p>
                        <p className="text-xs text-muted-foreground">
                          v{selected.answer_structured?.version || 0}
                        </p>
                      </div>
                      <Button onClick={saveRevision} disabled={saving}>
                        {t('saveRevision')}
                      </Button>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="raw-text">{t('rawText')}</Label>
                      <Textarea
                        id="raw-text"
                        rows={10}
                        value={rawText}
                        onChange={(event) => setRawText(event.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="markdown">{t('markdown')}</Label>
                      <Textarea
                        id="markdown"
                        rows={12}
                        value={markdown}
                        onChange={(event) => setMarkdown(event.target.value)}
                      />
                    </div>
                  </div>
                }
              />
            ) : (
              <div className="grid min-h-[680px] place-items-center p-6 text-center text-sm text-muted-foreground">
                {t('chooseQuestion')}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
