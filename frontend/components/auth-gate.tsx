'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

import { useAuth } from '@/components/auth-provider'
import { useLocale } from '@/components/locale-provider'

export function AuthGate({
  children,
  admin = false,
}: {
  children: React.ReactNode
  admin?: boolean
}) {
  const router = useRouter()
  const { user, ready } = useAuth()
  const { t } = useLocale()

  useEffect(() => {
    if (!ready) return
    if (!user) router.replace('/login')
    else if (admin && user.role !== 'admin') router.replace('/questions')
  }, [admin, ready, router, user])

  if (!ready || !user || (admin && user.role !== 'admin')) {
    return (
      <main className="grid min-h-svh place-items-center text-sm text-muted-foreground">
        {t('loading')}
      </main>
    )
  }
  return children
}
