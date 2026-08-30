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
  BookSearchIcon,
  Cancel01Icon,
  Search01Icon,
  Tick02Icon,
} from '@hugeicons/core-free-icons'

import { useLocale } from '@/components/locale-provider'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ApiError, apiRequest } from '@/lib/api'
import type { Exam, ImageSearchResponse, Question, Topic } from '@/lib/types'

type SearchMode = 'text' | 'image' | 'topic'
const ACCEPTED_IMAGES = ['image/jpeg', 'image/png', 'image/webp']

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
  const [imageData, setImageData] = useState('')
  const [recognizedText, setRecognizedText] = useState('')
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
        setRecognizedText('')
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
  const pdfUrl = useMemo(
    () =>
      selected && selectedExamId
        ? `/api/v1/exams/${encodeURIComponent(selectedExamId)}/questions/${selected.id}/question.pdf`
        : '',
    [selected, selectedExamId],
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
    setRecognizedText('')
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
              limit: 50,
            }),
          },
        )
        setRecognizedText(response.extracted_text)
        setResults(response.results)
      } else {
        const params = new URLSearchParams({
          query: mode === 'text' ? query.trim() : '',
          limit: '50',
        })
        if (examId !== 'all') params.set('exam_id', examId)
        if (mode === 'topic' && topicCode !== 'all') {
          params.append('topic', topicCode)
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
    setSelected(question)
    setSimilar([])
    if (!resolved) return
    try {
      setSimilar(
        await apiRequest<Question[]>(
          `/api/v1/exams/${encodeURIComponent(resolved)}/questions/${question.id}/similar?limit=8`,
        ),
      )
    } catch {
      setError(t('loadFailed'))
    }
  }

  return (
    <section
      className={
        compact
          ? 'space-y-4'
          : 'mx-auto w-full max-w-[1480px] space-y-6 p-4 md:p-8'
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
      <Card className="overflow-hidden">
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
                            setRecognizedText('')
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
                  <Label>{t('knowledgePoint')}</Label>
                  <Select
                    value={topicCode}
                    onValueChange={(value) => value && setTopicCode(value)}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder={t('chooseTopic')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('allTopics')}</SelectItem>
                      {topics.map((topic) => (
                        <SelectItem key={topic.code} value={topic.code}>
                          {topic.title} · {topic.question_count}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    {t('chooseTopic')}
                  </p>
                </div>
              </TabsContent>
              <div className="mt-4 grid gap-4 border-t pt-4 md:grid-cols-[minmax(0,1fr)_240px_auto] md:items-end">
                <div className="space-y-2 md:col-start-2">
                  <Label>{t('examPrograms')}</Label>
                  <Select
                    value={examId}
                    onValueChange={(value) => value && setExamId(value)}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('allExams')}</SelectItem>
                      {exams.map((exam) => (
                        <SelectItem key={exam.id} value={exam.id}>
                          {exam.course_code.toUpperCase()} ·{' '}
                          {exam.question_count}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
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
              {recognizedText && (
                <div className="mt-4 rounded-xl border bg-muted/35 p-4">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-primary">
                    {t('recognizedText')}
                  </p>
                  <p className="line-clamp-3 text-sm text-muted-foreground">
                    {recognizedText}
                  </p>
                </div>
              )}
            </form>
          </Tabs>
        </CardContent>
      </Card>
      <div className="grid min-h-[560px] gap-4 lg:grid-cols-[380px_minmax(0,1fr)]">
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
          <CardContent className="max-h-[720px] overflow-y-auto p-0">
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
                  <span className="mt-2 line-clamp-3 block text-sm leading-6 text-muted-foreground">
                    {item.content || item.local_key}
                  </span>
                  {item.topics?.length ? (
                    <span className="mt-3 flex flex-wrap gap-1">
                      {item.topics.slice(0, 3).map((topic) => (
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
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            {!selected ? (
              <div className="grid min-h-[560px] place-items-center p-8 text-center text-muted-foreground">
                <div>
                  <HugeiconsIcon
                    icon={BookSearchIcon}
                    className="mx-auto mb-4 size-10 text-primary"
                  />
                  <p>{t('chooseQuestion')}</p>
                </div>
              </div>
            ) : (
              <div>
                <div className="flex items-center justify-between border-b p-4">
                  <div>
                    <p className="font-mono text-xs text-primary">
                      {selected.paper_key}
                    </p>
                    <h2 className="font-semibold">
                      Q{selected.question_number}
                    </h2>
                  </div>
                  <Button
                    variant="outline"
                    render={
                      <a href={pdfUrl} target="_blank" rel="noreferrer" />
                    }
                  >
                    {t('openPdf')}
                  </Button>
                </div>
                <iframe
                  src={pdfUrl}
                  title={`${selected.paper_key} question ${selected.question_number}`}
                  className="h-[560px] w-full bg-muted"
                />
                <div className="border-t p-4">
                  <h3 className="mb-3 font-semibold">{t('similar')}</h3>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {similar.map((item) => (
                      <button
                        key={item.id}
                        onClick={() =>
                          choose({ ...item, exam_id: selectedExamId })
                        }
                        className="rounded-xl border p-3 text-left text-sm hover:bg-muted"
                      >
                        <span className="font-mono text-xs text-primary">
                          {item.paper_key} · Q{item.question_number}
                        </span>
                        <span className="mt-1 line-clamp-2 block text-muted-foreground">
                          {item.content}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </section>
  )
}
