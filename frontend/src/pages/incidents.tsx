import { useCallback, useEffect, useState, type KeyboardEvent, type MouseEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardAction } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { IncidentDetailSheet } from '@/components/incidents/incident-detail-sheet'
import { api, UnauthorizedError, type Incident } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export function IncidentsPage() {
  const navigate = useNavigate()
  const { isAdmin } = useAuth()
  const [params, setParams] = useSearchParams()
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
    if (!confirm(`Delete incident #${id}?`)) return
    await api.deleteIncident(id).catch(() => undefined)
    load()
  }

  async function handleClear() {
    if (!confirm('Delete ALL incident records?')) return
    await api.clearIncidents().catch(() => undefined)
    load()
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
            {isAdmin && (
              <Button variant="destructive" size="sm" onClick={handleClear} disabled={incidents.length === 0}>
                Clear all
              </Button>
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
                <TableHead>Detected at</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {incidents.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="text-center text-muted-foreground">
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
                  <TableCell className="capitalize">{row.object_class}</TableCell>
                  <TableCell>{row.object_track_id ?? '—'}</TableCell>
                  <TableCell>{row.person_track_id ?? '—'}</TableCell>
                  <TableCell>{row.distance != null ? `${row.distance.toFixed(0)} px` : '—'}</TableCell>
                  <TableCell>{row.camera_name ?? '—'}</TableCell>
                  <TableCell>
                    <Badge variant="destructive" className="capitalize">{row.status}</Badge>
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

      <IncidentDetailSheet incidentId={selectedId} canDelete={isAdmin} onClose={closeIncident} onDeleted={load} />
    </>
  )
}
