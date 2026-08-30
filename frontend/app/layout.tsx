import type { Metadata } from 'next'
import { Figtree, Geist_Mono } from 'next/font/google'

import './globals.css'
import { AppProviders } from '@/components/app-providers'
import { cn } from '@/lib/utils'

const figtree = Figtree({ subsets: ['latin'], variable: '--font-sans' })
const fontMono = Geist_Mono({ subsets: ['latin'], variable: '--font-mono' })

export const metadata: Metadata = {
  title: 'Oh My Exam',
  description: 'Question intelligence workspace',
  icons: {
    icon: {
      url: '/app-icon.png',
      type: 'image/png',
      sizes: '1254x1254',
    },
    shortcut: '/favicon.ico',
    apple: {
      url: '/apple-touch-icon.png',
      sizes: '180x180',
      type: 'image/png',
    },
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html
      lang="zh-CN"
      suppressHydrationWarning
      className={cn(
        'font-sans antialiased',
        fontMono.variable,
        figtree.variable,
      )}
    >
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  )
}
