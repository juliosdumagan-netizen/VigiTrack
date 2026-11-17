import { useEffect, useState, type FormEvent } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  confirmLabel?: string
  destructive?: boolean
  requirePassword?: boolean
  onConfirm: (password: string) => void | Promise<void>
}

/**
 * Shared confirmation modal for destructive actions.
 * The dialog stays open until onConfirm resolves, then closes itself;
 * if onConfirm throws, it stays open so the caller or inline error can surface the message.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirm',
  destructive = true,
  requirePassword = false,
  onConfirm,
}: Props) {
  const [busy, setBusy] = useState(false)
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) {
      setPassword('')
      setShowPassword(false)
      setError(null)
    }
  }, [open])

  async function handleConfirm(e?: FormEvent<HTMLFormElement>) {
    e?.preventDefault()
    if (requirePassword && !password) {
      setError('Enter your administrator password to confirm.')
      return
    }
    setError(null)
    setBusy(true)
    try {
      await onConfirm(password)
      onOpenChange(false)
    } catch (err) {
      if (requirePassword) {
        setError(err instanceof Error ? err.message : 'Confirmation failed.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !busy && onOpenChange(next)}>
      <DialogContent className="sm:max-w-sm">
        <form onSubmit={handleConfirm} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>{description}</DialogDescription>
          </DialogHeader>

          {requirePassword && (
            <div className="grid gap-2">
              <Label htmlFor="confirm-admin-password">Administrator password</Label>
              <div className="relative">
                <Input
                  id="confirm-admin-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Enter your password to confirm"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    if (error) setError(null)
                  }}
                  className="pr-10"
                  disabled={busy}
                  autoFocus
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
              {error && <p className="text-xs text-destructive">{error}</p>}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant={destructive ? 'destructive' : 'default'}
              disabled={busy || (requirePassword && !password)}
            >
              {busy ? 'Working…' : confirmLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
