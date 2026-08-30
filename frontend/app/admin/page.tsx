'use client'

import { AuthGate } from '@/components/auth-gate'
import { AdminDashboard } from '@/components/admin/admin-dashboard'

export default function AdminPage() {
  return (
    <AuthGate admin>
      <AdminDashboard />
    </AuthGate>
  )
}
