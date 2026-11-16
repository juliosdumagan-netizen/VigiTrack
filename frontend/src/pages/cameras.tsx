import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api, UnauthorizedError, type CameraStatus, type Settings } from '@/lib/api'
import { useAuth } from '@/lib/auth'

const CAMERA_BADGE: Record<CameraStatus['status'], { label: string; dot: string }> = {
  online: { label: 'Online', dot: 'bg-emerald-500' },
  reconnecting: { label: 'Reconnecting…', dot: 'bg-amber-500' },
  offline: { label: 'Offline', dot: 'bg-destructive' },
}

export function CamerasPage() {
  const navigate = useNavigate()
  const { isAdmin } = useAuth()
  const [settings, setSettings] = useState<Settings | null>(null)
  const [camera, setCamera] = useState<CameraStatus | null>(null)
  const [source, setSource] = useState('')
  const [name, setName] = useState('')
  const [message, setMessage] = useState<{ type: 'ok' | 'error'; text: string } | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    api
      .getSettings()
      .then((s) => {
        if (!active) return
        setSettings(s)
        setSource(String(s.camera_source))
        setName(s.camera_name)
      })
      .catch((err) => {
        if (!active) return
        if (err instanceof UnauthorizedError) navigate('/login', { replace: true })
        else setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to load' })
      })

    const pollStatus = () =>
      api
        .getCameraStatus()
        .then((c) => active && setCamera(c))
        .catch((err) => {
          if (err instanceof UnauthorizedError) navigate('/login', { replace: true })
        })

    void pollStatus()
    const timer = setInterval(pollStatus, 3000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [navigate])

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setMessage(null)
    const value = source.trim()
    if (!value) {
      setMessage({ type: 'error', text: 'Enter a camera index or RTSP URL.' })
      return
    }
    setSaving(true)
    try {
      const payload = {
        camera_source: /^\d+$/.test(value) ? Number(value) : value,
        camera_name: name.trim() || 'CAMERA',
      }
      const res = await api.updateSettings(payload)
      setSettings(res.settings as Settings)
      setCamera(await api.getCameraStatus().catch(() => null))
      setMessage({ type: 'ok', text: 'Camera source switched.' })
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Switch failed' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Connected cameras</CardTitle>
          <CardDescription>Cameras currently available to VigiTrack</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {settings && (
                <TableRow>
                  <TableCell className="font-medium">{settings.camera_name}</TableCell>
                  <TableCell className="font-mono text-xs">{String(settings.camera_source)}</TableCell>
                  <TableCell>
                    {camera ? (
                      <Badge variant="outline" className="gap-1.5">
                        <span className={`size-2 rounded-full ${CAMERA_BADGE[camera.status].dot}`} />
                        {CAMERA_BADGE[camera.status].label}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="gap-1.5">
                        <span className="size-2 rounded-full bg-muted-foreground" />
                        Checking…
                      </Badge>
                    )}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          <p className="mt-3 text-xs text-muted-foreground">
            The backend currently runs one camera at a time. Multi-camera support is the next step.
          </p>
        </CardContent>
      </Card>

      {isAdmin && (
      <Card>
        <CardHeader>
          <CardTitle>Switch source</CardTitle>
          <CardDescription>Use a camera index (0, 1, …) or an RTSP URL</CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit} className="grid gap-6">
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="camera-source">Source</Label>
              <Input
                id="camera-source"
                placeholder="0 or rtsp://user:pass@host:554/..."
                value={source}
                onChange={(e) => setSource(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="camera-name">Display name</Label>
              <Input id="camera-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            {message && (
              <p className={message.type === 'ok' ? 'text-sm text-emerald-600' : 'text-sm text-destructive'}>
                {message.text}
              </p>
            )}
          </CardContent>
          <CardFooter>
            <Button type="submit" className="w-full" disabled={saving}>
              {saving ? 'Switching…' : 'Switch camera'}
            </Button>
          </CardFooter>
        </form>
      </Card>
      )}
    </div>
  )
}
