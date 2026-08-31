'use client'

import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { HugeiconsIcon } from '@hugeicons/react'
import {
  Add01Icon,
  ArrowRight01Icon,
  BookSearchIcon,
  Cancel01Icon,
  Search01Icon,
  Tick02Icon,
} from '@hugeicons/core-free-icons'

import { useLocale } from '@/components/locale-provider'
import { ExamTreeSelect } from '@/components/exam-tree-select'
import { QuestionPreviewDialog } from '@/components/question-preview-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ApiError, apiRequest } from '@/lib/api'
import type { Exam, ImageSearchResponse, Question, Topic } from '@/lib/types'

type SearchMode = 'text' | 'image' | 'topic'
const ACCEPTED_IMAGES = ['image/jpeg', 'image/png', 'image/webp']

type TopicNode = Topic & { children: TopicNode[] }

function buildTopicTree(topics: Topic[]): TopicNode[] {
  const nodes = new Map<number, TopicNode>(
    topics.map((topic) => [topic.id, { ...topic, children: [] }]),
  )
  const roots: TopicNode[] = []
  nodes.forEach((node) => {
    const parent =
      node.parent_id === null ? undefined : nodes.get(node.parent_id)
    if (parent) parent.children.push(node)
    else roots.push(node)
  })
  return roots
}

function filterTopicTree(nodes: TopicNode[], query: string): TopicNode[] {
  if (!query.trim()) return nodes
  const normalized = query.trim().toLocaleLowerCase()
  return nodes.flatMap((node) => {
    const children = filterTopicTree(node.children, query)
    return node.title.toLocaleLowerCase().includes(normalized) ||
      children.length
      ? [{ ...node, children }]
      : []
  })
}

function collectTopicCodes(node: TopicNode): string[] {
  return [node.code, ...node.children.flatMap(collectTopicCodes)]
}

function findTopic(nodes: TopicNode[], code: string): TopicNode | undefined {
  for (const node of nodes) {
    if (node.code === code) return node
    const child = findTopic(node.children, code)
    if (child) return child
  }
}

