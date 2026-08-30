import type { Exam, UserRole } from '@/lib/types'

export interface AdminStats {
  users_total: number
  active_7d: number
  roles: Record<UserRole, number>
  activity: { date: string; count: number }[]
}

export interface AssetInventory {
  exam_programs: number
  papers: number
  questions: number
  source_documents: number
  searchable_questions: number
  answered_questions: number
  searchable_coverage: number
  answer_coverage: number
  by_exam: Exam[]
}

export interface AiBillItem {
  provider: string
  model: string
  calls: number
  input_tokens: number
  output_tokens: number
  cost_microusd: number
}

export interface AiBill {
  month: string
  currency: 'USD'
  calls: number
  input_tokens: number
  output_tokens: number
  cost_microusd: number
  items: AiBillItem[]
}

export interface AdminUser {
  id: number
  email: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface Invitation {
  id: number
  code_hint: string
  role: UserRole
  max_uses: number
  used_count: number
  expires_at: string
  is_active: boolean
  created_at: string
}
