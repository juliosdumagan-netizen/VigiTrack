import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Backpack,
  Briefcase,
  Camera,
  Check,
  Clock,
  Eye,
  FileCheck2,
  Link2,
  Scan,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  UserCheck,
  Users,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DetectionDemo } from '@/components/landing/detection-demo'
import { useInView } from '@/hooks/use-in-view'
import { useAuth } from '@/lib/auth'

const monitoredClasses = [
  { icon: UserCheck, label: 'Person (Owner)' },
  { icon: Backpack, label: 'Backpack' },
  { icon: ShoppingBag, label: 'Handbag' },
  { icon: Briefcase, label: 'Suitcase' },
]

const features = [
  {
    icon: Eye,
    title: 'Object detection',
    description:
      'Detects people and personal items \u2014 backpacks, handbags, suitcases \u2014 in live CCTV or webcam video using YOLOv8 and ByteTrack.',
  },
  {
    icon: Link2,
    title: 'Person\u2013object association',
    description:
      'Locks each item to its nearest owner so someone seated beside their belongings never triggers a false alarm, and passersby cannot hijack ownership.',
  },
  {
    icon: Clock,
    title: 'Timed alerts & hysteresis',
    description:
      'The countdown starts only when the owner truly steps beyond the distance threshold or leaves the frame. Alerts fire once the time limit expires.',
  },
  {
    icon: Scan,
    title: 'Watch & ignore zones',
    description:
      'Draw custom polygon zones directly over the camera view to enforce stricter countdowns in high-risk areas or ignore safe storage zones.',
  },
  {
    icon: ShieldAlert,
    title: 'Incident evidence & PDF reports',
    description:
      'Every alert captures a snapshot, pixel distance, state timeline, and operator review status, with one-click PDF incident reports and CSV exports.',
  },
  {
    icon: FileCheck2,
    title: 'Tamper-evident audit log',
    description:
      'Role-based access for Administrators and Operators backed by a SHA-256 hash-chained audit trail and password-confirmed incident deletion.',
  },
]

const steps = [
  { title: 'Detect', text: 'Find people and personal items in each frame.' },
  { title: 'Track', text: 'Keep the same ID on each object across frames.' },
  { title: 'Associate', text: 'Link each item to the nearest person.' },
  { title: 'Time', text: 'Start a countdown when the person moves away.' },
  { title: 'Alert', text: 'Sound a warning and save the incident.' },
]

const guarantees = [
  {
    icon: Camera,
    title: 'Works with your cameras',
    text: 'Use a built-in webcam, an OBS virtual camera, or an RTSP stream from an existing CCTV/NVR recorder.',
  },
  {
    icon: Users,
    title: 'Built for schools and offices',
    text: 'Runs entirely on a local PC on your institutional network — zero cloud subscriptions and no facial recognition.',
  },
  {
    icon: ShieldCheck,
    title: 'Human-in-the-loop verification',
    text: 'Decision-support design: operators acknowledge, verify, or dismiss alerts with notes while admins control thresholds and retention.',
  },
]

const reveal = (inView: boolean) =>
  `transition-all duration-700 ${inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'}`

