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
  qualification: string
  exam_board: string
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

export interface Topic {
  id: number
  parent_id: number | null
  code: string
  title: string
  description: string
  exam_id: string
  question_count: number
}

export interface ImageSearchResponse {
  extracted_text: string
  ocr_source: string
  results: Question[]
}

export interface TreeNode {
  id: string
  label: string
  kind: string
  count?: number
  paper_count?: number
  question_count?: number
  paper_id?: number
  exam_id?: string
  children: TreeNode[]
}
