'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'

import { ApiError, apiRequest } from '@/lib/api'
import type { CurrentUser } from '@/lib/types'

interface AuthContextValue {
  user: CurrentUser | null
  ready: boolean
  login: (email: string, password: string) => Promise<CurrentUser>
  logout: () => Promise<void>
  refresh: () => Promise<CurrentUser | null>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [ready, setReady] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const payload = await apiRequest<{ user: CurrentUser }>('/api/v1/me')
      setUser(payload.user)
      return payload.user
    } catch (error) {
      if (error instanceof ApiError && error.status !== 401) {
        console.warn('Session check unavailable', error.status)
      }
      setUser(null)
      return null
    } finally {
      setReady(true)
    }
  }, [])

  useEffect(() => {
    // Authentication is loaded once from the HttpOnly session cookie.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh()
  }, [refresh])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      ready,
      refresh,
      async login(email, password) {
        const payload = await apiRequest<{ user: CurrentUser }>(
          '/api/v1/auth/login',
          {
            method: 'POST',
            body: JSON.stringify({ email, password }),
          },
        )
        setUser(payload.user)
        return payload.user
      },
      async logout() {
        await apiRequest<void>('/api/v1/auth/logout', { method: 'POST' })
        setUser(null)
      },
    }),
    [ready, refresh, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used within AuthProvider')
  return value
}
