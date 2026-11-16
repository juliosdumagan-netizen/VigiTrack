import * as React from "react"
import {
  CalendarDaysIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronsLeftIcon,
  ChevronsRightIcon,
} from "lucide-react"
import { cn } from "cn"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]

/** Parse a YYYY-MM-DD string as a local date (no timezone shift). */
function parseISO(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return null
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
  return Number.isNaN(date.getTime()) ? null : date
}

function toISO(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

function formatDisplay(date: Date): string {
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

interface DatePickerProps {
  /** Selected date as YYYY-MM-DD, or '' for none. */
  value: string
  onChange: (value: string) => void
  id?: string
  placeholder?: string
  disabled?: boolean
  /** Show a Clear action in the footer while a date is set. */
  clearable?: boolean
  className?: string
  "aria-label"?: string
}

/**
 * Custom calendar dropdown: a trigger styled like the app's inputs that opens
 * a month grid in a popover. Values stay in YYYY-MM-DD form.
 */
function DatePicker({
  value,
  onChange,
  id,
  placeholder = "Pick a date",
  disabled,
  clearable = true,
  className,
  ...aria
}: DatePickerProps) {
  const selected = parseISO(value)
  const [open, setOpen] = React.useState(false)
  const [view, setView] = React.useState<Date>(() => startOfMonth(selected ?? new Date()))
  const [todayISO, setTodayISO] = React.useState<string>(() => toISO(new Date()))

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (next) {
      const now = new Date()
      setTodayISO(toISO(now))
      setView(startOfMonth(parseISO(value) ?? now))
    }
  }

  function choose(date: Date) {
    onChange(toISO(date))
    setOpen(false)
  }

  const year = view.getFullYear()
  const month = view.getMonth()
  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()

  const cells: Array<Date | null> = []
  for (let i = 0; i < 42; i += 1) {
    const day = i - firstDay + 1
    cells.push(day >= 1 && day <= daysInMonth ? new Date(year, month, day) : null)
  }

  const navButton =
    "flex size-7 items-center justify-center rounded-md text-muted-foreground outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:ring-3 focus-visible:ring-ring/50"

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <button
          type="button"
          id={id}
          disabled={disabled}
          aria-label={aria["aria-label"]}
          className={cn(
            "flex h-9 w-full min-w-0 items-center gap-2 rounded-md border border-input bg-transparent px-2.5 py-1 text-sm shadow-xs transition-[color,box-shadow] outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 dark:bg-input/30",
            !value && "text-muted-foreground",
            className
          )}
        >
          <CalendarDaysIcon className="size-4 shrink-0 text-muted-foreground" />
          <span className="flex-1 truncate text-left">
            {selected ? formatDisplay(selected) : placeholder}
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-fit p-0">
        <div className="grid gap-3 p-3">
          <div className="flex items-center justify-between gap-1">
            <button
              type="button"
              aria-label="Previous year"
              className={navButton}
              onClick={() => setView(new Date(year - 1, month, 1))}
            >
              <ChevronsLeftIcon />
            </button>
            <button
              type="button"
              aria-label="Previous month"
              className={navButton}
              onClick={() => setView(new Date(year, month - 1, 1))}
            >
              <ChevronLeftIcon />
            </button>
            <div className="min-w-36 text-center text-sm font-medium">
              {view.toLocaleDateString("en-US", { month: "long", year: "numeric" })}
            </div>
            <button
              type="button"
              aria-label="Next month"
              className={navButton}
              onClick={() => setView(new Date(year, month + 1, 1))}
            >
              <ChevronRightIcon />
            </button>
            <button
              type="button"
              aria-label="Next year"
              className={navButton}
              onClick={() => setView(new Date(year + 1, month, 1))}
            >
              <ChevronsRightIcon />
            </button>
          </div>

          <div className="grid grid-cols-7 gap-1">
            {WEEKDAYS.map((day) => (
              <div
                key={day}
                className="flex size-8 items-center justify-center text-xs font-medium text-muted-foreground"
              >
                {day}
              </div>
            ))}
            {cells.map((date, i) => {
              if (!date) return <div key={`blank-${i}`} className="size-8" />
              const iso = toISO(date)
              const isSelected = iso === value
              const isToday = iso === todayISO
              return (
                <button
                  key={iso}
                  type="button"
                  aria-label={formatDisplay(date)}
                  aria-pressed={isSelected}
                  onClick={() => choose(date)}
                  className={cn(
                    "flex size-8 items-center justify-center rounded-md text-sm outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50",
                    isSelected
                      ? "bg-primary font-medium text-primary-foreground"
                      : isToday
                        ? "ring-1 ring-ring/60 hover:bg-accent hover:text-accent-foreground"
                        : "hover:bg-accent hover:text-accent-foreground"
                  )}
                >
                  {date.getDate()}
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-border p-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onChange(todayISO)
              setOpen(false)
            }}
          >
            Today
          </Button>
          {clearable && (
            <Button
              variant="ghost"
              size="sm"
              disabled={!value}
              onClick={() => {
                onChange("")
                setOpen(false)
              }}
            >
              Clear
            </Button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}

export { DatePicker }