export function LandingPage() {
  const { user } = useAuth()
  const [scrolled, setScrolled] = useState(false)
  const { ref: featuresRef, inView: featuresInView } = useInView<HTMLElement>()
  const { ref: stepsRef, inView: stepsInView } = useInView<HTMLDivElement>()
  const { ref: guaranteesRef, inView: guaranteesInView } = useInView<HTMLElement>()

  const hubPath = user ? '/dashboard' : '/login'

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="min-h-svh bg-background text-foreground">
      <header
        className={`sticky top-0 z-40 border-b transition-all duration-300 ${
          scrolled ? 'border-border bg-background/80 backdrop-blur-md' : 'border-transparent'
        }`}
      >
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <Link to="/" className="flex items-center gap-2 font-semibold">
            <img src="/assets/logo.png" alt="VigiTrack logo" className="size-8 rounded-lg object-contain" />
            VigiTrack
          </Link>
          <nav className="flex items-center gap-1">
            <a
              href="#features"
              className="hidden rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground sm:block"
            >
              Features
            </a>
            <a
              href="#how-it-works"
              className="hidden rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground sm:block"
            >
              How it works
            </a>
            <a
              href="#security"
              className="hidden rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground sm:block"
            >
              Security &amp; privacy
            </a>
            <Button asChild variant={user ? 'default' : 'outline'} size="sm" className="ml-2 gap-1.5">
              <Link to={hubPath}>
                {user ? (
                  <>
                    Go to Dashboard
                    <ArrowRight className="size-3.5" />
                  </>
                ) : (
                  'Sign in'
                )}
              </Link>
            </Button>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute left-1/2 top-[-180px] h-[480px] w-[820px] max-w-full -translate-x-1/2 rounded-full bg-primary/10 blur-3xl" />
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-14 md:grid-cols-2 md:gap-10 md:py-20">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border bg-muted/50 px-3 py-1 text-xs font-medium text-muted-foreground animate-in fade-in-0 duration-700 [animation-delay:100ms] motion-reduce:animate-none">
              <ShieldCheck className="size-3.5" />
              Runs locally &middot; no cloud &middot; no face recognition
            </span>
            <h1 className="mt-4 text-4xl font-bold tracking-tight md:text-5xl animate-in fade-in-0 slide-in-from-bottom-4 duration-700 [animation-delay:200ms] motion-reduce:animate-none">
              Get alerted when personal items are left behind
            </h1>
            <p className="mt-4 max-w-xl text-lg text-muted-foreground animate-in fade-in-0 slide-in-from-bottom-4 duration-700 [animation-delay:300ms] motion-reduce:animate-none">
              VigiTrack watches CCTV or webcam video, detects unattended objects, and alerts staff
              before a situation becomes a problem. It runs on a local computer.
            </p>
            <div className="mt-6 flex flex-wrap gap-3 animate-in fade-in-0 slide-in-from-bottom-4 duration-700 [animation-delay:400ms] motion-reduce:animate-none">
              <Button asChild size="lg" className="gap-2">
                <Link to={hubPath}>
                  {user ? 'Go to Dashboard' : 'Open the hub'}
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <a href="#how-it-works">How it works</a>
              </Button>
            </div>
            <ul className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground animate-in fade-in-0 duration-700 [animation-delay:500ms] motion-reduce:animate-none">
              <li className="flex items-center gap-1.5">
                <Check className="size-4 text-primary" />
                Webcam, RTSP or NVR input
              </li>
              <li className="flex items-center gap-1.5">
                <Check className="size-4 text-primary" />
                Adjustable alert thresholds
              </li>
              <li className="flex items-center gap-1.5">
                <Check className="size-4 text-primary" />
                Snapshot and PDF report per alert
              </li>
            </ul>

            <div className="mt-6 border-t pt-4 animate-in fade-in-0 duration-700 [animation-delay:550ms] motion-reduce:animate-none">
              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Monitored object classes
              </p>
              <div className="flex flex-wrap gap-2">
                {monitoredClasses.map((item) => (
                  <Badge key={item.label} variant="secondary" className="gap-1.5 px-2.5 py-1 text-xs font-medium">
                    <item.icon className="size-3.5 text-primary" />
                    {item.label}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
          <DetectionDemo />
        </div>
      </section>

      {/* Features */}
      <section id="features" ref={featuresRef} className="scroll-mt-20">
        <div className="mx-auto max-w-6xl px-6 pb-16">
          <div className={`mx-auto max-w-2xl text-center ${reveal(featuresInView)}`}>
            <h2 className="text-2xl font-semibold sm:text-3xl">
              Everything the operator needs, in one screen
            </h2>
            <p className="mt-2 text-muted-foreground">
              From live detection and custom watch zones to tamper-evident incident records.
            </p>
          </div>
          <div
            className={`mt-8 grid gap-4 transition-all duration-700 [transition-delay:150ms] sm:grid-cols-2 lg:grid-cols-3 ${
              featuresInView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
            }`}
          >
            {features.map((feature) => (
              <Card
                key={feature.title}
                className="transition-all duration-300 hover:-translate-y-1 hover:shadow-lg"
              >
                <CardHeader>
                  <feature.icon className="mb-2 size-6 text-primary" />
                  <CardTitle>{feature.title}</CardTitle>
                  <CardDescription>{feature.description}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="scroll-mt-20 border-y bg-muted/40">
        <div ref={stepsRef} className="mx-auto grid max-w-6xl gap-8 px-6 py-16">
          <div className={`text-center ${reveal(stepsInView)}`}>
            <h2 className="text-2xl font-semibold sm:text-3xl">How it works</h2>
            <p className="mt-2 text-muted-foreground">Five steps from video frame to verified alert.</p>
          </div>
          <ol
            className={`grid gap-4 transition-all duration-700 [transition-delay:150ms] sm:grid-cols-2 lg:grid-cols-5 ${
              stepsInView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
            }`}
          >
            {steps.map((step, i) => (
              <li
                key={step.title}
                className="group grid gap-2 rounded-lg border bg-background p-4 transition-all duration-300 hover:-translate-y-1 hover:border-primary/40 hover:shadow-md"
              >
                <span className="flex size-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground transition-transform duration-300 group-hover:scale-110">
                  {i + 1}
                </span>
                <span className="font-medium">{step.title}</span>
                <span className="text-sm text-muted-foreground">{step.text}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Security & Privacy */}
      <section id="security" ref={guaranteesRef} className="scroll-mt-20">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <div className={`mx-auto max-w-2xl text-center ${reveal(guaranteesInView)}`}>
            <h2 className="text-2xl font-semibold sm:text-3xl">
              Built for institutional security &amp; privacy
            </h2>
            <p className="mt-2 text-muted-foreground">
              On-premise computer vision designed for schools, libraries, and offices.
            </p>
          </div>
          <div
            className={`mt-10 grid gap-6 transition-all duration-700 [transition-delay:150ms] sm:grid-cols-3 ${reveal(
              guaranteesInView,
            )}`}
          >
            {guarantees.map((item) => (
              <div key={item.title} className="grid gap-2 rounded-xl border bg-muted/20 p-5 text-center sm:text-left">
                <item.icon className="mx-auto size-6 text-primary sm:mx-0" />
                <h3 className="font-medium">{item.title}</h3>
                <p className="text-sm text-muted-foreground">{item.text}</p>
              </div>
            ))}
          </div>

          {/* Bottom Call-to-Action Banner */}
          <div className="mt-14 flex flex-col items-center justify-between gap-6 rounded-2xl border bg-muted/40 p-8 text-center sm:flex-row sm:text-left">
            <div className="grid gap-1">
              <h3 className="text-xl font-semibold">Ready to monitor your cameras?</h3>
              <p className="text-sm text-muted-foreground">
                Launch the surveillance hub to view live detections, review incidents, and configure thresholds.
              </p>
            </div>
            <Button asChild size="lg" className="shrink-0 gap-2">
              <Link to={hubPath}>
                {user ? 'Go to Dashboard' : 'Sign in to Hub'}
                <ArrowRight className="size-4" />
              </Link>
            </Button>
          </div>
        </div>
      </section>

      <footer className="border-t bg-muted/20 py-8 text-sm text-muted-foreground">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 sm:flex-row">
          <div className="flex items-center gap-2">
            <img src="/assets/logo.png" alt="" className="size-6 rounded object-contain" />
            <span className="font-medium text-foreground">VigiTrack</span>
            <span>&middot; AI-Based Unattended Object Detection &amp; Monitoring System</span>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs">
            <a href="#features" className="hover:text-foreground">Features</a>
            <a href="#how-it-works" className="hover:text-foreground">How it works</a>
            <a href="#security" className="hover:text-foreground">Security &amp; privacy</a>
            <Link to={hubPath} className="font-medium text-foreground hover:underline">
              {user ? 'Dashboard' : 'Sign in'}
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
