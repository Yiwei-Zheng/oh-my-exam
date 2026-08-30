'use client'

import { FormEvent, useEffect, useMemo, useState } from 'react'
import { HugeiconsIcon } from '@hugeicons/react'
import { BookSearchIcon, Search01Icon } from '@hugeicons/core-free-icons'

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
import { apiRequest } from '@/lib/api'
import type { Exam, Question } from '@/lib/types'

export function QuestionSearch({ compact = false }: { compact?: boolean }) {
  const { t } = useLocale()
  const [exams, setExams] = useState<Exam[]>([])
  const [query, setQuery] = useState('')
  const [examId, setExamId] = useState('all')
  const [results, setResults] = useState<Question[]>([])
  const [selected, setSelected] = useState<Question | null>(null)
  const [similar, setSimilar] = useState<Question[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    apiRequest<Exam[]>('/api/v1/exams')
      .then(setExams)
      .catch(() => setError(t('loadFailed')))
  }, [t])

  const selectedExamId = selected?.exam_id || (examId === 'all' ? '' : examId)
  const pdfUrl = useMemo(
    () =>
      selected && selectedExamId
        ? `/api/v1/exams/${encodeURIComponent(selectedExamId)}/questions/${selected.id}/question.pdf`
        : '',
    [selected, selectedExamId],
  )

  async function search(event: FormEvent) {
    event.preventDefault()
    if (!query.trim() || loading) return
    setLoading(true)
    setSearched(true)
    setError('')
    setSelected(null)
    setSimilar([])
    try {
      const params = new URLSearchParams({ query: query.trim(), limit: '50' })
      if (examId !== 'all') params.set('exam_id', examId)
      setResults(
        await apiRequest<Question[]>(`/api/v1/questions/search?${params}`),
      )
    } catch {
      setResults([])
      setError(t('loadFailed'))
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
      <Card>
        <CardContent className="pt-6">
          <form
            onSubmit={search}
            className="grid gap-4 md:grid-cols-[minmax(0,1fr)_240px_auto] md:items-end"
          >
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
            <div className="space-y-2">
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
                      {exam.course_code.toUpperCase()} · {exam.question_count}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" size="lg" disabled={!query.trim() || loading}>
              <HugeiconsIcon icon={Search01Icon} data-icon="inline-start" />
              {t('search')}
            </Button>
          </form>
          {error && (
            <p role="alert" className="mt-4 text-sm text-destructive">
              {error}
            </p>
          )}
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
