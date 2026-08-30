'use client'

import { FormEvent, useEffect, useState } from 'react'
import { HugeiconsIcon } from '@hugeicons/react'
import { Add01Icon, Copy01Icon, Delete02Icon } from '@hugeicons/core-free-icons'

import type { AdminUser, Invitation } from '@/components/admin/types'
import { useLocale } from '@/components/locale-provider'
import { Badge } from '@/components/ui/badge'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { apiRequest } from '@/lib/api'
import type { UserRole } from '@/lib/types'

export function AccountsPanel() {
  const { locale, t } = useLocale()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<UserRole>('student')
  const [invitationRole, setInvitationRole] = useState<UserRole>('student')
  const [maxUses, setMaxUses] = useState(1)
  const [validDays, setValidDays] = useState(7)
  const [revealedCode, setRevealedCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      apiRequest<{ users: AdminUser[] }>('/api/v1/admin/users'),
      apiRequest<{ invitations: Invitation[] }>('/api/v1/admin/invitations'),
    ])
      .then(([userPayload, invitationPayload]) => {
        setUsers(userPayload.users)
        setInvitations(invitationPayload.invitations)
      })
      .catch(() => setError(t('loadFailed')))
  }, [t])

  async function createUser(event: FormEvent) {
    event.preventDefault()
    if (!email || password.length < 15 || busy) return
    setBusy(true)
    setError('')
    try {
      const payload = await apiRequest<{ user: AdminUser }>(
        '/api/v1/admin/users',
        { method: 'POST', body: JSON.stringify({ email, password, role }) },
      )
      setUsers([payload.user, ...users])
      setEmail('')
      setPassword('')
    } catch {
      setError(t('loadFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function createInvitation(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    setRevealedCode('')
    try {
      const payload = await apiRequest<{
        invitation: Invitation
        code: string
      }>('/api/v1/admin/invitations', {
        method: 'POST',
        body: JSON.stringify({
          role: invitationRole,
          max_uses: maxUses,
          expires_in_days: validDays,
        }),
      })
      setInvitations([payload.invitation, ...invitations])
      setRevealedCode(payload.code)
    } catch {
      setError(t('loadFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function revoke(invitation: Invitation) {
    const payload = await apiRequest<{ invitation: Invitation }>(
      `/api/v1/admin/invitations/${invitation.id}`,
      { method: 'DELETE' },
    )
    setInvitations(
      invitations.map((item) =>
        item.id === invitation.id ? payload.invitation : item,
      ),
    )
  }

  const roleLabel = (value: UserRole) =>
    locale === 'zh-CN'
      ? { student: '学生', teacher: '教师', admin: '管理员' }[value]
      : value
  const date = (value: string) =>
    new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(
      new Date(value.endsWith('Z') ? value : `${value}Z`),
    )

  return (
    <div className="space-y-6">
      <p className="text-muted-foreground">{t('accountHint')}</p>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Tabs defaultValue="accounts">
        <TabsList>
          <TabsTrigger value="accounts">
            {t('existingAccounts')} · {users.length}
          </TabsTrigger>
          <TabsTrigger value="invitations">
            {t('invitations')} · {invitations.length}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="accounts" className="mt-4 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('createUser')}</CardTitle>
              <CardDescription>{t('passwordRule')}</CardDescription>
            </CardHeader>
            <CardContent>
              <form
                onSubmit={createUser}
                className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_180px_auto] md:items-end"
              >
                <div className="space-y-2">
                  <Label htmlFor="new-email">{t('email')}</Label>
                  <Input
                    id="new-email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="new-password">{t('password')}</Label>
                  <Input
                    id="new-password"
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t('role')}</Label>
                  <Select
                    value={role}
                    onValueChange={(value) =>
                      value && setRole(value as UserRole)
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(['student', 'teacher', 'admin'] as UserRole[]).map(
                        (item) => (
                          <SelectItem key={item} value={item}>
                            {roleLabel(item)}
                          </SelectItem>
                        ),
                      )}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  type="submit"
                  size="lg"
                  disabled={busy || !email || password.length < 15}
                >
                  <HugeiconsIcon icon={Add01Icon} data-icon="inline-start" />
                  {t('createUser')}
                </Button>
              </form>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('email')}</TableHead>
                    <TableHead>{t('role')}</TableHead>
                    <TableHead>{t('status')}</TableHead>
                    <TableHead>{t('createdAt')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell className="font-medium">
                        {user.email}
                      </TableCell>
                      <TableCell>{roleLabel(user.role)}</TableCell>
                      <TableCell>
                        <Badge
                          variant={user.is_active ? 'secondary' : 'outline'}
                        >
                          {user.is_active ? t('active') : t('inactive')}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {date(user.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="invitations" className="mt-4 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('createInvitation')}</CardTitle>
              <CardDescription>{t('invitationShownOnce')}</CardDescription>
            </CardHeader>
            <CardContent>
              <form
                onSubmit={createInvitation}
                className="grid gap-4 md:grid-cols-[180px_180px_180px_auto] md:items-end"
              >
                <div className="space-y-2">
                  <Label>{t('role')}</Label>
                  <Select
                    value={invitationRole}
                    onValueChange={(value) =>
                      value && setInvitationRole(value as UserRole)
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(['student', 'teacher', 'admin'] as UserRole[]).map(
                        (item) => (
                          <SelectItem key={item} value={item}>
                            {roleLabel(item)}
                          </SelectItem>
                        ),
                      )}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max-uses">{t('maxUses')}</Label>
                  <Input
                    id="max-uses"
                    type="number"
                    min={1}
                    max={100}
                    value={maxUses}
                    onChange={(event) => setMaxUses(Number(event.target.value))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="valid-days">{t('validDays')}</Label>
                  <Input
                    id="valid-days"
                    type="number"
                    min={1}
                    max={365}
                    value={validDays}
                    onChange={(event) =>
                      setValidDays(Number(event.target.value))
                    }
                  />
                </div>
                <Button type="submit" size="lg" disabled={busy}>
                  <HugeiconsIcon icon={Add01Icon} data-icon="inline-start" />
                  {t('createInvitation')}
                </Button>
              </form>
              {revealedCode && (
                <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary/25 bg-primary/5 p-4">
                  <div>
                    <p className="text-xs text-muted-foreground">
                      {t('invitationShownOnce')}
                    </p>
                    <code className="mt-1 block font-mono text-sm font-semibold">
                      {revealedCode}
                    </code>
                  </div>
                  <Button
                    variant="outline"
                    onClick={() => navigator.clipboard.writeText(revealedCode)}
                  >
                    <HugeiconsIcon icon={Copy01Icon} data-icon="inline-start" />
                    {t('copyCode')}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('invitation')}</TableHead>
                    <TableHead>{t('role')}</TableHead>
                    <TableHead>{t('status')}</TableHead>
                    <TableHead>{t('createdAt')}</TableHead>
                    <TableHead className="text-right" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invitations.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-mono">
                        •••• {item.code_hint}
                      </TableCell>
                      <TableCell>{roleLabel(item.role)}</TableCell>
                      <TableCell>
                        <Badge
                          variant={item.is_active ? 'secondary' : 'outline'}
                        >
                          {item.used_count}/{item.max_uses}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {date(item.expires_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={t('revoke')}
                          disabled={!item.is_active}
                          onClick={() => revoke(item)}
                        >
                          <HugeiconsIcon icon={Delete02Icon} />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
