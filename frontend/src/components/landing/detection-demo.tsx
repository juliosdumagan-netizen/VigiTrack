import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { Clock, RotateCcw, ShieldAlert } from 'lucide-react'

/**
 * Camera-feed chrome + FSM state machine around the 3D preview.
 * The scene itself lives in demo-scene.tsx and is lazy-loaded with the page.
 */

const DemoScene = lazy(() => import('./demo-scene'))

type Phase = 'attended' | 'separated' | 'countdown' | 'alert'

const ORDER: Phase[] = ['attended', 'separated', 'countdown', 'alert']

const DURATION_MS: Record<Phase, number> = {
  attended: 2800,
  separated: 2200,
  countdown: 4400,
  alert: 4200,
}

const STAGE_LABELS: Record<Phase, string> = {
  attended: 'Attended',
  separated: 'Separated',
  countdown: 'Countdown',
  alert: 'Alert',
}

const STAGE_CAPTIONS: Record<Phase, string> = {
  attended: 'Green proximity line — owner is within the distance threshold; no timer runs.',
  separated: 'Red proximity line — owner stepped beyond the distance threshold.',
  countdown: 'Separation timer active — cancels automatically if the owner returns in time.',
  alert: 'Time threshold exceeded — visual/audio alert triggered and snapshot logged.',
}

const STATUS: Record<Phase, { label: string; chip: string; dot: string }> = {
  attended: {
    label: 'Owner nearby \u00b7 attended',
    chip: 'border-white/15 bg-black/50 text-zinc-200',
    dot: 'bg-emerald-400',
  },
  separated: {
    label: 'Person separated',
    chip: 'border-amber-400/40 bg-amber-500/15 text-amber-300',
    dot: 'bg-amber-400 animate-pulse',
  },
  countdown: {
    label: 'Separation timer',
    chip: 'border-amber-400/40 bg-amber-500/15 text-amber-300',
    dot: 'bg-amber-400 animate-pulse',
  },
  alert: {
    label: 'Alert raised',
    chip: 'border-red-500/50 bg-red-500/15 text-red-300',
    dot: 'bg-red-500 animate-pulse',
  },
}

export function DetectionDemo() {
  const [phase, setPhase] = useState<Phase>('attended')
  const [count, setCount] = useState(10)
  const [runId, setRunId] = useState(0)
  const [clock, setClock] = useState(() => new Date().toTimeString().slice(0, 8))

  const reducedMotion = useMemo(
    () =>
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    [],
  )

  // Advance through the phases on a loop.
  useEffect(() => {
    if (reducedMotion) return
    const index = ORDER.indexOf(phase)
    const next = ORDER[(index + 1) % ORDER.length]
    const timer = window.setTimeout(() => {
      setPhase(next)
      setCount(next === 'alert' ? 0 : 10)
    }, DURATION_MS[phase])
    return () => window.clearTimeout(timer)
  }, [phase, runId, reducedMotion])

  // Tick the separation countdown down while that phase is active.
  useEffect(() => {
    if (reducedMotion || phase !== 'countdown') return
    const interval = window.setInterval(() => setCount((c) => (c > 0 ? c - 1 : 0)), 400)
    return () => window.clearInterval(interval)
  }, [phase, runId, reducedMotion])

  // Live-looking timestamp in the feed header.
  useEffect(() => {
    const interval = window.setInterval(
      () => setClock(new Date().toTimeString().slice(0, 8)),
      1000,
    )
    return () => window.clearInterval(interval)
  }, [])

  function goTo(next: Phase) {
    setPhase(next)
    setCount(next === 'alert' ? 0 : 10)
    setRunId((n) => n + 1)
  }

  const alerting = phase === 'alert'
  const status = STATUS[phase]

  return (
    <div className="animate-in fade-in-0 slide-in-from-right-6 duration-700 [animation-delay:300ms] motion-reduce:animate-none">
      <div className="overflow-hidden rounded-xl border border-white/10 bg-zinc-950 shadow-2xl">
        {/* Feed header: recorder-style strip */}
        <div className="flex items-center justify-between border-b border-white/10 px-3 py-2 text-[11px]">
          <span className="flex items-center gap-1.5 font-medium text-zinc-300">
            <span className="size-1.5 animate-pulse rounded-full bg-red-500" />
            REC
          </span>
          <span className="font-mono tracking-wider text-zinc-500">CAM 01 &middot; LOBBY</span>
          <span className="font-mono text-zinc-500">{clock}</span>
        </div>

        {/* 3D feed */}
        <div className="relative aspect-[4/3] overflow-hidden bg-zinc-950">
          <Suspense fallback={null}>
            <DemoScene phase={phase} reducedMotion={reducedMotion} />
          </Suspense>

          {/* Vignette and scan line keep the CCTV feel over the 3D render */}
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_45%,rgba(0,0,0,0.45))]" />
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-emerald-400/70 to-transparent animate-[vt-scan_5.5s_linear_infinite] motion-reduce:hidden" />

          {/* Alert banner */}
          {alerting && (
            <div className="absolute left-1/2 top-3 flex -translate-x-1/2 items-center gap-2 rounded-md border border-red-500/60 bg-red-600 px-3 py-1.5 text-xs font-semibold text-white shadow-lg animate-in fade-in-0 zoom-in-95">
              <ShieldAlert className="size-3.5" />
              Unattended object detected
            </div>
          )}

          {/* Pulsing red border while alerting */}
          {alerting && (
            <div className="pointer-events-none absolute inset-0 border-2 border-red-500 animate-[vt-alert-pulse_1.1s_ease-in-out_infinite] motion-reduce:animate-none" />
          )}

          {/* Status chip (bottom-left) */}
          <div
            className={`absolute bottom-3 left-3 flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium backdrop-blur-sm ${status.chip}`}
          >
            <span className={`size-1.5 rounded-full ${status.dot}`} />
            {status.label}
          </div>

          {/* Separation countdown (bottom-right) */}
          {(phase === 'countdown' || alerting) && (
            <div
              className={`absolute bottom-3 right-3 flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[11px] font-medium backdrop-blur-sm ${
                alerting
                  ? 'border-red-500/50 bg-black/60 text-red-300'
                  : 'border-amber-400/40 bg-black/60 text-amber-300'
              }`}
            >
              <Clock className="size-3" />
              00:{String(count).padStart(2, '0')}
            </div>
          )}
        </div>

        {/* Footer: clickable FSM stages + replay */}
        <div className="flex items-center justify-between gap-2 border-t border-white/10 px-3 py-2">
          <div className="flex items-center gap-1">
            {ORDER.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => goTo(p)}
                aria-label={`Show ${STAGE_LABELS[p]} stage`}
                className={`rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
                  phase === p
                    ? 'bg-white/10 text-zinc-100'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                {STAGE_LABELS[p]}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => goTo('attended')}
            aria-label="Replay demo"
            className="flex items-center gap-1 rounded-md border border-white/10 px-2 py-1 text-[10px] font-medium text-zinc-400 transition-colors hover:bg-white/5 hover:text-zinc-200"
          >
            <RotateCcw className="size-3" />
            Replay
          </button>
        </div>
      </div>
      <div className="mt-2.5 text-center text-xs">
        <p className="font-medium text-foreground/90">{STAGE_CAPTIONS[phase]}</p>
        <p className="mt-0.5 text-[11px] text-muted-foreground">
          Interactive 3D simulation &mdash; click any stage above to inspect the state machine.
        </p>
      </div>
    </div>
  )
}
