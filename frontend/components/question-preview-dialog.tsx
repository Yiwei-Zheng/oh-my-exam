'use client'

import { useState, type ReactNode } from 'react'

import { useLocale } from '@/components/locale-provider'
import { Badge } from '@/components/ui/badge'
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
}: {
  question: Question
  sourceType: 0 | 1
  title: string
  errorMessage: string
}) {
  const [imageFailed, setImageFailed] = useState(false)
  const imageKind = sourceType === 0 ? 'question' : 'answer'
  const imageUrl = question.exam_id
    ? `/api/v1/exams/${encodeURIComponent(question.exam_id)}/questions/${question.id}/${imageKind}.jpg`
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
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="h-[92dvh] max-w-[calc(100%-1rem)] gap-0 overflow-hidden p-0 sm:max-w-[min(1200px,calc(100%-2rem))]">
        <QuestionPreview
          question={question}
          similar={similar}
          onChooseSimilar={onChooseSimilar}
          textPanel={textPanel}
          dialogTitle
        />
      </DialogContent>
    </Dialog>
  )
}

export function QuestionPreview({
  question,
  similar = [],
  onChooseSimilar,
  textPanel,
  dialogTitle = false,
}: {
  question: Question | null
  similar?: Question[]
  onChooseSimilar?: (question: Question) => void
  textPanel?: ReactNode
  dialogTitle?: boolean
}) {
  const { t } = useLocale()

  if (!question) return null
  return (
    <div className="flex h-full min-h-0 flex-col">
      <DialogHeader className="border-b px-5 py-4 pr-16">
        {dialogTitle ? (
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-primary">{question.paper_key}</span>
            <Badge variant="secondary">Q{question.question_number}</Badge>
          </DialogTitle>
        ) : (
          <h2 className="flex flex-wrap items-center gap-2 font-heading text-base font-medium">
            <span className="font-mono text-primary">{question.paper_key}</span>
            <Badge variant="secondary">Q{question.question_number}</Badge>
          </h2>
        )}
        {dialogTitle ? (
          <DialogDescription>{t('questionPreview')}</DialogDescription>
        ) : (
          <p className="text-sm text-muted-foreground">
            {t('questionPreview')}
          </p>
        )}
      </DialogHeader>
      <Tabs defaultValue="question" className="flex min-h-0 flex-1 flex-col">
        <div className="border-b px-4 py-2">
          <TabsList>
            <TabsTrigger value="question">{t('question')}</TabsTrigger>
            <TabsTrigger value="answer">{t('answer')}</TabsTrigger>
            {textPanel && <TabsTrigger value="text">{t('text')}</TabsTrigger>}
          </TabsList>
        </div>
        {similar.length > 0 && (
          <div className="border-b bg-muted/20 px-4 py-3">
            <p className="mb-2 text-xs font-semibold text-muted-foreground">
              {t('similar')}
            </p>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {similar.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onChooseSimilar?.(item)}
                  className="ui-interactive min-h-11 min-w-36 shrink-0 rounded-lg border bg-background px-3 py-2 text-left hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="block font-mono text-xs text-primary">
                    {item.paper_key} · Q{item.question_number}
                  </span>
                  {item.shared_topics?.length ? (
                    <span className="mt-1 block max-w-56 truncate text-xs text-muted-foreground">
                      {item.shared_topics.slice(0, 2).join(' · ')}
                    </span>
                  ) : null}
                </button>
              ))}
            </div>
          </div>
        )}
        <TabsContent value="question" className="m-0 min-h-0 flex-1">
          <DocumentFrame
            key={`${question.id}:question`}
            question={question}
            sourceType={0}
            title={t('questionPdf')}
            errorMessage={t('imageUnavailable')}
          />
        </TabsContent>
        <TabsContent value="answer" className="m-0 min-h-0 flex-1">
          <DocumentFrame
            key={`${question.id}:answer`}
            question={question}
            sourceType={1}
            title={t('answerPdf')}
            errorMessage={t('imageUnavailable')}
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
      <div className="flex flex-wrap items-center gap-2 border-t px-4 py-3">
        <span className="text-xs font-semibold text-muted-foreground">
          {t('tags')}
        </span>
        {question.topics?.length ? (
          question.topics.map((topic) => (
            <Badge key={topic} variant="secondary">
              {topic}
            </Badge>
          ))
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </div>
    </div>
  )
}
