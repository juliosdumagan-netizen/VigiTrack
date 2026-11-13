import { useEffect, useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { api } from '@/lib/api'

type BagClass = 'backpack' | 'handbag' | 'suitcase'

const BAG_CLASSES: { key: BagClass; label: string }[] = [
  { key: 'backpack', label: 'Backpack' },
  { key: 'handbag', label: 'Handbag' },
  { key: 'suitcase', label: 'Suitcase' },
]

export function SettingsPage() {
  const [loaded, setLoaded] = useState(false)
  const [distance, setDistance] = useState('150')
  const [time, setTime] = useState('10')
  const [audio, setAudio] = useState(true)
  const [bags, setBags] = useState<Record<BagClass, boolean>>({ backpack: true, handbag: true, suitcase: true })
  const [retention, setRetention] = useState('30')
  const [message, setMessage] = useState<{ type: 'ok' | 'error'; text: string } | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api
      .getSettings()
      .then((s) => {
        setDistance(String(s.distance_threshold))
        setTime(String(s.time_threshold))
        setAudio(s.audio_alert_enabled)
        setRetention(String(s.retention_days))
        setBags({
          backpack: s.monitored_classes.includes('backpack'),
          handbag: s.monitored_classes.includes('handbag'),
          suitcase: s.monitored_classes.includes('suitcase'),
        })
        setLoaded(true)
      })
      .catch((err) => setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to load settings' }))
  }, [])

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setMessage(null)

    const distanceNum = Number(distance)
    const timeNum = Number(time)
    const retentionNum = Number(retention)
    if (!(distanceNum > 0) || !(timeNum > 0)) {
      setMessage({ type: 'error', text: 'Distance and time thresholds must be positive numbers.' })
      return
    }
    if (!Number.isInteger(retentionNum) || retentionNum < 1 || retentionNum > 3650) {
      setMessage({ type: 'error', text: 'Retention must be a whole number between 1 and 3650 days.' })
      return
    }

    setSaving(true)
    try {
      const monitored_classes = ['person', ...BAG_CLASSES.filter((c) => bags[c.key]).map((c) => c.key)]
      await api.updateSettings({
        distance_threshold: distanceNum,
        time_threshold: timeNum,
        audio_alert_enabled: audio,
        monitored_classes,
        retention_days: retentionNum,
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
            <CardTitle>Objects to monitor</CardTitle>
            <CardDescription>Person is always monitored, because bags are linked to the person nearest them</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <div className="flex items-center justify-between rounded-lg border p-3">
              <Label>Person</Label>
              <Switch checked disabled />
            </div>
            {BAG_CLASSES.map((c) => (
              <div key={c.key} className="flex items-center justify-between rounded-lg border p-3">
                <Label htmlFor={`monitor-${c.key}`}>{c.label}</Label>
                <Switch
                  id={`monitor-${c.key}`}
                  checked={bags[c.key]}
                  onCheckedChange={(v) => setBags((prev) => ({ ...prev, [c.key]: v }))}
                  disabled={!loaded}
                />
              </div>
            ))}
            <p className="text-xs text-muted-foreground">Changes take effect on the next detection frame. No restart needed.</p>
          </CardContent>
        </Card>

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
            <div className="grid gap-2">
              <Label htmlFor="retention">Record retention (days)</Label>
              <Input
                id="retention"
                type="number"
                min={1}
                max={3650}
                step={1}
                value={retention}
                onChange={(e) => setRetention(e.target.value)}
                disabled={!loaded}
              />
              <p className="text-xs text-muted-foreground">
                Incidents and snapshots older than this are deleted automatically, at least once an hour. Also shown on the sign-in privacy notice.
              </p>
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
