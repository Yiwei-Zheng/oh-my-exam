'use client'

import { useEffect, useMemo, useState } from 'react'
import { HugeiconsIcon } from '@hugeicons/react'
import { RefreshIcon, Search01Icon } from '@hugeicons/core-free-icons'

import type { AssetInventory } from '@/components/admin/types'
import { useLocale } from '@/components/locale-provider'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { apiRequest } from '@/lib/api'
import type { Question, TreeNode } from '@/lib/types'

interface PaperChoice {
  id: number
  examId: string
  label: string
  path: string
}

function paperChoices(
  nodes: TreeNode[],
  parents: string[] = [],
): PaperChoice[] {
  return nodes.flatMap((node) =>
    node.kind === 'paper' && node.paper_id && node.exam_id
      ? [
          {
            id: node.paper_id,
            examId: node.exam_id,
            label: node.label,
            path: [...parents, node.label].join(' / '),
          },
        ]
      : paperChoices(node.children || [], [...parents, node.label]),
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
  const [filter, setFilter] = useState('')
  const [selectedPaper, setSelectedPaper] = useState<PaperChoice | null>(null)
  const [questions, setQuestions] = useState<Question[]>([])
  const [selected, setSelected] = useState<Question | null>(null)
  const [rawText, setRawText] = useState('')
  const [markdown, setMarkdown] = useState('')
  const [saving, setSaving] = useState(false)
  const [updateConfigured, setUpdateConfigured] = useState(false)
  const [updateRunning, setUpdateRunning] = useState(false)

  useEffect(() => {
    Promise.all([
      apiRequest<TreeNode[]>('/api/v1/admin/question-tree'),
      apiRequest<{ configured: boolean; job: { status: string } | null }>(
        '/api/v1/admin/question-update',
      ),
    ]).then(([nodes, update]) => {
      setTree(nodes)
      setUpdateConfigured(update.configured)
      setUpdateRunning(update.job?.status === 'running')
    })
  }, [])

  const papers = useMemo(
    () =>
      paperChoices(tree).filter((paper) =>
        paper.path.toLowerCase().includes(filter.toLowerCase()),
      ),
    [filter, tree],
  )

  async function choosePaper(paper: PaperChoice) {
    setSelectedPaper(paper)
    setSelected(null)
    const next = await apiRequest<Question[]>(
      `/api/v1/admin/papers/${paper.id}/questions`,
    )
    setQuestions(next)
    if (next[0]) await chooseQuestion(next[0], paper.examId)
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

  async function startUpdate() {
    if (!updateConfigured || updateRunning) return
    setUpdateRunning(true)
    try {
      await apiRequest('/api/v1/admin/question-update', { method: 'POST' })
    } catch {
      setUpdateRunning(false)
    }
  }

  async function refreshInventory() {
    onInventory(await apiRequest<AssetInventory>('/api/v1/admin/assets'))
  }

  const questionPdf = selected
    ? `/api/v1/exams/${encodeURIComponent(selected.exam_id || '')}/questions/${selected.id}/question.pdf`
    : ''
  const answerPdf = selected
    ? `/api/v1/exams/${encodeURIComponent(selected.exam_id || '')}/questions/${selected.id}/answer.pdf`
    : ''

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-muted-foreground">{t('assetsHint')}</p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={refreshInventory}>
            <HugeiconsIcon icon={RefreshIcon} data-icon="inline-start" />
            Refresh
          </Button>
          <Button
            onClick={startUpdate}
            disabled={!updateConfigured || updateRunning}
          >
            <HugeiconsIcon icon={RefreshIcon} data-icon="inline-start" />
            {updateRunning ? t('pipelineRunning') : t('updateLibrary')}
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
      {inventory && (
        <Card>
          <CardHeader>
            <CardTitle>{t('examPrograms')}</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('examPrograms')}</TableHead>
                  <TableHead className="text-right">
                    {t('totalPapers')}
                  </TableHead>
                  <TableHead className="text-right">
                    {t('totalQuestions')}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {inventory.by_exam.map((exam) => (
                  <TableRow key={exam.id}>
                    <TableCell>
                      <strong>{exam.course_code.toUpperCase()}</strong>
                      <span className="ml-2 text-xs text-muted-foreground">
                        {exam.display_name}
                      </span>
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {exam.paper_count}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {exam.question_count}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
      <Card>
        <CardHeader>
          <CardTitle>{t('questionLibrary')}</CardTitle>
        </CardHeader>
        <CardContent className="grid min-h-[680px] gap-4 p-4 xl:grid-cols-[280px_280px_minmax(0,1fr)]">
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
            <div className="max-h-[620px] overflow-y-auto p-2">
              {papers.map((paper) => (
                <button
                  key={paper.id}
                  onClick={() => choosePaper(paper)}
                  className={`w-full rounded-lg p-3 text-left text-sm hover:bg-muted ${selectedPaper?.id === paper.id ? 'bg-primary/10 text-primary' : ''}`}
                >
                  <span className="line-clamp-2">{paper.path}</span>
                  <Badge variant="secondary" className="mt-2">
                    {paper.label}
                  </Badge>
                </button>
              ))}
            </div>
          </div>
          <div className="rounded-xl border">
            <div className="border-b p-4 text-sm font-semibold">
              {selectedPaper?.label || t('selectPaper')}
            </div>
            <div className="max-h-[620px] overflow-y-auto">
              {questions.map((question) => (
                <button
                  key={question.id}
                  onClick={() => chooseQuestion(question)}
                  className={`w-full border-b p-4 text-left hover:bg-muted ${selected?.id === question.id ? 'bg-primary/10' : ''}`}
                >
                  <strong className="font-mono text-xs text-primary">
                    Q{question.question_number}
                  </strong>
                  <span className="mt-2 line-clamp-3 block text-sm text-muted-foreground">
                    {question.content || question.local_key}
                  </span>
                </button>
              ))}
            </div>
          </div>
          <div className="min-w-0 overflow-hidden rounded-xl border">
            {!selected ? (
              <div className="grid h-full place-items-center p-8 text-center text-muted-foreground">
                {t('selectPaper')}
              </div>
            ) : (
              <Tabs defaultValue="question" className="h-full">
                <div className="border-b p-3">
                  <TabsList>
                    <TabsTrigger value="question">{t('question')}</TabsTrigger>
                    <TabsTrigger value="answer">{t('answer')}</TabsTrigger>
                    <TabsTrigger value="text">{t('text')}</TabsTrigger>
                  </TabsList>
                </div>
                <TabsContent value="question" className="m-0">
                  <iframe
                    className="h-[620px] w-full"
                    src={questionPdf}
                    title={t('questionPdf')}
                  />
                </TabsContent>
                <TabsContent value="answer" className="m-0">
                  <iframe
                    className="h-[620px] w-full"
                    src={answerPdf}
                    title={t('answerPdf')}
                  />
                </TabsContent>
                <TabsContent value="text" className="space-y-4 p-4">
                  <div className="flex justify-between">
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
                </TabsContent>
              </Tabs>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
