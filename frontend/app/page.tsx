'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

import { useAuth } from '@/components/auth-provider'

export default function Home() {
  const router = useRouter()
  const { user, ready } = useAuth()

  useEffect(() => {
    if (!ready) return
    router.replace(
      user?.role === 'admin' ? '/admin' : user ? '/questions' : '/login',
    )
  }, [ready, router, user])

  return (
    <main className="grid min-h-svh place-items-center text-sm text-muted-foreground">
      Loading…
    </main>
  )
}
