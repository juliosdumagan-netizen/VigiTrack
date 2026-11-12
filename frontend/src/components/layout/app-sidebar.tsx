import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Camera, LayoutDashboard, LogOut, Settings, ShieldAlert, User as UserIcon, Users } from 'lucide-react'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
import { useAuth } from '@/lib/auth'

const navItems = [
  { title: 'Dashboard', to: '/dashboard', icon: LayoutDashboard, adminOnly: false },
  { title: 'Cameras', to: '/cameras', icon: Camera, adminOnly: false },
  { title: 'Incidents', to: '/incidents', icon: ShieldAlert, adminOnly: false },
  { title: 'Users', to: '/users', icon: Users, adminOnly: true },
  { title: 'Settings', to: '/settings', icon: Settings, adminOnly: true },
  { title: 'My account', to: '/account', icon: UserIcon, adminOnly: false },
]

export function AppSidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, isAdmin, logout } = useAuth()

  const visibleItems = navItems.filter(
    (item) => !user?.must_change_password || item.to === '/account',
  ).filter((item) => !item.adminOnly || isAdmin)

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link to="/dashboard">
                <img src="/assets/logo.png" alt="VigiTrack logo" className="size-8 shrink-0 rounded-lg object-contain" />
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">VigiTrack</span>
                  <span className="truncate text-xs text-muted-foreground">Surveillance Hub</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {visibleItems.map((item) => (
                <SidebarMenuItem key={item.to}>
                  <SidebarMenuButton asChild tooltip={item.title} isActive={location.pathname.startsWith(item.to)}>
                    <Link to={item.to}>
                      <item.icon />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        {user && (
          <div className="grid px-2 py-1 text-xs group-data-[collapsible=icon]:hidden">
            <span className="truncate font-medium">{user.username}</span>
            <span className="capitalize text-muted-foreground">{user.role}</span>
          </div>
        )}
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton tooltip="Log out" onClick={handleLogout}>
              <LogOut />
              <span>Log out</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
