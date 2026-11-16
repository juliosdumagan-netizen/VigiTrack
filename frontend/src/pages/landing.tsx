import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Camera, Check, Clock, Eye, Link2, ShieldAlert, ShieldCheck, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DetectionDemo } from '@/components/landing/detection-demo'
import { useInView } from '@/hooks/use-in-view'

const features = [
  {
    icon: Eye,
    title: 'Object detection',
    description:
      'Detects people and personal items \u2014 backpacks, luggage, purses \u2014 in live CCTV or webcam video using YOLOv8.',
  },
  {
    icon: Link2,
    title: 'Person\u2013object association',
    description:
      'Links each item to the nearest person, so someone seated next to their belongings never triggers an alarm.',
  },
  {
    icon: Clock,
    title: 'Timed alerts',
    description:
      'The countdown starts only when the person actually walks away or leaves the view. Alerts fire after the set time limit.',
  },
  {
    icon: ShieldAlert,
    title: 'Incident evidence',
    description:
      'Each alert is saved with a snapshot, the distance and time involved, and a timeline of what happened.',
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
    text: 'Use a webcam, a virtual camera, or an RTSP stream from a CCTV recorder.',
  },
  {
    icon: Users,
    title: 'Built for schools and offices',
    text: 'Runs on an ordinary PC on the local network, without cloud costs.',
  },
  {
    icon: ShieldCheck,
    title: 'Staff stay in control',
    text: 'Thresholds are adjustable, and every alert is recorded for review.',
  },
]

const reveal = (inView: boolean) =>
  `transition-all duration-700 ${inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'}`

export function LandingPage() {
  const [scrolled, setScrolled] = useState(false)
  const { ref: featuresRef, inView: featuresInView } = useInView<HTMLElement>()
  const { ref: stepsRef, inView: stepsInView } = useInView<HTMLDivElement>()
  const { ref: guaranteesRef, inView: guaranteesInView } = useInView<HTMLElement>()

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
            <img src="/assets/logo.png" alt="" className="size-8 rounded-lg object-contain" />
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
            <Button asChild variant="outline" size="sm" className="ml-2">
              <Link to="/login">Sign in</Link>
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
              <Button asChild size="lg">
                <Link to="/login">Open the hub</Link>
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
                Snapshot and timeline per alert
              </li>
            </ul>
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
              From live detection to evidence you can review afterwards.
            </p>
          </div>
          <div
            className={`mt-8 grid gap-4 transition-all duration-700 [transition-delay:150ms] sm:grid-cols-2 lg:grid-cols-4 ${
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
            <p className="mt-2 text-muted-foreground">Five steps from video frame to alert.</p>
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

      {/* Guarantees */}
      <section ref={guaranteesRef}>
        <div
          className={`mx-auto grid max-w-6xl gap-6 px-6 py-16 transition-all duration-700 sm:grid-cols-3 ${reveal(
            guaranteesInView,
          )}`}
        >
          {guarantees.map((item) => (
            <div key={item.title} className="grid gap-2 text-center sm:text-left">
              <item.icon className="mx-auto size-6 text-primary sm:mx-0" />
              <h3 className="font-medium">{item.title}</h3>
              <p className="text-sm text-muted-foreground">{item.text}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t py-6 text-center text-sm text-muted-foreground">
        VigiTrack &middot; AI-Based Unattended Object Detection and Monitoring System
      </footer>
    </div>
  )
}
