'use client'

import { AuthGate } from '@/components/auth-gate'
import { ProductHeader } from '@/components/product-header'
import { QuestionSearch } from '@/components/question-search'

export default function QuestionsPage() {
  return (
    <AuthGate>
      <ProductHeader />
      <main>
        <QuestionSearch />
      </main>
    </AuthGate>
  )
}
