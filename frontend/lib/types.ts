export type UserRole = 'student' | 'teacher' | 'admin'

export interface CurrentUser {
  id: number
  email: string
  role: UserRole
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export interface Exam {
  id: string
  course_code: string
  display_name: string
  paper_count: number
  question_count: number
}

export interface AnswerStructured {
  version: number
  raw_text: string
  markdown: string
  status: string
}

export interface Question {
  id: number
  exam_id?: string
  paper_id: number
  paper_key: string
  question_number: string
  local_key: string
  content: string
  topics?: string[]
  score?: number
  shared_topics?: string[]
  answer_structured?: AnswerStructured | null
}

export interface TreeNode {
  id: string
  label: string
  kind: string
  count?: number
  paper_id?: number
  exam_id?: string
  children: TreeNode[]
}
