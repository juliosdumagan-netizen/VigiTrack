import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { DashboardLayout } from '@/components/layout/dashboard-layout'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AuthProvider } from '@/lib/auth'
import { AccountPage } from '@/pages/account'
import { CamerasPage } from '@/pages/cameras'
import { DashboardPage } from '@/pages/dashboard'
import { IncidentsPage } from '@/pages/incidents'
import { LandingPage } from '@/pages/landing'
import { LoginPage } from '@/pages/login'
import { SettingsPage } from '@/pages/settings'
import { SetupPage } from '@/pages/setup'
import { UsersPage } from '@/pages/users'

export default function App() {
  return (
    <TooltipProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/setup" element={<SetupPage />} />
            <Route element={<DashboardLayout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/cameras" element={<CamerasPage />} />
              <Route path="/incidents" element={<IncidentsPage />} />
              <Route path="/users" element={<UsersPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/account" element={<AccountPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </TooltipProvider>
  )
}
