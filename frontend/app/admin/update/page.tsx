'use client'

import { QuestionUpdateWorkspace } from '@/components/admin/question-update-workspace'
import { AuthGate } from '@/components/auth-gate'

export default function QuestionUpdatePage() {
  return (
    <AuthGate admin>
      <QuestionUpdateWorkspace />
    </AuthGate>
  )
}
