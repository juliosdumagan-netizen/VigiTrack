import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { AppSidebar } from '@/components/layout/app-sidebar'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { useAuth } from '@/lib/auth'

const titles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/cameras': 'Cameras',
  '/incidents': 'Incidents',
  '/users': 'Users',
  '/account': 'My account',
  '/settings': 'Settings',
}

export function DashboardLayout() {
  const location = useLocation()
  const { user, loading, error } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-svh items-center justify-center text-sm text-muted-foreground">
        Checking session…
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-svh flex-col items-center justify-center gap-2 p-6 text-center">
        <p className="font-medium">Cannot reach the VigiTrack backend</p>
        <p className="max-w-md text-sm text-muted-foreground">
          Check that <code>python run.py</code> is running in the backend folder, and that the frontend was started
          with the same <code>VIGITRACK_PORT</code>. ({error})
        </p>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (user.must_change_password && location.pathname !== '/account') {
    return <Navigate to="/account" replace />
  }

  const title = titles[location.pathname] ?? 'VigiTrack'

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <h1 className="text-sm font-medium">{title}</h1>
          <div className="ml-auto">
            <Badge variant="outline" className="gap-1.5">
              <span className="size-2 rounded-full bg-emerald-500" />
              System Online
            </Badge>
          </div>
        </header>
        <main className="flex flex-1 flex-col gap-4 p-4 md:p-6">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
