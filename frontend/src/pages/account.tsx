import { useState, type FormEvent } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export function AccountPage() {
  const { user, refresh } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [message, setMessage] = useState<{ type: 'ok' | 'error'; text: string } | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setMessage(null)
    if (next !== confirm) {
      setMessage({ type: 'error', text: 'The new passwords do not match.' })
      return
    }
    setSaving(true)
    try {
      await api.changeOwnPassword(current, next)
      setCurrent('')
      setNext('')
      setConfirm('')
      setMessage({ type: 'ok', text: 'Password changed.' })
      await refresh()
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Could not change password' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid max-w-xl gap-4">
      {user?.must_change_password && (
        <p className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
          Your password is temporary. Choose a new password to continue to the hub.
        </p>
      )}
      <Card>
        <CardHeader>
          <CardTitle>Your account</CardTitle>
          <CardDescription>Accounts are created by an administrator.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Username</span>
            <span className="font-medium">{user?.username}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Role</span>
            <Badge variant="outline" className="capitalize">{user?.role}</Badge>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
          <CardDescription>Use at least 8 characters.</CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit} className="grid gap-6">
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="current">Current password</Label>
              <Input id="current" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="next">New password</Label>
              <Input id="next" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} required />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="confirm">Confirm new password</Label>
              <Input id="confirm" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
            </div>
            {message && (
              <p className={message.type === 'ok' ? 'text-sm text-emerald-600' : 'text-sm text-destructive'}>{message.text}</p>
            )}
          </CardContent>
          <CardFooter>
            <Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Change password'}</Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
