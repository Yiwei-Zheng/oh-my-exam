'use client'

import { useEffect, useState } from 'react'

import { AssetsPanel } from '@/components/admin/assets-panel'
import type { AssetInventory } from '@/components/admin/types'
import { AuthGate } from '@/components/auth-gate'
import { ProductHeader } from '@/components/product-header'
import { apiRequest } from '@/lib/api'

export default function LibraryPage() {
  const [inventory, setInventory] = useState<AssetInventory | null>(null)

  useEffect(() => {
    apiRequest<AssetInventory>('/api/v1/assets').then(setInventory)
  }, [])

  return (
    <AuthGate>
      <ProductHeader />
      <main className="ui-page-enter mx-auto w-full max-w-[1680px] p-4 md:p-8">
        <AssetsPanel
          inventory={inventory}
          onInventory={setInventory}
          readOnly
        />
      </main>
    </AuthGate>
  )
}
