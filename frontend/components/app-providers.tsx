'use client'

import { AuthProvider } from '@/components/auth-provider'
import { LocaleProvider } from '@/components/locale-provider'
import { ThemeProvider } from '@/components/theme-provider'

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <LocaleProvider>
        <AuthProvider>{children}</AuthProvider>
      </LocaleProvider>
    </ThemeProvider>
  )
}
