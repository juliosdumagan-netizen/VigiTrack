import type { Incident } from '@/lib/api'

type Evidence = NonNullable<Incident['class_evidence']>

const BAG_LABELS = ['backpack', 'handbag', 'suitcase', 'laptop']

/** True when the track was labelled as more than one bag type during its window. */
export function mixedBagLabels(evidence: Evidence) {
  return Object.keys(evidence).filter((k) => BAG_LABELS.includes(k)).length > 1
}

export function formatEvidence(evidence: Evidence) {
  return Object.entries(evidence)
    .sort((a, b) => b[1].frames - a[1].frames)
    .map(([name, e]) => `${name} ${e.frames} frames (best ${e.max_confidence.toFixed(2)})`)
    .join(' · ')
}
