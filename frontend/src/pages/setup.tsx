import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export function SetupPage() {
  const navigate = useNavigate()
  const { setUser } = useAuth()
  const [checking, setChecking] = useState(true)
  const [codeRequired, setCodeRequired] = useState(true)
  const [setupCode, setSetupCode] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    api
      .setupStatus()
      .then((s) => {
        if (!s.setup_required) navigate('/login', { replace: true })
        else {
          setCodeRequired(s.setup_code_required)
          setChecking(false)
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Cannot reach the backend'))
  }, [navigate])

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)
    if (password !== confirm) {
      setError('The passwords do not match.')
      return
    }
    setSubmitting(true)
    try {
      const res = await api.completeSetup(setupCode.trim(), username.trim(), password)
      setUser(res.user)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Setup failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (checking && !error) {
    return <div className="flex min-h-svh items-center justify-center text-sm text-muted-foreground">Checking setup…</div>
  }

  return (
    <div className="flex min-h-svh items-center justify-center bg-muted/40 p-6">
      <Card className="w-full max-w-md">
        <CardHeader className="items-center text-center">
          <img src="/assets/logo.png" alt="VigiTrack logo" className="mx-auto mb-2 size-12 rounded-lg object-contain" />
          <CardTitle>Set up VigiTrack</CardTitle>
          <CardDescription>
            {codeRequired
              ? 'Create the administrator account for this computer. Enter the setup code shown in the VigiTrack backend terminal.'
              : 'Create the administrator account for this computer.'}
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit} className="grid gap-6">
          <CardContent className="grid gap-4">
            {codeRequired && (
              <div className="grid gap-2">
                <Label htmlFor="setup-code">Setup code</Label>
                <Input
                  id="setup-code"
                  placeholder="000-000-000"
                  autoComplete="off"
                  value={setupCode}
                  onChange={(e) => setSetupCode(e.target.value)}
                  required
                />
              </div>
            )}
            <div className="grid gap-2">
              <Label htmlFor="setup-username">Administrator username</Label>
              <Input id="setup-username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="setup-password">Password</Label>
              <Input id="setup-password" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
              <p className="text-xs text-muted-foreground">At least 8 characters.</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="setup-confirm">Confirm password</Label>
              <Input id="setup-confirm" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </CardContent>
          <CardFooter>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? 'Creating account…' : 'Create administrator account'}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
