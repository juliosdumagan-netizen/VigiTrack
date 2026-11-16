import { useEffect, useState } from 'react'
import { Download, ImageOff, Maximize2, Minimize2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { api, saveBlob, UnauthorizedError, type Incident, type ReviewAction, type ReviewStatus } from '@/lib/api'

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
  onReviewed: () => void
}

const REVIEW_LABELS: Record<ReviewStatus, string> = {
  open: 'Needs review',
  acknowledged: 'Acknowledged',
  verified: 'Verified',
  dismissed: 'False alarm',
}

export function ReviewBadge({ status }: { status: ReviewStatus }) {
  if (status === 'verified') return <Badge>{REVIEW_LABELS.verified}</Badge>
  if (status === 'acknowledged') return <Badge variant="secondary">{REVIEW_LABELS.acknowledged}</Badge>
  if (status === 'dismissed') return <Badge variant="outline">{REVIEW_LABELS.dismissed}</Badge>
  return <Badge variant="destructive">{REVIEW_LABELS.open}</Badge>
}

export function IncidentDetailSheet({ incidentId, canDelete, onClose, onDeleted, onReviewed }: Props) {
  const [incident, setIncident] = useState<Incident | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [imageFailed, setImageFailed] = useState(false)
  const [note, setNote] = useState('')
  const [reviewing, setReviewing] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [isExpanded, setIsExpanded] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [reportBusy, setReportBusy] = useState(false)

  useEffect(() => {
    if (incidentId === null) return
    let active = true
    setLoading(true)
    setError(null)
    setImageFailed(false)
    setNote('')
    setReviewError(null)
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

  async function confirmDelete() {
    if (!incident) return
    await api.deleteIncident(incident.id).catch(() => undefined)
    setDeleteOpen(false)
    onDeleted()
    onClose()
  }

  async function submitReview(action: ReviewAction) {
    if (!incident) return
    setReviewing(true)
    setReviewError(null)
    try {
      const res = await api.reviewIncident(incident.id, action, note.trim() || undefined)
      setIncident(res.incident)
      setNote('')
      onReviewed()
    } catch (err) {
      setReviewError(err instanceof Error ? err.message : 'Review failed')
    } finally {
      setReviewing(false)
    }
  }

  async function downloadReport() {
    if (!incident) return
    setReportBusy(true)
    try {
      const blob = await api.incidentReportPdf(incident.id)
      saveBlob(blob, `vigitrack-incident-${incident.id}.pdf`)
    } catch (err) {
      if (err instanceof UnauthorizedError) onClose()
      else toast.error(err instanceof Error ? err.message : 'Could not create the PDF')
    } finally {
      setReportBusy(false)
    }
  }

  const firstTime = incident?.state_history[0]?.time ? new Date(incident.state_history[0].time).getTime() : null

  return (
    <>
      <Sheet
        open={incidentId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setIsExpanded(false)
            onClose()
          }
        }}
      >
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

            <div className="group relative overflow-hidden rounded-lg border bg-muted">
              {incident?.image_url && !imageFailed ? (
                <>
                  <img
                    src={incident.image_url}
                    alt={`Snapshot for incident ${incident.id}`}
                    className="w-full cursor-pointer object-contain transition duration-150 hover:opacity-95"
                    onClick={() => setIsExpanded(true)}
                    onError={() => setImageFailed(true)}
                    title="Click to enlarge snapshot"
                  />
                  <div className="absolute top-2 right-2">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() => setIsExpanded(true)}
                      className="h-8 gap-1.5 rounded-md bg-background/85 px-2.5 text-xs font-medium shadow-xs backdrop-blur-xs transition hover:bg-background"
                      aria-label="Expand screenshot"
                    >
                      <Maximize2 className="size-3.5" />
                      <span>Expand</span>
                    </Button>
                  </div>
                </>
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

              <section className="grid gap-3 text-sm">
                <h3 className="font-medium">Review</h3>
                <div className="grid gap-1 text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <ReviewBadge status={incident.review_status} />
                    {incident.reviewed_by && (
                      <span>
                        by {incident.reviewed_by}
                        {incident.reviewed_at && ` · ${new Date(incident.reviewed_at).toLocaleString()}`}
                      </span>
                    )}
                  </div>
                  {incident.review_note && <p className="text-foreground">“{incident.review_note}”</p>}
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="review-note">Note (required to dismiss as a false alarm)</Label>
                  <Input
                    id="review-note"
                    value={note}
                    maxLength={500}
                    placeholder="e.g. student seated with bag"
                    onChange={(e) => setNote(e.target.value)}
                  />
                </div>
                {reviewError && <p className="text-destructive">{reviewError}</p>}
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" disabled={reviewing} onClick={() => submitReview('acknowledged')}>
                    Acknowledge
                  </Button>
                  <Button variant="outline" size="sm" disabled={reviewing} onClick={() => submitReview('verified')}>
                    Verify as real
                  </Button>
                  <Button variant="secondary" size="sm" disabled={reviewing} onClick={() => submitReview('dismissed')}>
                    Dismiss as false alarm
                  </Button>
                </div>
              </section>

              <Separator />

              <div className="flex flex-wrap justify-between gap-2">
                <Button variant="outline" disabled={reportBusy} onClick={downloadReport}>
                  <Download />
                  {reportBusy ? 'Preparing PDF…' : 'Download PDF report'}
                </Button>
                {canDelete && (
                  <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
                    <Trash2 />
                    Delete incident
                  </Button>
                )}
              </div>
            </>
          )}
        </div>
      </SheetContent>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={(open) => !open && setDeleteOpen(false)}
        title={`Delete incident #${incidentId}?`}
        description="The snapshot and timeline for this incident are removed permanently. This cannot be undone."
        confirmLabel="Delete"
        onConfirm={confirmDelete}
      />
    </Sheet>

    {incident?.image_url && !imageFailed && (
      <Dialog open={isExpanded} onOpenChange={setIsExpanded}>
        <DialogContent
          showCloseButton={false}
          overlayClassName="bg-black/75 backdrop-blur-sm z-[60]"
          className="z-[60] max-h-[92vh] w-full sm:max-w-4xl lg:max-w-5xl xl:max-w-6xl flex flex-col p-4 sm:p-6 gap-3"
        >
          <DialogHeader className="flex flex-row items-center justify-between gap-4 space-y-0 pb-1">
            <div>
              <DialogTitle className="text-base sm:text-lg">
                Incident #{incident.id} · Snapshot
              </DialogTitle>
              <DialogDescription className="text-xs sm:text-sm">
                {capitalize(incident.object_class)} detected at {new Date(incident.detected_at).toLocaleString()}
              </DialogDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsExpanded(false)}
              className="h-8 gap-1.5 text-xs font-medium shrink-0"
              aria-label="Minimize screenshot"
              title="Minimize screenshot (Esc)"
            >
              <Minimize2 className="size-3.5" />
              <span>Minimize</span>
            </Button>
          </DialogHeader>

          <div className="relative flex flex-1 items-center justify-center overflow-hidden rounded-lg bg-black/95 p-1 sm:p-2 border">
            <img
              src={incident.image_url}
              alt={`Enlarged snapshot for incident ${incident.id}`}
              className="max-h-[70vh] w-auto max-w-full rounded object-contain select-none shadow-md"
            />
          </div>

          <DialogFooter className="flex flex-row items-center justify-between gap-3 pt-1">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="destructive" className="capitalize">{incident.status}</Badge>
              <span>Camera: {incident.camera_name ?? '—'}</span>
              {incident.distance != null && <span>· Distance: {incident.distance.toFixed(0)} px</span>}
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    )}
  </>
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
