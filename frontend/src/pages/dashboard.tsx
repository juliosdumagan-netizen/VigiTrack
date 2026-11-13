import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardAction } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api, UnauthorizedError, type Alert, type CameraStatus, type Settings } from '@/lib/api'

export function DashboardPage() {
  const navigate = useNavigate()
  const [settings, setSettings] = useState<Settings | null>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [camera, setCamera] = useState<CameraStatus | null>(null)

  useEffect(() => {
    let active = true
    const pollStatus = () =>
      api
        .getCameraStatus()
        .then((s) => active && setCamera(s))
        .catch(() => undefined)

    pollStatus()
    const timer = setInterval(pollStatus, 3000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    let active = true

    const handleError = (err: unknown) => {
      if (err instanceof UnauthorizedError) navigate('/login', { replace: true })
    }

    api.getSettings().then((s) => active && setSettings(s)).catch(handleError)

    const poll = () =>
      api
        .getAlerts()
        .then((a) => active && setAlerts(a))
        .catch(handleError)

    poll()
    const timer = setInterval(poll, 2000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [navigate])

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>{settings?.camera_name ?? 'Camera'}</CardTitle>
          <CardDescription>Live feed with person and object detection</CardDescription>
          <CardAction>
            <Badge variant="destructive">● Live</Badge>
          </CardAction>
        </CardHeader>
        <CardContent>
          <div className="relative aspect-video overflow-hidden rounded-lg bg-black">
            <img src="/video_feed" alt="Live surveillance feed" className="size-full object-contain" />
          </div>
        </CardContent>
      </Card>

      <div className="grid content-start gap-4">
        <Card>
          <CardHeader>
            <CardTitle>System status</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm">
            <StatusRow label="Camera" value={settings?.camera_name ?? '—'} />
            <div className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">Camera status</span>
              <CameraStatusBadge camera={camera} />
            </div>
            <StatusRow label="Source" value={String(settings?.camera_source ?? '—')} />
            <StatusRow label="Distance threshold" value={`${settings?.distance_threshold ?? '—'} px`} />
            <StatusRow label="Time threshold" value={`${settings?.time_threshold ?? '—'} s`} />
            <StatusRow label="Audio alerts" value={settings?.audio_alert_enabled ? 'On' : 'Off'} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Live alert feed</CardTitle>
            <CardDescription>Most recent unattended-object alerts</CardDescription>
          </CardHeader>
          <CardContent>
            {alerts.length === 0 ? (
              <p className="text-sm italic text-muted-foreground">No alerts yet — monitoring…</p>
            ) : (
              <ScrollArea className="h-72 pr-3">
                <ul className="grid gap-3">
                  {alerts.map((alert, i) => (
                    <li key={`${alert.time}-${i}`} className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm">
                      <p className="font-medium text-destructive">{alert.message}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {alert.time} · {alert.camera}
                      </p>
                    </li>
                  ))}
                </ul>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function CameraStatusBadge({ camera }: { camera: CameraStatus | null }) {
  if (!camera) return <Badge variant="outline">Checking…</Badge>
  if (camera.status === 'online') {
    return <Badge className="border-transparent bg-emerald-600 text-white">Online</Badge>
  }
  if (camera.status === 'reconnecting') {
    return <Badge className="border-transparent bg-amber-500 text-white">Reconnecting…</Badge>
  }
  return <Badge variant="destructive">Offline</Badge>
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate font-medium">{value}</span>
    </div>
  )
}
