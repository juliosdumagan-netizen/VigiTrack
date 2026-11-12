import { useEffect, useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { api } from '@/lib/api'

export function SettingsPage() {
  const [loaded, setLoaded] = useState(false)
  const [distance, setDistance] = useState('150')
  const [time, setTime] = useState('10')
  const [audio, setAudio] = useState(true)
  const [message, setMessage] = useState<{ type: 'ok' | 'error'; text: string } | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api
      .getSettings()
      .then((s) => {
        setDistance(String(s.distance_threshold))
        setTime(String(s.time_threshold))
        setAudio(s.audio_alert_enabled)
        setLoaded(true)
      })
      .catch((err) => setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to load settings' }))
  }, [])

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setMessage(null)

    const distanceNum = Number(distance)
    const timeNum = Number(time)
    if (!(distanceNum > 0) || !(timeNum > 0)) {
      setMessage({ type: 'error', text: 'Distance and time thresholds must be positive numbers.' })
      return
    }

    setSaving(true)
    try {
      await api.updateSettings({
        distance_threshold: distanceNum,
        time_threshold: timeNum,
        audio_alert_enabled: audio,
      })
      setMessage({ type: 'ok', text: 'Settings saved and active.' })
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Save failed' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid max-w-2xl gap-4">
      <form onSubmit={handleSubmit} className="grid gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Detection</CardTitle>
            <CardDescription>Thresholds for person–object association and alerts</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="distance">Distance threshold (pixels)</Label>
              <Input id="distance" type="number" min={10} step={10} value={distance} onChange={(e) => setDistance(e.target.value)} disabled={!loaded} />
              <p className="text-xs text-muted-foreground">Maximum pixel distance between a person and their bag.</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="time">Time threshold (seconds)</Label>
              <Input id="time" type="number" min={1} step={1} value={time} onChange={(e) => setTime(e.target.value)} disabled={!loaded} />
              <p className="text-xs text-muted-foreground">How long a bag may be unattended before an alert fires.</p>
            </div>
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <Label htmlFor="audio">Audible alert beeps</Label>
                <p className="text-xs text-muted-foreground">Play a warning tone on unattended alerts.</p>
              </div>
              <Switch id="audio" checked={audio} onCheckedChange={setAudio} disabled={!loaded} />
            </div>
          </CardContent>
          <CardFooter className="flex-col items-stretch gap-3">
            {message && (
              <p className={message.type === 'ok' ? 'text-sm text-emerald-600' : 'text-sm text-destructive'}>{message.text}</p>
            )}
            <Button type="submit" disabled={!loaded || saving}>
              {saving ? 'Saving…' : 'Save settings'}
            </Button>
          </CardFooter>
        </Card>
      </form>
    </div>
  )
}
