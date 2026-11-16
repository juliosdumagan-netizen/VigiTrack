import { useCallback, useEffect, useState, type KeyboardEvent, type MouseEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CalendarX2, Download, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardAction } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { DatePicker } from '@/components/ui/date-picker'
import { Label } from '@/components/ui/label'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import { IncidentDetailSheet, ReviewBadge } from '@/components/incidents/incident-detail-sheet'
import { mixedBagLabels } from '@/lib/incident-evidence'
import { api, saveBlob, UnauthorizedError, type Incident } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export function IncidentsPage() {
  const navigate = useNavigate()
  const { isAdmin } = useAuth()
  const [params, setParams] = useSearchParams()
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [purgeOpen, setPurgeOpen] = useState(false)
  const [purgeStart, setPurgeStart] = useState('')
  const [purgeEnd, setPurgeEnd] = useState('')
  const [purgeError, setPurgeError] = useState<string | null>(null)
  const [purging, setPurging] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
  const [clearOpen, setClearOpen] = useState(false)
  const [exporting, setExporting] = useState(false)

  const selectedParam = params.get('selected')
  const selectedId = selectedParam && /^\d+$/.test(selectedParam) ? Number(selectedParam) : null

  const load = useCallback(() => {
    setLoading(true)
    api
      .getIncidents()
      .then((rows) => {
        setIncidents(rows)
        setError(null)
      })
      .catch((err) => {
        if (err instanceof UnauthorizedError) navigate('/login', { replace: true })
        else setError(err instanceof Error ? err.message : 'Failed to load incidents')
      })
      .finally(() => setLoading(false))
  }, [navigate])

  useEffect(() => {
    load()
  }, [load])

  function openIncident(id: number) {
    setParams({ selected: String(id) })
  }

  function closeIncident() {
    setParams({})
  }

  async function handleDelete(e: MouseEvent, id: number) {
    e.stopPropagation()
    setDeleteTarget(id)
  }

  async function confirmDelete() {
    if (deleteTarget === null) return
    try {
      await api.deleteIncident(deleteTarget)
      setDeleteTarget(null)
      load()
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        setDeleteTarget(null)
        navigate('/login', { replace: true })
      } else {
        toast.error(err instanceof Error ? err.message : 'Failed to delete incident')
        throw err
      }
    }
  }

  async function confirmClear() {
    try {
      await api.clearIncidents()
      setClearOpen(false)
      load()
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        setClearOpen(false)
        navigate('/login', { replace: true })
      } else {
        toast.error(err instanceof Error ? err.message : 'Failed to clear incidents')
        throw err
      }
    }
  }

  async function handleExport() {
    setExporting(true)
    try {
      const blob = await api.exportIncidentsCsv()
      saveBlob(blob, `vigitrack-incidents-${new Date().toISOString().slice(0, 10)}.csv`)
    } catch (err) {
      if (err instanceof UnauthorizedError) navigate('/login', { replace: true })
      else toast.error(err instanceof Error ? err.message : 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  function openPurge() {
    setPurgeStart('')
    setPurgeEnd('')
    setPurgeError(null)
    setPurgeOpen(true)
  }

  async function handlePurge() {
    if (!purgeStart || !purgeEnd) {
      setPurgeError('Choose both dates.')
      return
    }
    if (purgeEnd < purgeStart) {
      setPurgeError('The end date is before the start date.')
      return
    }
    setPurgeError(null)
    setPurging(true)
    try {
      const res = await api.purgeIncidents(purgeStart, purgeEnd)
      setPurgeOpen(false)
      toast.success(`${res.deleted} incident(s) deleted.`)
      load()
    } catch (err) {
      setPurgeError(err instanceof Error ? err.message : 'Delete failed')
    } finally {
      setPurging(false)
    }
  }

  function handleRowKey(e: KeyboardEvent, id: number) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      openIncident(id)
    }
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Incident history</CardTitle>
          <CardDescription>Select an incident to see its snapshot and timeline</CardDescription>
          <CardAction className="flex gap-2">
            <Button variant="outline" size="sm" onClick={load} disabled={loading}>
              Refresh
            </Button>
            <Button variant="outline" size="sm" onClick={handleExport} disabled={exporting || incidents.length === 0}>
              <Download />
              {exporting ? 'Exporting…' : 'Export CSV'}
            </Button>
            {isAdmin && (
              <>
                <Button variant="outline" size="sm" onClick={openPurge} disabled={incidents.length === 0}>
                  <CalendarX2 />
                  Delete by date…
                </Button>
                <Button variant="destructive" size="sm" onClick={() => setClearOpen(true)} disabled={incidents.length === 0}>
                  Clear all
                </Button>
              </>
            )}
          </CardAction>
        </CardHeader>
        <CardContent>
          {error && <p className="mb-4 text-sm text-destructive">{error}</p>}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Object</TableHead>
                <TableHead>Object #</TableHead>
                <TableHead>Person #</TableHead>
                <TableHead>Distance</TableHead>
                <TableHead>Camera</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Review</TableHead>
                <TableHead>Detected at</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {incidents.length === 0 && (
                <TableRow>
                  <TableCell colSpan={10} className="text-center text-muted-foreground">
                    {loading ? 'Loading…' : 'No incidents recorded.'}
                  </TableCell>
                </TableRow>
              )}
              {incidents.map((row) => (
                <TableRow
                  key={row.id}
                  className="cursor-pointer"
                  tabIndex={0}
                  onClick={() => openIncident(row.id)}
                  onKeyDown={(e) => handleRowKey(e, row.id)}
                  aria-label={`Open incident ${row.id}`}
                >
                  <TableCell>{row.id}</TableCell>
                  <TableCell className="capitalize">
                    {row.object_class}
                    {row.class_evidence && mixedBagLabels(row.class_evidence) && (
                      <span className="block text-xs normal-case text-muted-foreground">mixed bag labels</span>
                    )}
                  </TableCell>
                  <TableCell>{row.object_track_id ?? '—'}</TableCell>
                  <TableCell>{row.person_track_id ?? '—'}</TableCell>
                  <TableCell>{row.distance != null ? `${row.distance.toFixed(0)} px` : '—'}</TableCell>
                  <TableCell>{row.camera_name ?? '—'}</TableCell>
                  <TableCell>
                    <Badge variant="destructive" className="capitalize">{row.status}</Badge>
                  </TableCell>
                  <TableCell>
                    <ReviewBadge status={row.review_status} />
                  </TableCell>
                  <TableCell>{new Date(row.detected_at).toLocaleString()}</TableCell>
                  <TableCell>
                    {isAdmin && (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`Delete incident ${row.id}`}
                        onClick={(e) => handleDelete(e, row.id)}
                      >
                        <Trash2 />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={purgeOpen} onOpenChange={setPurgeOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete incidents by date</DialogTitle>
            <DialogDescription>
              Deletes every incident detected from the start date to the end date (inclusive), with their snapshots.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid gap-2">
              <Label htmlFor="purge-start">From (inclusive)</Label>
              <DatePicker
                id="purge-start"
                aria-label="From date"
                value={purgeStart}
                onChange={setPurgeStart}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="purge-end">To (inclusive)</Label>
              <DatePicker
                id="purge-end"
                aria-label="To date"
                value={purgeEnd}
                onChange={setPurgeEnd}
              />
            </div>
            {purgeError && <p className="text-sm text-destructive">{purgeError}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPurgeOpen(false)} disabled={purging}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handlePurge} disabled={purging}>
              {purging ? 'Deleting…' : 'Delete range'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title={`Delete incident #${deleteTarget}?`}
        description="The snapshot and timeline for this incident are removed permanently. This cannot be undone."
        confirmLabel="Delete"
        onConfirm={confirmDelete}
      />

      <ConfirmDialog
        open={clearOpen}
        onOpenChange={setClearOpen}
        title="Delete ALL incident records?"
        description="Every incident, snapshot, and timeline in the history is removed permanently. This cannot be undone."
        confirmLabel="Delete all"
        onConfirm={confirmClear}
      />

      <IncidentDetailSheet
        incidentId={selectedId}
        canDelete={isAdmin}
        onClose={closeIncident}
        onDeleted={load}
        onReviewed={load}
      />
    </>
  )
}
