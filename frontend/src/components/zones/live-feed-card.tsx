import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Pencil, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { ZoneOverlay } from '@/components/zones/zone-overlay'
import { api, UnauthorizedError, type Zone, type ZoneKind, type ZonePoint } from '@/lib/api'
import { useAuth } from '@/lib/auth'

const MIN_CORNERS = 3
const MAX_WATCH_SECONDS = 3600

/** The live camera feed, with zones drawn on it. Administrators can edit the zones here. */
export function LiveFeedCard({ cameraName, className }: { cameraName: string; className?: string }) {
  const navigate = useNavigate()
  const { isAdmin } = useAuth()
  const [zones, setZones] = useState<Zone[]>([])
  const [aspect, setAspect] = useState<number>(16 / 9)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<Zone[]>([])
  const [shape, setShape] = useState<ZonePoint[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api
      .getZones()
      .then((res) => active && setZones(res.zones))
      .catch((err) => {
        if (err instanceof UnauthorizedError) navigate('/login', { replace: true })
      })
    return () => {
      active = false
    }
  }, [navigate])

  function startEditing() {
    setDraft(zones.map((z) => ({ ...z, points: z.points.map((p) => [...p] as ZonePoint) })))
    setShape([])
    setError(null)
    setEditing(true)
  }

  function cancelEditing() {
    setEditing(false)
    setDraft([])
    setShape([])
    setError(null)
  }

  function finishShape() {
    if (shape.length < MIN_CORNERS) return
    setDraft((d) => [
      ...d,
      { id: `zone-${Date.now()}`, name: `Zone ${d.length + 1}`, type: 'ignore', points: shape },
    ])
    setShape([])
  }

  function updateZone(id: string, changes: Partial<Zone>) {
    setDraft((d) => d.map((z) => (z.id === id ? { ...z, ...changes } : z)))
  }

  function setKind(zone: Zone, kind: ZoneKind) {
    updateZone(zone.id, { type: kind, time_threshold: kind === 'watch' ? (zone.time_threshold ?? 5) : undefined })
  }

  async function save() {
    setSaving(true)
    setError(null)
    try {
      const res = await api.saveZones(draft)
      setZones(res.zones)
      setEditing(false)
      setDraft([])
      setShape([])
      toast.success(res.zones.length === 0 ? 'All zones removed.' : `${res.zones.length} zone(s) saved.`)
    } catch (err) {
      if (err instanceof UnauthorizedError) navigate('/login', { replace: true })
      else setError(err instanceof Error ? err.message : 'Could not save the zones')
    } finally {
      setSaving(false)
    }
  }

  const shownZones = editing ? draft : zones

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>{cameraName}</CardTitle>
        <CardDescription>
          {editing ? 'Draw zones on the feed, then save' : 'Live feed with person and object detection'}
        </CardDescription>
        <CardAction className="flex items-center gap-2">
          {isAdmin && !editing && (
            <Button variant="outline" size="sm" onClick={startEditing}>
              <Pencil />
              Edit zones
            </Button>
          )}
          <Badge variant="destructive">● Live</Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="relative overflow-hidden rounded-lg bg-black" style={{ aspectRatio: aspect }}>
          <img
            src="/video_feed"
            alt="Live surveillance feed"
            className="size-full object-contain"
            onLoad={(e) => {
              const { naturalWidth, naturalHeight } = e.currentTarget
              if (naturalWidth > 0 && naturalHeight > 0) setAspect(naturalWidth / naturalHeight)
            }}
          />
          <ZoneOverlay
            zones={shownZones}
            shape={editing ? shape : []}
            editing={editing}
            onAddPoint={(p) => setShape((s) => [...s, p])}
          />
        </div>

        {!editing && zones.length > 0 && (
          <div className="flex flex-wrap gap-2 text-xs">
            {zones.map((z) => (
              <Badge key={z.id} variant="outline">
                {z.name} · {z.type === 'ignore' ? 'ignored' : `watch ${z.time_threshold}s`}
              </Badge>
            ))}
          </div>
        )}

        {editing && (
          <div className="grid gap-4">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted-foreground">
                {shape.length === 0
                  ? 'Click the feed to add corners.'
                  : `${shape.length} corner(s) placed.`}
              </span>
              <Button variant="outline" size="sm" disabled={shape.length === 0} onClick={() => setShape((s) => s.slice(0, -1))}>
                Undo corner
              </Button>
              <Button variant="outline" size="sm" disabled={shape.length < MIN_CORNERS} onClick={finishShape}>
                Finish shape
              </Button>
              <Button variant="ghost" size="sm" disabled={shape.length === 0} onClick={() => setShape([])}>
                Discard shape
              </Button>
            </div>

            <Separator />

            {draft.length === 0 ? (
              <p className="text-sm text-muted-foreground">No zones yet. Draw one above.</p>
            ) : (
              <ul className="grid gap-3">
                {draft.map((zone) => (
                  <li key={zone.id} className="grid gap-3 rounded-md border p-3 text-sm sm:grid-cols-[1fr_auto_auto_auto] sm:items-end">
                    <div className="grid gap-1.5">
                      <Label htmlFor={`zone-name-${zone.id}`}>Name</Label>
                      <Input
                        id={`zone-name-${zone.id}`}
                        value={zone.name}
                        maxLength={40}
                        onChange={(e) => updateZone(zone.id, { name: e.target.value })}
                      />
                    </div>
                    <div className="grid gap-1.5">
                      <Label>Type</Label>
                      <div className="flex gap-1">
                        <Button
                          variant={zone.type === 'ignore' ? 'default' : 'outline'}
                          size="sm"
                          aria-pressed={zone.type === 'ignore'}
                          onClick={() => setKind(zone, 'ignore')}
                        >
                          Ignore
                        </Button>
                        <Button
                          variant={zone.type === 'watch' ? 'default' : 'outline'}
                          size="sm"
                          aria-pressed={zone.type === 'watch'}
                          onClick={() => setKind(zone, 'watch')}
                        >
                          Watch
                        </Button>
                      </div>
                    </div>
                    {zone.type === 'watch' ? (
                      <div className="grid gap-1.5">
                        <Label htmlFor={`zone-seconds-${zone.id}`}>Alert after (s)</Label>
                        <Input
                          id={`zone-seconds-${zone.id}`}
                          type="number"
                          min={1}
                          max={MAX_WATCH_SECONDS}
                          step={1}
                          className="w-24"
                          value={zone.time_threshold ?? ''}
                          onChange={(e) => {
                            const raw = e.target.value
                            updateZone(zone.id, { time_threshold: raw === '' ? undefined : Number(raw) })
                          }}
                        />
                      </div>
                    ) : (
                      <span />
                    )}
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`Delete ${zone.name}`}
                      onClick={() => setDraft((d) => d.filter((z) => z.id !== zone.id))}
                    >
                      <Trash2 />
                    </Button>
                  </li>
                ))}
              </ul>
            )}

            {error && <p className="text-sm text-destructive">{error}</p>}

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={cancelEditing} disabled={saving}>
                Cancel
              </Button>
              <Button onClick={save} disabled={saving}>
                {saving ? 'Saving…' : 'Save zones'}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
