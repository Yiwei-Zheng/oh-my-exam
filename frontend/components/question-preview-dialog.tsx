'use client'

import { useState, type ReactNode } from 'react'
import { HugeiconsIcon } from '@hugeicons/react'
import { FileValidationIcon, FileViewIcon } from '@hugeicons/core-free-icons'

import { useLocale } from '@/components/locale-provider'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { Question } from '@/lib/types'

function DocumentFrame({
  question,
  sourceType,
  title,
  errorMessage,
  sourcePage = false,
}: {
  question: Question
  sourceType: 0 | 1
  title: string
  errorMessage: string
  sourcePage?: boolean
}) {
  const [imageFailed, setImageFailed] = useState(false)
  const imageKind = sourceType === 0 ? 'question' : 'answer'
  const imageUrl = question.exam_id
    ? `/api/v1/exams/${encodeURIComponent(question.exam_id)}/questions/${question.id}/${sourcePage ? `source/${imageKind}` : imageKind}.jpg`
    : ''

  if (imageUrl && !imageFailed) {
    return (
      // The authenticated API serves dynamic catalog images.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={imageUrl}
        alt={title}
        onError={() => setImageFailed(true)}
        className="h-full min-h-[58dvh] w-full bg-white object-contain p-3"
      />
    )
  }

  return (
    <div
      role="alert"
      className="grid min-h-[58dvh] place-items-center p-6 text-center text-sm text-destructive"
    >
      {errorMessage}
    </div>
  )
}

export function QuestionPreviewDialog({
  question,
  open,
  onOpenChange,
  similar = [],
  onChooseSimilar,
  textPanel,
}: {
  question: Question | null
  open: boolean
  onOpenChange: (open: boolean) => void
  similar?: Question[]
  onChooseSimilar?: (question: Question) => void
  textPanel?: ReactNode
}) {
  const { t } = useLocale()
  const [view, setView] = useState<{
    questionId: number
    tab: 'question' | 'answer' | 'text'
    sourcePage: boolean
  } | null>(null)
  const activeView =
    question && view?.questionId === question.id
      ? view
      : {
          questionId: question?.id ?? 0,
          tab: 'question' as const,
          sourcePage: false,
        }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="h-[92dvh] max-w-[calc(100%-1rem)] gap-0 overflow-hidden p-0 sm:max-w-[min(1200px,calc(100%-2rem))]">
        {question && (
          <>
            <DialogHeader className="border-b px-5 py-4 pr-16">
              <DialogTitle className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-primary">
                  {question.paper_key}
                </span>
                <Badge variant="secondary">Q{question.question_number}</Badge>
              </DialogTitle>
              <DialogDescription>{t('questionPreview')}</DialogDescription>
            </DialogHeader>
            <Tabs
              value={activeView.tab}
              onValueChange={(tab) =>
                setView({
                  questionId: question.id,
                  tab: tab as 'question' | 'answer' | 'text',
                  sourcePage: false,
                })
              }
              className="flex min-h-0 flex-1 flex-col"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2">
                <TabsList>
                  <TabsTrigger value="question">{t('question')}</TabsTrigger>
                  <TabsTrigger value="answer">{t('answer')}</TabsTrigger>
                  {textPanel && (
                    <TabsTrigger value="text">{t('text')}</TabsTrigger>
                  )}
                </TabsList>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant={
                      activeView.sourcePage && activeView.tab === 'question'
                        ? 'secondary'
                        : 'outline'
                    }
                    onClick={() =>
                      setView({
                        questionId: question.id,
                        tab: 'question',
                        sourcePage: true,
                      })
                    }
                  >
                    <HugeiconsIcon
                      icon={FileViewIcon}
                      data-icon="inline-start"
                    />
                    {t('viewQuestionInPaper')}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={
                      activeView.sourcePage && activeView.tab === 'answer'
                        ? 'secondary'
                        : 'outline'
                    }
                    onClick={() =>
                      setView({
                        questionId: question.id,
                        tab: 'answer',
                        sourcePage: true,
                      })
                    }
                  >
                    <HugeiconsIcon
                      icon={FileValidationIcon}
                      data-icon="inline-start"
                    />
                    {t('viewAnswerInPaper')}
                  </Button>
                </div>
              </div>
              <TabsContent value="question" className="m-0 min-h-0 flex-1">
                <DocumentFrame
                  key={`${question.id}:question:${activeView.sourcePage ? 'source' : 'crop'}`}
                  question={question}
                  sourceType={0}
                  title={t('questionPdf')}
                  errorMessage={t('imageUnavailable')}
                  sourcePage={
                    activeView.sourcePage && activeView.tab === 'question'
                  }
                />
              </TabsContent>
              <TabsContent value="answer" className="m-0 min-h-0 flex-1">
                <DocumentFrame
                  key={`${question.id}:answer:${activeView.sourcePage ? 'source' : 'crop'}`}
                  question={question}
                  sourceType={1}
                  title={t('answerPdf')}
                  errorMessage={t('imageUnavailable')}
                  sourcePage={
                    activeView.sourcePage && activeView.tab === 'answer'
                  }
                />
              </TabsContent>
              {textPanel && (
                <TabsContent
                  value="text"
                  className="m-0 min-h-0 flex-1 overflow-y-auto p-5"
                >
                  {textPanel}
                </TabsContent>
              )}
            </Tabs>
            {similar.length > 0 && (
              <div className="max-h-32 overflow-y-auto border-t p-3">
                <p className="mb-2 text-sm font-semibold">{t('similar')}</p>
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {similar.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => onChooseSimilar?.(item)}
                      className="min-h-11 shrink-0 rounded-xl border px-3 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <span className="font-mono text-xs text-primary">
                        {item.paper_key} · Q{item.question_number}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
