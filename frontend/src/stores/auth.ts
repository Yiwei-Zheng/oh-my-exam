import { defineStore } from 'pinia'
import { ref } from 'vue'

import { ApiError, apiRequest } from '../shared/api'

export type UserRole = 'student' | 'teacher' | 'admin'

export interface CurrentUser {
  id: number
  email: string
  role: UserRole
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(null)
  const checked = ref(false)

  async function fetchMe() {
    try {
      const payload = await apiRequest<{ user: CurrentUser }>('/api/v1/me')
      user.value = payload.user
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error
      user.value = null
    } finally {
      checked.value = true
    }
    return user.value
  }

  async function login(email: string, password: string) {
    const payload = await apiRequest<{ user: CurrentUser }>(
      '/api/v1/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      },
    )
    user.value = payload.user
    checked.value = true
    return payload.user
  }

  async function logout() {
    await apiRequest<void>('/api/v1/auth/logout', { method: 'POST' })
    user.value = null
    checked.value = true
  }

  return { user, checked, fetchMe, login, logout }
})
