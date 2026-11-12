import { Link } from 'react-router-dom'
import { Camera, Clock, Eye, Link2, ShieldAlert, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const features = [
  {
    icon: Eye,
    title: 'Object detection',
    description: 'Detects people, backpacks, handbags and suitcases in live CCTV or webcam video using YOLOv8.',
  },
  {
    icon: Link2,
    title: 'Person–object association',
    description: 'Links each bag to the nearest person. Someone seated beside their bag does not trigger an alarm.',
  },
  {
    icon: Clock,
    title: 'Timed alerts',
    description: 'The countdown starts only when the person actually walks away or leaves the view. Alerts fire after the set time limit.',
  },
  {
    icon: ShieldAlert,
    title: 'Incident evidence',
    description: 'Each alert is saved with a snapshot, the distance and time involved, and a timeline of what happened.',
  },
]

const steps = [
  { title: 'Detect', text: 'Find people and bags in each frame.' },
  { title: 'Track', text: 'Keep the same ID on each object across frames.' },
  { title: 'Associate', text: 'Link each bag to the nearest person.' },
  { title: 'Time', text: 'Start a countdown when the person moves away.' },
  { title: 'Alert', text: 'Sound a warning and save the incident.' },
]

export function LandingPage() {
  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2 font-semibold">
          <img src="/assets/logo.png" alt="" className="size-8 rounded-lg object-contain" />
          VigiTrack
        </div>
        <Button asChild variant="outline">
          <Link to="/login">Sign in</Link>
        </Button>
      </header>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-16 text-center md:py-24">
        <img src="/assets/logo.png" alt="VigiTrack logo" className="mx-auto size-24 rounded-2xl object-contain" />
        <h1 className="text-4xl font-bold tracking-tight md:text-5xl">
          Know when a bag is left unattended
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
          VigiTrack is an AI surveillance system that watches CCTV or webcam video, detects unattended objects,
          and alerts staff before a situation becomes a problem. It runs on a local computer, with no face
          recognition.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Button asChild size="lg">
            <Link to="/login">Open the hub</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <a href="#how-it-works">How it works</a>
          </Button>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-16">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((feature) => (
            <Card key={feature.title}>
              <CardHeader>
                <feature.icon className="mb-2 size-6 text-primary" />
                <CardTitle>{feature.title}</CardTitle>
                <CardDescription>{feature.description}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>

      <section id="how-it-works" className="border-y bg-muted/40">
        <div className="mx-auto grid max-w-6xl gap-8 px-6 py-16">
          <div className="text-center">
            <h2 className="text-2xl font-semibold">How it works</h2>
            <p className="mt-2 text-muted-foreground">Five steps from video frame to alert.</p>
          </div>
          <ol className="grid gap-4 sm:grid-cols-5">
            {steps.map((step, i) => (
              <li key={step.title} className="grid gap-2 rounded-lg border bg-background p-4">
                <span className="flex size-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                  {i + 1}
                </span>
                <span className="font-medium">{step.title}</span>
                <span className="text-sm text-muted-foreground">{step.text}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-16 sm:grid-cols-3">
        <div className="grid gap-2 text-center sm:text-left">
          <Camera className="mx-auto size-6 text-primary sm:mx-0" />
          <h3 className="font-medium">Works with your cameras</h3>
          <p className="text-sm text-muted-foreground">Use a webcam, a virtual camera, or an RTSP stream from a CCTV recorder.</p>
        </div>
        <div className="grid gap-2 text-center sm:text-left">
          <Users className="mx-auto size-6 text-primary sm:mx-0" />
          <h3 className="font-medium">Built for schools and offices</h3>
          <p className="text-sm text-muted-foreground">Runs on an ordinary PC on the local network, without cloud costs.</p>
        </div>
        <div className="grid gap-2 text-center sm:text-left">
          <ShieldAlert className="mx-auto size-6 text-primary sm:mx-0" />
          <h3 className="font-medium">Staff stay in control</h3>
          <p className="text-sm text-muted-foreground">Thresholds are adjustable, and every alert is recorded for review.</p>
        </div>
      </section>

      <footer className="border-t py-6 text-center text-sm text-muted-foreground">
        VigiTrack · AI-Based Unattended Object Detection and Monitoring System
      </footer>
    </div>
  )
}
