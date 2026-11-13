import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { api, UnauthorizedError, type Incident } from '@/lib/api'
import { useAuth } from '@/lib/auth'

const POLL_MS = 5000

// Watches for new incidents while the hub is open and tells the operator about each new batch.
// The first check only records the newest incident, so opening the hub does not replay old alerts.
export function IncidentNotifier() {
  const { user, refresh } = useAuth()
  const navigate = useNavigate()
  const lastSeenId = useRef<number | null>(null)

  useEffect(() => {
    if (!user || user.must_change_password) return
    let active = true

    async function announce(fresh: Incident[]) {
      const latest = fresh[0]
      const settings = await api.getSettings().catch(() => null)
      if (settings?.audio_alert_enabled) playAlertTone()

      toast.warning(
        fresh.length > 1 ? `${fresh.length} new unattended-object alerts` : `Unattended ${latest.object_class} detected`,
        {
          description: `${latest.camera_name ?? 'Camera'} · ${new Date(latest.detected_at).toLocaleTimeString()}`,
          duration: 15000,
          action: { label: 'Review', onClick: () => navigate(`/incidents?selected=${latest.id}`) },
        },
      )
    }

    async function check() {
      try {
        const rows = await api.getIncidents()
        if (!active) return
        const newest = rows.reduce((max, row) => Math.max(max, row.id), 0)
        const previous = lastSeenId.current
        lastSeenId.current = newest
        if (previous === null) return

        const fresh = rows.filter((row) => row.id > previous)
        if (fresh.length > 0) await announce(fresh)
      } catch (err) {
        // Other errors are retried on the next check. An expired session sends the user back to sign-in.
        if (err instanceof UnauthorizedError) void refresh()
      }
    }

    check()
    const timer = setInterval(check, POLL_MS)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [user, navigate, refresh])

  return null
}

function playAlertTone() {
  try {
    const AudioCtx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    const ctx = new AudioCtx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.frequency.value = 1200
    gain.gain.value = 0.15
    osc.connect(gain).connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.35)
    osc.onended = () => void ctx.close()
  } catch {
    // Browsers block audio until the user has interacted with the page. The toast still shows.
  }
}
