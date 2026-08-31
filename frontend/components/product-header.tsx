'use client'

import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { useTheme } from 'next-themes'
import { HugeiconsIcon } from '@hugeicons/react'
import { Logout01Icon, Moon02Icon, Sun03Icon } from '@hugeicons/core-free-icons'

import { useAuth } from '@/components/auth-provider'
import { useLocale } from '@/components/locale-provider'
import { Button } from '@/components/ui/button'

export function ProductHeader() {
  const router = useRouter()
  const { user, logout } = useAuth()
  const { locale, t, toggleLocale } = useLocale()
  const { resolvedTheme, setTheme } = useTheme()

  async function signOut() {
    await logout()
    router.replace('/login')
  }

  return (
    <header className="ui-section-enter sticky top-0 z-40 flex min-h-14 items-center gap-3 border-b bg-background/92 px-4 backdrop-blur md:px-6">
      <Link
        href={user?.role === 'admin' ? '/admin' : '/questions'}
        className="mr-auto flex items-center gap-2 font-semibold tracking-tight"
      >
        <Image
          src="/app-icon.png"
          alt=""
          width={28}
          height={28}
          aria-hidden="true"
          className="size-7"
          priority
        />
        <span>Oh My Exam</span>
      </Link>
      {user?.role === 'admin' && (
        <>
          <Button variant="ghost" size="sm" render={<Link href="/admin" />}>
            {t('admin')}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="hidden md:inline-flex"
            render={<Link href="/admin/update" />}
          >
            {t('updateLibrary')}
          </Button>
        </>
      )}
      <Button variant="ghost" size="sm" render={<Link href="/questions" />}>
        {t('questions')}
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label={t('theme')}
        onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
      >
        <HugeiconsIcon
          icon={resolvedTheme === 'dark' ? Sun03Icon : Moon02Icon}
        />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label={t('switchLanguage')}
        onClick={toggleLocale}
      >
        <span className="font-mono text-xs font-semibold">
          {locale === 'zh-CN' ? 'EN' : '中'}
        </span>
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label={t('signOut')}
        onClick={signOut}
      >
        <HugeiconsIcon icon={Logout01Icon} />
      </Button>
    </header>
  )
}
