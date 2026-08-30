'use client'

import type { AiBill } from '@/components/admin/types'
import { useLocale } from '@/components/locale-provider'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'

const tokens = new Intl.NumberFormat()

export function BillingPanel({ bill }: { bill: AiBill | null }) {
  const { t } = useLocale()
  if (!bill) return <Skeleton className="h-72 w-full" />
  const money = (microusd: number) => `$${(microusd / 1_000_000).toFixed(4)}`
  return (
    <div className="space-y-6">
      <p className="text-muted-foreground">{t('billingHint')}</p>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          [t('calls'), tokens.format(bill.calls)],
          [t('inputTokens'), tokens.format(bill.input_tokens)],
          [t('outputTokens'), tokens.format(bill.output_tokens)],
          [t('cost'), money(bill.cost_microusd)],
        ].map(([label, value]) => (
          <Card key={label}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                {label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="font-mono text-3xl font-semibold">{value}</p>
              <p className="mt-2 text-xs text-muted-foreground">
                {bill.month} · {bill.currency}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{t('currentMonth')}</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {bill.items.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('provider')}</TableHead>
                  <TableHead>{t('model')}</TableHead>
                  <TableHead className="text-right">{t('calls')}</TableHead>
                  <TableHead className="text-right">
                    {t('inputTokens')}
                  </TableHead>
                  <TableHead className="text-right">
                    {t('outputTokens')}
                  </TableHead>
                  <TableHead className="text-right">{t('cost')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {bill.items.map((item) => (
                  <TableRow key={`${item.provider}:${item.model}`}>
                    <TableCell>{item.provider}</TableCell>
                    <TableCell className="font-mono">{item.model}</TableCell>
                    <TableCell className="text-right font-mono">
                      {tokens.format(item.calls)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {tokens.format(item.input_tokens)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {tokens.format(item.output_tokens)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {money(item.cost_microusd)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="grid min-h-56 place-items-center p-8 text-center">
              <div>
                <p className="font-medium">{t('noUsage')}</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  {bill.month} · {bill.currency}
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
