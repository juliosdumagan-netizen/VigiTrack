import { useEffect, useState } from 'react'
import { ImageOff, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { api, type Incident } from '@/lib/api'

const STATE_LABELS: Record<string, string> = {
  UNASSIGNED: 'Unassigned',
  CARRIED: 'Carried',
  STATIC_ATTENDED: 'Attended (stationary)',
  SEPARATED: 'Person separated',
  OWNER_OUT_OF_VIEW: 'Person out of view',
  UNATTENDED_ALERT: 'Unattended alert',
}

type Props = {
  incidentId: number | null
  canDelete: boolean
  onClose: () => void
  onDeleted: () => void
}

export function IncidentDetailSheet({ incidentId, canDelete, onClose, onDeleted }: Props) {
  const [incident, setIncident] = useState<Incident | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [imageFailed, setImageFailed] = useState(false)

  useEffect(() => {
    if (incidentId === null) return
    let active = true
    setLoading(true)
    setError(null)
    setImageFailed(false)
    setIncident(null)
    api
      .getIncident(incidentId)
      .then((data) => active && setIncident(data))
      .catch((err) => active && setError(err instanceof Error ? err.message : 'Failed to load incident'))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [incidentId])

  async function handleDelete() {
    if (!incident) return
    if (!confirm(`Delete incident #${incident.id}?`)) return
    await api.deleteIncident(incident.id).catch(() => undefined)
    onDeleted()
    onClose()
  }

  const firstTime = incident?.state_history[0]?.time ? new Date(incident.state_history[0].time).getTime() : null

  return (
    <Sheet open={incidentId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>Incident #{incidentId}</SheetTitle>
          <SheetDescription>
            {incident
              ? `${capitalize(incident.object_class)} · ${new Date(incident.detected_at).toLocaleString()}`
              : 'Loading incident details…'}
          </SheetDescription>
        </SheetHeader>

        <div className="grid gap-6 px-4 pb-6">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="overflow-hidden rounded-lg border bg-muted">
            {incident?.image_url && !imageFailed ? (
              <img
                src={incident.image_url}
                alt={`Snapshot for incident ${incident.id}`}
                className="w-full object-contain"
                onError={() => setImageFailed(true)}
              />
            ) : (
              <div className="flex aspect-video flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
                <ImageOff className="size-6" />
                {loading ? 'Loading snapshot…' : 'No snapshot recorded for this incident'}
              </div>
            )}
          </div>

          {incident && (
            <>
              <section className="grid gap-2 text-sm">
                <h3 className="font-medium">Details</h3>
                <DetailRow label="Status">
                  <Badge variant="destructive" className="capitalize">{incident.status}</Badge>
                </DetailRow>
                <DetailRow label="Object">{capitalize(incident.object_class)} #{incident.object_track_id ?? '—'}</DetailRow>
                <DetailRow label="Associated person">{incident.person_track_id != null ? `Person #${incident.person_track_id}` : 'None'}</DetailRow>
                <DetailRow label="Distance at alert">
                  {incident.distance != null ? `${incident.distance.toFixed(0)} px` : '—'}
                  {incident.distance_threshold != null && (
                    <span className="text-muted-foreground"> (threshold {incident.distance_threshold} px)</span>
                  )}
                </DetailRow>
                <DetailRow label="Time limit">
                  {incident.time_threshold != null ? `${incident.time_threshold} s` : '—'}
                </DetailRow>
                <DetailRow label="Camera">{incident.camera_name ?? '—'}</DetailRow>
              </section>

              <Separator />

              <section className="grid gap-2">
                <h3 className="text-sm font-medium">What happened</h3>
                {incident.state_history.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No state history recorded for this incident.</p>
                ) : (
                  <ScrollArea className="max-h-64 pr-3">
                    <ol className="grid gap-3 text-sm">
                      {incident.state_history.map((entry, i) => {
                        const offset =
                          firstTime != null ? (new Date(entry.time).getTime() - firstTime) / 1000 : null
                        return (
                          <li key={`${entry.time}-${i}`} className="flex gap-3">
                            <span className="mt-1.5 size-2 shrink-0 rounded-full bg-primary" />
                            <div className="grid">
                              <span className="font-medium">{STATE_LABELS[entry.state] ?? entry.state}</span>
                              <span className="text-xs text-muted-foreground">
                                {new Date(entry.time).toLocaleTimeString()}
                                {offset != null && ` · +${offset.toFixed(1)} s`}
                              </span>
                            </div>
                          </li>
                        )
                      })}
                    </ol>
                  </ScrollArea>
                )}
              </section>

              <Separator />

              {canDelete && (
                <div className="flex justify-end">
                  <Button variant="destructive" onClick={handleDelete}>
                    <Trash2 />
                    Delete incident
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{children}</span>
    </div>
  )
}

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1)
}
