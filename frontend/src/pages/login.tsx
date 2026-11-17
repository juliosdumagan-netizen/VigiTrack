import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Eye, EyeOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, type Notice } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export function LoginPage() {
  const navigate = useNavigate()
  const { user, setUser } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [notice, setNotice] = useState<Notice | null>(null)

  useEffect(() => {
    api
      .setupStatus()
      .then((s) => {
        if (s.setup_required) navigate('/setup', { replace: true })
      })
      .catch(() => undefined)
    api.getNotice().then(setNotice).catch(() => undefined)
  }, [navigate])

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const res = await api.login(username.trim(), password)
      setUser(res.user)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-muted/40 p-6">
      <div className="w-full max-w-sm">
        <div className="mb-3">
          <Button asChild variant="ghost" size="sm" className="-ml-2 gap-1.5 text-muted-foreground hover:text-foreground">
            <Link to="/">
              <ArrowLeft className="size-4" />
              Back to homepage
            </Link>
          </Button>
        </div>

        <Card className="w-full">
          <CardHeader className="items-center text-center">
            <Link to="/" className="group flex flex-col items-center">
              <img
                src="/assets/logo.png"
                alt="VigiTrack logo"
                className="mx-auto mb-2 size-12 rounded-lg object-contain transition-transform group-hover:scale-105"
              />
              <CardTitle className="group-hover:underline">VigiTrack</CardTitle>
            </Link>
            <CardDescription>Sign in to the surveillance hub</CardDescription>
          </CardHeader>
          <form onSubmit={handleSubmit} className="grid gap-6">
            <CardContent className="grid gap-4">
              {user && (
                <div className="flex items-center justify-between gap-2 rounded-md border bg-muted/60 p-3 text-xs">
                  <span className="truncate text-muted-foreground">
                    Signed in as <strong className="text-foreground">{user.username}</strong>
                  </span>
                  <Button asChild size="sm" variant="secondary" className="h-7 shrink-0 gap-1 px-2.5 text-xs">
                    <Link to="/dashboard">
                      Dashboard
                      <ArrowRight className="size-3.5" />
                    </Link>
                  </Button>
                </div>
              )}
              {notice && (
                <p className="rounded-md bg-muted p-3 text-xs text-muted-foreground">
                  Privacy notice: this camera records for security monitoring. Detections are stored{' '}
                  {notice.retention_days} day{notice.retention_days === 1 ? '' : 's'} and then deleted automatically.
                </p>
              )}
              <div className="grid gap-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pr-10"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    title={showPassword ? 'Hide password' : 'Show password'}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
            </CardContent>
            <CardFooter>
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? 'Signing in…' : 'Sign in'}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  )
}
