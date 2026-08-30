'use client'

import { useEffect, useId, useMemo, useRef, useState } from 'react'
import {
  ArrowDown01Icon,
  ArrowRight01Icon,
  Tick02Icon,
} from '@hugeicons/core-free-icons'
import { HugeiconsIcon } from '@hugeicons/react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { Exam } from '@/lib/types'

interface ExamGroup {
  id: string
  label: string
  children: ExamGroup[]
  exam?: Exam
}

function groupExams(exams: Exam[]): ExamGroup[] {
  const qualifications = new Map<string, ExamGroup>()

  for (const exam of exams) {
    let qualification = qualifications.get(exam.qualification)
    if (!qualification) {
      qualification = {
        id: `qualification:${exam.qualification}`,
        label: exam.qualification.replaceAll('_', ' ').toUpperCase(),
        children: [],
      }
      qualifications.set(exam.qualification, qualification)
    }

    let board = qualification.children.find(
      (node) => node.id === `board:${exam.qualification}:${exam.exam_board}`,
    )
    if (!board) {
      board = {
        id: `board:${exam.qualification}:${exam.exam_board}`,
        label: exam.exam_board.replaceAll('_', ' ').toUpperCase(),
        children: [],
      }
      qualification.children.push(board)
    }

    board.children.push({
      id: exam.id,
      label: exam.course_code.toUpperCase(),
      children: [],
      exam,
    })
  }

  return [...qualifications.values()]
}

function branchIds(nodes: ExamGroup[]): string[] {
  return nodes.flatMap((node) =>
    node.children.length ? [node.id, ...branchIds(node.children)] : [],
  )
}

function ExamTreeItem({
  node,
  depth,
  expanded,
  selected,
  onToggle,
  onSelect,
}: {
  node: ExamGroup
  depth: number
  expanded: Set<string>
  selected: string
  onToggle: (id: string) => void
  onSelect: (id: string) => void
}) {
  const isBranch = node.children.length > 0
  const isExpanded = expanded.has(node.id)
  const isSelected = node.exam?.id === selected

  return (
    <div
      role="treeitem"
      aria-expanded={isBranch ? isExpanded : undefined}
      aria-selected={node.exam ? isSelected : undefined}
    >
      <button
        type="button"
        className={cn(
          'ui-interactive flex min-h-11 w-full items-center gap-2 rounded-xl pr-3 text-left text-sm transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          isSelected && 'bg-primary/10 text-primary',
        )}
        style={{ paddingLeft: `${8 + depth * 16}px` }}
        onClick={() =>
          isBranch ? onToggle(node.id) : node.exam && onSelect(node.exam.id)
        }
      >
        <HugeiconsIcon
          icon={ArrowRight01Icon}
          className={cn(
            'size-4 shrink-0 transition-transform duration-200',
            isExpanded && 'rotate-90',
            !isBranch && 'opacity-25',
          )}
        />
        <span className="min-w-0 flex-1 truncate font-medium">
          {node.label}
        </span>
        {node.exam && (
          <span className="font-mono text-xs tabular-nums text-muted-foreground">
            {node.exam.question_count.toLocaleString()}
          </span>
        )}
        {isSelected && (
          <HugeiconsIcon icon={Tick02Icon} className="size-4 shrink-0" />
        )}
      </button>
      {isBranch && isExpanded && (
        <div role="group" className="ui-tree-enter">
          {node.children.map((child) => (
            <ExamTreeItem
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

export function ExamTreeSelect({
  exams,
  value,
  allLabel,
  treeLabel,
  onValueChange,
}: {
  exams: Exam[]
  value: string
  allLabel: string
  treeLabel: string
  onValueChange: (value: string) => void
}) {
  const treeId = useId()
  const containerRef = useRef<HTMLDivElement>(null)
  const nodes = useMemo(() => groupExams(exams), [exams])
  const [open, setOpen] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const selectedExam = exams.find((exam) => exam.id === value)

  useEffect(() => {
    if (!open) return
    function closeOutside(event: PointerEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', closeOutside)
    return () => document.removeEventListener('pointerdown', closeOutside)
  }, [open])

  function select(next: string) {
    const exam = exams.find((item) => item.id === next)
    if (exam) {
      setExpanded(
        new Set([
          `qualification:${exam.qualification}`,
          `board:${exam.qualification}:${exam.exam_board}`,
        ]),
      )
    }
    onValueChange(next)
    setOpen(false)
  }

  function toggleOpen() {
    if (!open && expanded.size === 0) setExpanded(new Set(branchIds(nodes)))
    setOpen((current) => !current)
  }

  return (
    <div
      ref={containerRef}
      className="relative"
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          setOpen(false)
          containerRef.current?.querySelector('button')?.focus()
        }
      }}
    >
      <Button
        type="button"
        variant="outline"
        className="h-11 w-full justify-between bg-input/50 px-3 font-normal"
        aria-controls={treeId}
        aria-expanded={open}
        onClick={toggleOpen}
      >
        <span className="min-w-0 truncate">
          {selectedExam
            ? `${selectedExam.course_code.toUpperCase()} · ${selectedExam.question_count.toLocaleString()}`
            : allLabel}
        </span>
        <HugeiconsIcon
          icon={ArrowDown01Icon}
          className={cn(
            'size-4 shrink-0 text-muted-foreground transition-transform duration-200',
            open && 'rotate-180',
          )}
        />
      </Button>
      {open && (
        <div
          id={treeId}
          className="absolute right-0 z-40 mt-2 max-h-[min(24rem,60vh)] w-[min(28rem,calc(100vw-2rem))] overflow-y-auto rounded-2xl bg-popover p-2 text-popover-foreground shadow-lg ring-1 ring-foreground/5 dark:ring-foreground/10"
        >
          <button
            type="button"
            aria-pressed={value === 'all'}
            className={cn(
              'ui-interactive flex min-h-11 w-full items-center justify-between rounded-xl px-3 text-left text-sm font-medium transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              value === 'all' && 'bg-primary/10 text-primary',
            )}
            onClick={() => select('all')}
          >
            {allLabel}
            {value === 'all' && (
              <HugeiconsIcon icon={Tick02Icon} className="size-4 shrink-0" />
            )}
          </button>
          <div role="tree" aria-label={treeLabel}>
            {nodes.map((node) => (
              <ExamTreeItem
                key={node.id}
                node={node}
                depth={0}
                expanded={expanded}
                selected={value}
                onToggle={(id) =>
                  setExpanded((current) => {
                    const next = new Set(current)
                    if (next.has(id)) next.delete(id)
                    else next.add(id)
                    return next
                  })
                }
                onSelect={select}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
