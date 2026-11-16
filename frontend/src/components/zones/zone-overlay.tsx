import type { MouseEvent } from 'react'
import type { Zone, ZonePoint } from '@/lib/api'

type Props = {
  zones: Zone[]
  shape: ZonePoint[]
  editing: boolean
  onAddPoint?: (point: ZonePoint) => void
}

const ZONE_STYLE: Record<Zone['type'], { fill: string; stroke: string; text: string }> = {
  ignore: { fill: 'rgba(161,161,170,0.22)', stroke: '#a1a1aa', text: 'bg-zinc-400 text-zinc-950' },
  watch: { fill: 'rgba(251,191,36,0.18)', stroke: '#fbbf24', text: 'bg-amber-400 text-zinc-950' },
}

/**
 * Draws zones over the live feed. Points are normalised (0–1), so the overlay
 * stays aligned at any size. The parent must be a positioned box with the
 * same aspect ratio as the frame.
 */
export function ZoneOverlay({ zones, shape, editing, onAddPoint }: Props) {
  function handleClick(e: MouseEvent<HTMLDivElement>) {
    if (!editing || !onAddPoint) return
    const rect = e.currentTarget.getBoundingClientRect()
    const x = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
    const y = Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height))
    onAddPoint([Math.round(x * 1000) / 1000, Math.round(y * 1000) / 1000])
  }

  return (
    <div
      className={`absolute inset-0 ${editing ? 'cursor-crosshair' : 'pointer-events-none'}`}
      onClick={handleClick}
      role={editing ? 'application' : undefined}
      aria-label={editing ? 'Click the feed to add zone corners' : undefined}
    >
      <svg className="absolute inset-0 size-full" viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
        {zones.map((zone) => (
          <polygon
            key={zone.id}
            points={zone.points.map(([x, y]) => `${x},${y}`).join(' ')}
            fill={ZONE_STYLE[zone.type].fill}
            stroke={ZONE_STYLE[zone.type].stroke}
            strokeWidth={2}
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {shape.length > 1 && (
          <polyline
            points={shape.map(([x, y]) => `${x},${y}`).join(' ')}
            fill="none"
            stroke="#e4e4e7"
            strokeWidth={2}
            strokeDasharray="6 4"
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>

      {zones.map((zone) => {
        const [x, y] = zone.points[0]
        return (
          <span
            key={`${zone.id}-label`}
            className={`absolute -translate-y-full whitespace-nowrap rounded-sm px-1.5 py-px font-mono text-[10px] font-semibold shadow ${ZONE_STYLE[zone.type].text}`}
            style={{ left: `${x * 100}%`, top: `${y * 100}%` }}
          >
            {zone.name}
            {zone.type === 'watch' && zone.time_threshold != null ? ` · ${zone.time_threshold}s` : ''}
          </span>
        )
      })}

      {shape.map(([x, y], i) => (
        <span
          key={`corner-${i}`}
          className="absolute size-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-zinc-950 bg-white"
          style={{ left: `${x * 100}%`, top: `${y * 100}%` }}
        />
      ))}
    </div>
  )
}
