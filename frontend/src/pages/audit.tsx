import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download, RefreshCw, ShieldCheck, ShieldAlert } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardAction } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { DatePicker } from '@/components/ui/date-picker'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  api,
  saveBlob,
  UnauthorizedError,
  type AuditEntry,
  type AuditQuery,
  type AuditVerification,
} from '@/lib/api'

const PAGE_SIZE = 50

export function AuditPage() {
  const navigate = useNavigate()
  const [actor, setActor] = useState('')
  const [action, setAction] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [page, setPage] = useState(0)
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actions, setActions] = useState<string[]>([])
  const [integrity, setIntegrity] = useState<AuditVerification | null>(null)
  const [checking, setChecking] = useState(false)
  const [exporting, setExporting] = useState(false)

  const filters: AuditQuery = {
    actor: actor.trim() || undefined,
    action: action || undefined,
    start: start || undefined,
    end: end || undefined,
  }

  useEffect(() => {
    api
      .auditActions()
      .then(setActions)
      .catch((err) => err instanceof UnauthorizedError && navigate('/login', { replace: true }))
  }, [navigate])

  useEffect(() => {
    let active = true
    const timer = setTimeout(() => {
      const query: AuditQuery = {
        actor: actor.trim() || undefined,
        action: action || undefined,
        start: start || undefined,
        end: end || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }
      setLoading(true)
      api
        .searchAudit(query)
        .then((res) => {
          if (!active) return
          setEntries(res.entries)
          setTotal(res.total)
          setError(null)
        })
        .catch((err) => {
          if (!active) return
          if (err instanceof UnauthorizedError) navigate('/login', { replace: true })
          else setError(err instanceof Error ? err.message : 'Could not load the audit trail')
        })
        .finally(() => active && setLoading(false))
    }, 250)
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [actor, action, start, end, page, navigate])

  const verify = useCallback(() => {
    setChecking(true)
    api
      .verifyAudit()
      .then(setIntegrity)
      .catch((err) => err instanceof UnauthorizedError && navigate('/login', { replace: true }))
      .finally(() => setChecking(false))
  }, [navigate])

  useEffect(() => {
    api
      .verifyAudit()
      .then(setIntegrity)
      .catch((err) => err instanceof UnauthorizedError && navigate('/login', { replace: true }))
  }, [navigate])

  function changeFilter(setter: (value: string) => void, value: string) {
    setter(value)
    setPage(0)
  }

  async function handleExport() {
    setExporting(true)
    try {
      const blob = await api.exportAuditCsv(filters)
      saveBlob(blob, `vigitrack-audit-${new Date().toISOString().slice(0, 10)}.csv`)
    } catch (err) {
      if (err instanceof UnauthorizedError) navigate('/login', { replace: true })
      else toast.error(err instanceof Error ? err.message : 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  const from = total === 0 ? 0 : page * PAGE_SIZE + 1
  const to = Math.min(total, (page + 1) * PAGE_SIZE)
  const lastPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1)

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Log integrity</CardTitle>
          <CardDescription>Each entry is linked to the one before it, so a change or deletion shows up here</CardDescription>
          <CardAction>
            <Button variant="outline" size="sm" onClick={verify} disabled={checking}>
              <RefreshCw />
              {checking ? 'Checking…' : 'Check again'}
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          {integrity === null ? (
            <p className="text-sm text-muted-foreground">Checking the log…</p>
          ) : integrity.ok ? (
            <p className="flex items-center gap-2 text-sm text-emerald-700">
              <ShieldCheck className="size-4" />
              The log is intact.
              {integrity.unhashed_entries > 0 && (
                <span className="text-muted-foreground">
                  {' '}({integrity.unhashed_entries} entries from before linking was added are not checked.)
                </span>
              )}
            </p>
          ) : (
            <p className="flex items-center gap-2 text-sm text-destructive">
              <ShieldAlert className="size-4" />
              Entry #{integrity.first_bad_id} does not match the entries around it. The log may have been changed or
              an entry removed.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Audit trail</CardTitle>
          <CardDescription>Who did what, and when. Camera passwords are never recorded.</CardDescription>
          <CardAction>
            <Button variant="outline" size="sm" onClick={handleExport} disabled={exporting || total === 0}>
              <Download />
              {exporting ? 'Exporting…' : 'Export CSV'}
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="grid gap-1.5">
              <Label htmlFor="audit-actor">User</Label>
              <Input id="audit-actor" value={actor} placeholder="Any user" onChange={(e) => changeFilter(setActor, e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="audit-action">Action</Label>
              <Select
                value={action || "__all__"}
                onValueChange={(value) => changeFilter(setAction, value === "__all__" ? "" : value)}
              >
                <SelectTrigger id="audit-action" className="w-full" aria-label="Action">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent position="popper" align="start">
                  <SelectItem value="__all__">All actions</SelectItem>
                  {actions.map((name) => (
                    <SelectItem key={name} value={name}>
                      {name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="audit-start">From</Label>
              <DatePicker
                id="audit-start"
                aria-label="From date"
                value={start}
                onChange={(value) => changeFilter(setStart, value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="audit-end">To</Label>
              <DatePicker
                id="audit-end"
                aria-label="To date"
                value={end}
                onChange={(value) => changeFilter(setEnd, value)}
              />
            </div>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Recorded at</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Detail</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    {loading ? 'Loading…' : 'No entries match these filters.'}
                  </TableCell>
                </TableRow>
              )}
              {entries.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell className="whitespace-nowrap">{new Date(entry.created_at).toLocaleString()}</TableCell>
                  <TableCell>{entry.actor ?? 'System'}</TableCell>
                  <TableCell className="font-mono text-xs">{entry.action}</TableCell>
                  <TableCell className="max-w-md whitespace-normal break-words text-sm">{entry.detail ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
            <span>
              {from}–{to} of {total}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>
                Newer
              </Button>
              <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.min(lastPage, p + 1))} disabled={page >= lastPage}>
                Older
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
