import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { KeyRound, Lock, Trash2, Unlock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api, type AuditEntry, type Role, type User } from '@/lib/api'
import { useAuth } from '@/lib/auth'

type Notice = { type: 'ok' | 'error'; text: string }

export function UsersPage() {
  const { user: me } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const [notice, setNotice] = useState<Notice | null>(null)

  const [newName, setNewName] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState<Role>('operator')
  const [creating, setCreating] = useState(false)

  const [resetTarget, setResetTarget] = useState<User | null>(null)
  const [resetPassword, setResetPassword] = useState('')

  const load = useCallback(() => {
    api.listUsers().then(setUsers).catch((err) => setNotice({ type: 'error', text: err.message }))
    api.getAudit().then(setAudit).catch(() => undefined)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function run(action: () => Promise<unknown>, success: string) {
    setNotice(null)
    try {
      await action()
      setNotice({ type: 'ok', text: success })
      load()
    } catch (err) {
      setNotice({ type: 'error', text: err instanceof Error ? err.message : 'Action failed' })
    }
  }

  async function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setCreating(true)
    try {
      await api.createUser(newName.trim(), newPassword, newRole)
      setNewName('')
      setNewPassword('')
      setNewRole('operator')
      setNotice({ type: 'ok', text: 'Account created.' })
      load()
    } catch (err) {
      setNotice({ type: 'error', text: err instanceof Error ? err.message : 'Could not create account' })
    } finally {
      setCreating(false)
    }
  }

  async function handleReset(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!resetTarget) return
    const target = resetTarget
    setResetTarget(null)
    await run(() => api.updateUser(target.id, { new_password: resetPassword }), `Password reset for ${target.username}.`)
    setResetPassword('')
  }

  function handleDelete(target: User) {
    if (!confirm(`Delete account "${target.username}"? This cannot be undone.`)) return
    run(() => api.deleteUser(target.id), `Deleted ${target.username}.`)
  }

  return (
    <div className="grid gap-4">
      {notice && (
        <p className={notice.type === 'ok' ? 'text-sm text-emerald-600' : 'text-sm text-destructive'}>{notice.text}</p>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Accounts</CardTitle>
            <CardDescription>Administrators can manage every account. Operators can view and acknowledge.</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Username</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last login</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => {
                  const isSelf = u.id === me?.id
                  return (
                    <TableRow key={u.id}>
                      <TableCell className="font-medium">
                        {u.username}
                        {isSelf && <span className="ml-2 text-xs text-muted-foreground">(you)</span>}
                      </TableCell>
                      <TableCell>
                        <Select
                          value={u.role}
                          disabled={isSelf}
                          onValueChange={(value) =>
                            run(() => api.updateUser(u.id, { role: value as Role }), `Role updated for ${u.username}.`)
                          }
                        >
                          <SelectTrigger className="w-36" aria-label={`Role for ${u.username}`}>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="operator">Operator</SelectItem>
                            <SelectItem value="admin">Admin</SelectItem>
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {u.is_active ? (
                            <Badge variant="outline">Active</Badge>
                          ) : (
                            <Badge variant="secondary">Disabled</Badge>
                          )}
                          {u.is_locked && (
                            <Badge variant="destructive" className="gap-1">
                              <Lock className="size-3" /> Locked
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'Never'}
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-1">
                          {u.is_locked && (
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label={`Unlock ${u.username}`}
                              title="Unlock"
                              onClick={() => run(() => api.updateUser(u.id, { unlock: true }), `Unlocked ${u.username}.`)}
                            >
                              <Unlock />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label={`Reset password for ${u.username}`}
                            title="Reset password"
                            onClick={() => setResetTarget(u)}
                          >
                            <KeyRound />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={isSelf}
                            onClick={() =>
                              run(
                                () => api.updateUser(u.id, { is_active: !u.is_active }),
                                `${u.is_active ? 'Disabled' : 'Enabled'} ${u.username}.`,
                              )
                            }
                          >
                            {u.is_active ? 'Disable' : 'Enable'}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label={`Delete ${u.username}`}
                            title="Delete"
                            disabled={isSelf}
                            onClick={() => handleDelete(u)}
                          >
                            <Trash2 />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Create account</CardTitle>
            <CardDescription>Share the password with the user in person.</CardDescription>
          </CardHeader>
          <form onSubmit={handleCreate} className="grid gap-6">
            <CardContent className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="new-name">Username</Label>
                <Input id="new-name" value={newName} onChange={(e) => setNewName(e.target.value)} required />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="new-pass">Temporary password</Label>
                <Input id="new-pass" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="new-role">Role</Label>
                <Select value={newRole} onValueChange={(value) => setNewRole(value as Role)}>
                  <SelectTrigger id="new-role" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="operator">Operator: view and monitor</SelectItem>
                    <SelectItem value="admin">Admin: full access</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
            <CardFooter>
              <Button type="submit" disabled={creating}>{creating ? 'Creating…' : 'Create account'}</Button>
            </CardFooter>
          </form>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Activity log</CardTitle>
          <CardDescription>Logins, account changes and settings updates, newest first</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Detail</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {audit.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">No activity yet.</TableCell>
                </TableRow>
              )}
              {audit.slice(0, 100).map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell className="whitespace-nowrap">{new Date(entry.created_at).toLocaleString()}</TableCell>
                  <TableCell>{entry.actor ?? '—'}</TableCell>
                  <TableCell className="font-mono text-xs">{entry.action}</TableCell>
                  <TableCell className="text-muted-foreground">{entry.detail ?? ''}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={resetTarget !== null} onOpenChange={(open) => !open && setResetTarget(null)}>
        <DialogContent>
          <form onSubmit={handleReset} className="grid gap-4">
            <DialogHeader>
              <DialogTitle>Reset password</DialogTitle>
              <DialogDescription>
                Set a new password for {resetTarget?.username}. This also clears any lockout.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-2">
              <Label htmlFor="reset-pass">New password</Label>
              <Input id="reset-pass" type="password" value={resetPassword} onChange={(e) => setResetPassword(e.target.value)} required />
            </div>
            <DialogFooter>
              <Button type="submit">Reset password</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