function TopicTreeItem({
  node,
  depth,
  expanded,
  selected,
  onToggle,
  onSelect,
}: {
  node: TopicNode
  depth: number
  expanded: Set<number>
  selected: string
  onToggle: (id: number) => void
  onSelect: (code: string) => void
}) {
  const isBranch = node.children.length > 0
  const isExpanded = expanded.has(node.id)
  return (
    <div
      role="treeitem"
      aria-expanded={isBranch ? isExpanded : undefined}
      aria-selected={selected === node.code}
    >
      <div
        className={`flex min-h-11 items-center rounded-xl transition-colors ${selected === node.code ? 'bg-primary/10 text-primary' : 'hover:bg-muted/70'}`}
        style={{ paddingLeft: `${4 + depth * 16}px` }}
      >
        <button
          type="button"
          className="grid size-11 shrink-0 place-items-center rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={node.title}
          onClick={() => (isBranch ? onToggle(node.id) : onSelect(node.code))}
        >
          <HugeiconsIcon
            icon={ArrowRight01Icon}
            className={`size-4 transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''} ${isBranch ? '' : 'opacity-25'}`}
          />
        </button>
        <button
          type="button"
          className="flex min-h-11 min-w-0 flex-1 items-center justify-between gap-3 rounded-xl pr-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={() => onSelect(node.code)}
        >
          <span className="truncate text-sm font-medium">{node.title}</span>
          <span className="font-mono text-xs tabular-nums text-muted-foreground">
            {node.question_count}
          </span>
        </button>
      </div>
      {isBranch && isExpanded && (
        <div role="group" className="ui-tree-enter">
          {node.children.map((child) => (
            <TopicTreeItem
              key={child.id}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              selected={selected}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function readImage(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!ACCEPTED_IMAGES.includes(file.type) || file.size > 20 * 1024 * 1024) {
      reject(new Error('invalid_image'))
      return
    }
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('invalid_image'))
    reader.onload = () => {
      const image = new Image()
      image.onerror = () => reject(new Error('invalid_image'))
      image.onload = () => {
        const scale = Math.min(1, 2400 / Math.max(image.width, image.height))
        const canvas = document.createElement('canvas')
        canvas.width = Math.max(1, Math.round(image.width * scale))
        canvas.height = Math.max(1, Math.round(image.height * scale))
        const context = canvas.getContext('2d')
        if (!context) {
          reject(new Error('invalid_image'))
          return
        }
        context.drawImage(image, 0, 0, canvas.width, canvas.height)
        const encoded = canvas.toDataURL('image/jpeg', 0.9)
        if (encoded.length > 12_000_000) reject(new Error('invalid_image'))
        else resolve(encoded)
      }
      image.src = String(reader.result || '')
    }
    reader.readAsDataURL(file)
  })
}

export function QuestionSearch({ compact = false }: { compact?: boolean }) {
  const { t } = useLocale()
  const fileInput = useRef<HTMLInputElement>(null)
  const [mode, setMode] = useState<SearchMode>('text')
  const [exams, setExams] = useState<Exam[]>([])
  const [topics, setTopics] = useState<Topic[]>([])
  const [query, setQuery] = useState('')
  const [examId, setExamId] = useState('all')
  const [topicCode, setTopicCode] = useState('all')
  const [topicFilter, setTopicFilter] = useState('')
  const [expandedTopics, setExpandedTopics] = useState<Set<number>>(new Set())
  const [imageData, setImageData] = useState('')
  const [results, setResults] = useState<Question[]>([])
  const [selected, setSelected] = useState<Question | null>(null)
  const [similar, setSimilar] = useState<Question[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState('')

  const acceptImage = useCallback(
    async (file: File) => {
      setError('')
      try {
        setImageData(await readImage(file))
      } catch {
        setImageData('')
        setError(t('invalidImage'))
      }
    },
    [t],
  )

  useEffect(() => {
    apiRequest<Exam[]>('/api/v1/exams')
      .then(setExams)
      .catch(() => setError(t('loadFailed')))
  }, [t])

  useEffect(() => {
    const params = new URLSearchParams()
    if (examId !== 'all') params.set('exam_id', examId)
    apiRequest<Topic[]>(`/api/v1/topics${params.size ? `?${params}` : ''}`)
      .then((next) => {
        setTopics(next)
        setTopicCode('all')
      })
      .catch(() => setTopics([]))
  }, [examId])

  useEffect(() => {
    if (mode !== 'image') return
    const onPaste = (event: ClipboardEvent) => {
      const item = Array.from(event.clipboardData?.items || []).find((entry) =>
        entry.type.startsWith('image/'),
      )
      const file = item?.getAsFile()
      if (!file) return
      event.preventDefault()
      void acceptImage(file)
    }
    document.addEventListener('paste', onPaste)
    return () => document.removeEventListener('paste', onPaste)
  }, [acceptImage, mode])

  const selectedExamId = selected?.exam_id || (examId === 'all' ? '' : examId)
  const topicTree = useMemo(() => buildTopicTree(topics), [topics])
  const visibleTopicTree = useMemo(
    () => filterTopicTree(topicTree, topicFilter),
    [topicFilter, topicTree],
  )

  function canSearch() {
    if (mode === 'text') return Boolean(query.trim())
    if (mode === 'image') return Boolean(imageData)
    return topicCode !== 'all'
  }

  async function search(event: FormEvent) {
    event.preventDefault()
    if (!canSearch() || loading) return
    setLoading(true)
    setSearched(true)
    setError('')
    setSelected(null)
    setSimilar([])
    try {
      if (mode === 'image') {
        const response = await apiRequest<ImageSearchResponse>(
          '/api/v1/questions/image-search',
          {
            method: 'POST',
            body: JSON.stringify({
              image_data_url: imageData,
              exam_id: examId === 'all' ? null : examId,
              topic: [],
              limit: 5,
            }),
          },
        )
        setResults(response.results)
      } else {
        const params = new URLSearchParams({
          query: mode === 'text' ? query.trim() : '',
          limit: '50',
        })
        if (examId !== 'all') params.set('exam_id', examId)
        if (mode === 'topic' && topicCode !== 'all') {
          const selectedTopic = findTopic(topicTree, topicCode)
          for (const code of selectedTopic
            ? collectTopicCodes(selectedTopic)
            : [topicCode]) {
            params.append('topic', code)
          }
        }
        setResults(
          await apiRequest<Question[]>(`/api/v1/questions/search?${params}`),
        )
      }
    } catch (reason) {
      setResults([])
      setError(
        reason instanceof ApiError && reason.detail === 'ocr_unavailable'
          ? t('ocrUnavailable')
          : t('loadFailed'),
      )
    } finally {
      setLoading(false)
    }
  }

  async function choose(question: Question) {
    const resolved = question.exam_id || (examId === 'all' ? '' : examId)
    setSimilar([])
    if (!resolved) {
      setError(t('loadFailed'))
      return
    }
    try {
      const [detail, related] = await Promise.all([
        apiRequest<Question>(
          `/api/v1/exams/${encodeURIComponent(resolved)}/questions/${question.id}`,
        ),
        apiRequest<Question[]>(
          `/api/v1/exams/${encodeURIComponent(resolved)}/questions/${question.id}/similar?limit=8`,
        ),
      ])
      setSelected({ ...detail, exam_id: resolved })
      setSimilar(related)
    } catch {
      setError(t('loadFailed'))
    }
  }

  return (
    <section
      className={
        compact
          ? 'space-y-4'
          : 'ui-page-enter mx-auto w-full max-w-[1480px] space-y-6 p-4 md:p-8'
      }
    >
      {!compact && (
        <div className="max-w-2xl">
          <p className="mb-2 font-mono text-xs font-semibold uppercase tracking-[.18em] text-primary">
            Question intelligence
          </p>
          <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
            {t('searchTitle')}
          </h1>
          <p className="mt-3 text-muted-foreground">{t('searchHint')}</p>
        </div>
      )}
      <Card className="relative z-20 overflow-visible">
        <CardContent className="p-0">
          <Tabs
            value={mode}
            onValueChange={(value) => setMode(value as SearchMode)}
          >
            <div className="border-b bg-muted/30 px-4 pt-4 md:px-6">
              <TabsList>
                <TabsTrigger value="text">{t('textSearch')}</TabsTrigger>
                <TabsTrigger value="image">{t('imageSearch')}</TabsTrigger>
                <TabsTrigger value="topic">{t('topicSearch')}</TabsTrigger>
              </TabsList>
            </div>
            <form onSubmit={search} className="p-4 md:p-6">
              <TabsContent value="text" className="m-0">
                <div className="space-y-2">
                  <Label htmlFor="question-query">{t('questions')}</Label>
                  <Input
                    id="question-query"
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder={t('searchPlaceholder')}
                  />
                </div>
              </TabsContent>
              <TabsContent value="image" className="m-0">
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
                  <div
                    className="relative grid min-h-48 place-items-center overflow-hidden rounded-xl border border-dashed bg-muted/25 p-5 text-center focus-within:ring-2 focus-within:ring-ring"
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => {
                      event.preventDefault()
                      const file = event.dataTransfer.files[0]
                      if (file) void acceptImage(file)
                    }}
                  >
                    {imageData ? (
                      // A user-provided data URL cannot be optimized by Next Image.
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={imageData}
                        alt={t('uploadQuestionImage')}
                        className="max-h-72 w-full object-contain"
                      />
                    ) : (
                      <div className="max-w-md">
                        <HugeiconsIcon
                          icon={BookSearchIcon}
                          className="mx-auto mb-3 size-9 text-primary"
                        />
                        <p className="font-semibold">
                          {t('uploadQuestionImage')}
                        </p>
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">
                          {t('imageSearchHint')}
                        </p>
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col justify-between gap-4 rounded-xl border p-4">
                    <div>
                      <p className="flex items-center gap-2 text-sm font-medium">
                        <HugeiconsIcon
                          icon={Tick02Icon}
                          className="size-4 text-primary"
                        />
                        {t('pasteReady')}
                      </p>
                      <p className="mt-2 text-xs leading-5 text-muted-foreground">
                        {t('imageSearchHint')}
                      </p>
                    </div>
                    <div className="grid gap-2">
                      <input
                        ref={fileInput}
                        id="question-image"
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        capture="environment"
                        className="sr-only"
                        onChange={(event) => {
                          const file = event.target.files?.[0]
                          if (file) void acceptImage(file)
                          event.target.value = ''
                        }}
                      />
                      <Button
                        type="button"
                        variant={imageData ? 'outline' : 'default'}
                        onClick={() => fileInput.current?.click()}
                      >
                        <HugeiconsIcon
                          icon={Add01Icon}
                          data-icon="inline-start"
                        />
                        {imageData ? t('replaceImage') : t('chooseImage')}
                      </Button>
                      {imageData && (
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => {
                            setImageData('')
                          }}
                        >
                          <HugeiconsIcon
                            icon={Cancel01Icon}
                            data-icon="inline-start"
                          />
                          {t('removeImage')}
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="topic" className="m-0">
                <div className="space-y-2">
                  <Label htmlFor="topic-filter">{t('knowledgePoint')}</Label>
                  <Input
                    id="topic-filter"
                    type="search"
                    value={topicFilter}
                    onChange={(event) => setTopicFilter(event.target.value)}
                    placeholder={t('filterTopics')}
                  />
                  <div className="max-h-72 overflow-y-auto rounded-2xl border bg-muted/15 p-2">
                    <button
                      type="button"
                      className={`min-h-11 w-full rounded-xl px-3 text-left text-sm font-medium transition-colors ${topicCode === 'all' ? 'bg-primary/10 text-primary' : 'hover:bg-muted/70'}`}
                      onClick={() => setTopicCode('all')}
                    >
                      {t('allTopics')}
                    </button>
                    <div role="tree" aria-label={t('topicTree')}>
                      {visibleTopicTree.map((node) => (
                        <TopicTreeItem
                          key={node.id}
                          node={node}
                          depth={0}
                          expanded={expandedTopics}
                          selected={topicCode}
                          onToggle={(id) =>
                            setExpandedTopics((current) => {
                              const next = new Set(current)
                              if (next.has(id)) next.delete(id)
                              else next.add(id)
                              return next
                            })
                          }
                          onSelect={setTopicCode}
                        />
                      ))}
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t('chooseTopic')}
                  </p>
                </div>
              </TabsContent>
              <div className="mt-4 grid gap-4 border-t pt-4 md:grid-cols-[minmax(0,1fr)_240px_auto] md:items-end">
                <div className="space-y-2 md:col-start-2">
                  <Label>{t('examPrograms')}</Label>
                  <ExamTreeSelect
                    exams={exams}
                    value={examId}
                    allLabel={t('allExams')}
                    treeLabel={t('examPrograms')}
                    onValueChange={setExamId}
                  />
                </div>
                <Button
                  type="submit"
                  size="lg"
                  disabled={!canSearch() || loading}
                >
                  <HugeiconsIcon icon={Search01Icon} data-icon="inline-start" />
                  {t('search')}
                </Button>
              </div>
              {error && (
                <p role="alert" className="mt-4 text-sm text-destructive">
                  {error}
                </p>
              )}
            </form>
          </Tabs>
        </CardContent>
      </Card>
      <div className="relative z-0 min-h-[360px]">
        <Card className="overflow-hidden">
          <CardHeader className="border-b">
            <CardTitle className="text-base">
              {t('results')}{' '}
              {searched && (
                <span className="font-mono text-muted-foreground">
                  · {results.length}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="max-h-[620px] overflow-y-auto p-0">
            {loading && (
              <div className="space-y-3 p-4">
                {[1, 2, 3, 4].map((item) => (
                  <Skeleton key={item} className="h-24 w-full" />
                ))}
              </div>
            )}
            {!loading && searched && !results.length && (
              <p className="p-6 text-sm text-muted-foreground">
                {t('noResults')}
              </p>
            )}
            {!loading &&
              results.map((item) => (
                <button
                  key={`${item.exam_id}:${item.id}`}
                  type="button"
                  onClick={() => choose(item)}
                  className={`w-full border-b p-4 text-left transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${selected?.id === item.id ? 'bg-primary/7 shadow-[inset_3px_0_var(--primary)]' : ''}`}
                >
                  <span className="font-mono text-xs font-semibold text-primary">
                    {item.paper_key} · Q{item.question_number}
                  </span>
                  {item.topics?.length ? (
                    <span className="mt-3 flex flex-wrap gap-1">
                      {item.topics.map((topic) => (
                        <Badge key={topic} variant="secondary">
                          {topic}
                        </Badge>
                      ))}
                    </span>
                  ) : null}
                </button>
              ))}
          </CardContent>
        </Card>
      </div>
      <QuestionPreviewDialog
        question={selected}
        open={Boolean(selected)}
        onOpenChange={(open) => !open && setSelected(null)}
        similar={similar}
        onChooseSimilar={(item) => choose({ ...item, exam_id: selectedExamId })}
      />
    </section>
  )
}
