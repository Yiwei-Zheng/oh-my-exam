'use client'

import { FormEvent, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { HugeiconsIcon } from '@hugeicons/react'
import {
  ArrowRight01Icon,
  ViewIcon,
  ViewOffIcon,
} from '@hugeicons/core-free-icons'

import { useAuth } from '@/components/auth-provider'
import { useLocale } from '@/components/locale-provider'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError, apiRequest } from '@/lib/api'

export default function LoginPage() {
  const router = useRouter()
  const { user, ready, login } = useAuth()
  const { locale, t, toggleLocale } = useLocale()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [invitation, setInvitation] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (ready && user)
      router.replace(user.role === 'admin' ? '/admin' : '/questions')
  }, [ready, router, user])

  const valid =
    email.includes('@') &&
    password.length >= (mode === 'register' ? 15 : 1) &&
    (mode === 'login' || invitation.length >= 8)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!valid || loading) return
    setLoading(true)
    setError('')
    try {
      if (mode === 'register')
        await apiRequest('/api/v1/auth/register', {
          method: 'POST',
          body: JSON.stringify({
            email: email.trim(),
            password,
            invitation_code: invitation.trim(),
          }),
        })
      const loggedIn = await login(email.trim(), password)
      const redirect = new URLSearchParams(window.location.search).get(
        'redirect',
      )
      router.replace(
        redirect || (loggedIn.role === 'admin' ? '/admin' : '/questions'),
      )
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401)
        setError(t('invalidCredentials'))
      else if (caught instanceof ApiError && caught.status === 429)
        setError(t('rateLimited'))
      else if (
        caught instanceof ApiError &&
        caught.detail === 'invalid_or_expired_invitation'
      )
        setError(t('invalidInvitation'))
      else setError(t('unavailable'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="relative grid min-h-svh overflow-hidden bg-muted/35 lg:grid-cols-[1.1fr_.9fr]">
      <Button
        variant="outline"
        size="icon"
        className="absolute right-5 top-5 z-10 bg-background"
        aria-label={t('switchLanguage')}
        onClick={toggleLocale}
      >
        <span className="font-mono text-xs font-bold">
          {locale === 'zh-CN' ? 'EN' : '中'}
        </span>
      </Button>
      <section className="relative hidden overflow-hidden border-r p-12 lg:flex lg:flex-col lg:justify-between">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:36px_36px] opacity-40" />
        <div className="relative flex items-center gap-3 font-semibold">
          <span className="grid size-9 place-items-center rounded-xl bg-primary text-primary-foreground">
            O
          </span>
          OH MY EXAM
        </div>
        <div className="relative max-w-xl">
          <p className="mb-4 font-mono text-xs font-bold uppercase tracking-[.2em] text-primary">
            Question intelligence / STEM
          </p>
          <h1 className="text-6xl font-semibold leading-[.95] tracking-[-.055em]">
            Every paper.
            <br />
            One clear desk.
          </h1>
          <p className="mt-6 max-w-md text-lg leading-8 text-muted-foreground">
            {t('loginHint')}
          </p>
          <div className="mt-8 flex gap-2">
            {['CAIE', 'STEP', 'TMUA', 'PAT'].map((item) => (
              <span
                key={item}
                className="rounded-full border bg-background px-3 py-1 font-mono text-xs"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
        <p className="relative font-mono text-xs text-muted-foreground">
          CATALOG / SEARCH / REVIEW
        </p>
      </section>
      <section className="grid place-items-center p-5 md:p-10">
        <Card className="w-full max-w-md shadow-xl shadow-primary/5">
          <CardHeader>
            <CardTitle className="text-2xl">
              {mode === 'login' ? t('loginTitle') : t('registerTitle')}
            </CardTitle>
            <CardDescription>{t('loginHint')}</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={submit} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="email">{t('email')}</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="username"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">{t('password')}</Label>
                <div className="relative">
                  <Input
                    id="password"
                    className="pr-11"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete={
                      mode === 'login' ? 'current-password' : 'new-password'
                    }
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                  <button
                    type="button"
                    className="absolute right-0 top-0 grid size-9 place-items-center text-muted-foreground"
                    aria-label={t('password')}
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    <HugeiconsIcon
                      icon={showPassword ? ViewOffIcon : ViewIcon}
                    />
                  </button>
                </div>
                {mode === 'register' && (
                  <p className="text-xs text-muted-foreground">
                    {t('passwordRule')}
                  </p>
                )}
              </div>
              {mode === 'register' && (
                <div className="space-y-2">
                  <Label htmlFor="invitation">{t('invitation')}</Label>
                  <Input
                    id="invitation"
                    autoComplete="one-time-code"
                    placeholder="OME-XXXXXX-XXXXXX-XXXXXX"
                    value={invitation}
                    onChange={(event) => setInvitation(event.target.value)}
                  />
                </div>
              )}
              {error && (
                <p role="alert" className="text-sm text-destructive">
                  {error}
                </p>
              )}
              <Button
                type="submit"
                size="lg"
                className="w-full"
                disabled={!valid || loading}
              >
                {mode === 'login' ? t('signIn') : t('createAccount')}
                <HugeiconsIcon icon={ArrowRight01Icon} data-icon="inline-end" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="w-full"
                onClick={() => {
                  setMode(mode === 'login' ? 'register' : 'login')
                  setError('')
                }}
              >
                {mode === 'login' ? t('useInvitation') : t('backToLogin')}
              </Button>
            </form>
          </CardContent>
        </Card>
      </section>
    </main>
  )
}
