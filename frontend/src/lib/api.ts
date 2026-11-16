export type Role = 'admin' | 'operator'

export type User = {
  id: number
  username: string
  role: Role
  is_active: boolean
  is_locked: boolean
  failed_attempts: number
  created_at: string
  last_login_at: string | null
  must_change_password: boolean
}

export type Settings = {
  distance_threshold: number
  time_threshold: number
  camera_source: number | string
  camera_name: string
  audio_alert_enabled: boolean
  monitored_classes: string[]
  retention_days: number
}

export type Notice = {
  retention_days: number
}

export type CameraStatus = {
  status: 'online' | 'reconnecting' | 'offline'
  last_frame_age: number | null
  camera_name: string
  source: number | string
}

export type Alert = {
  message: string
  time: string
  camera: string
}

export type ReviewStatus = 'open' | 'acknowledged' | 'verified' | 'dismissed'
export type ReviewAction = Exclude<ReviewStatus, 'open'>

export type IncidentState = {
  time: string
  state: string
}

export type Incident = {
  id: number
  object_class: string
  object_track_id: number | null
  person_track_id: number | null
  distance: number | null
  camera_name: string | null
  status: string
  detected_at: string
  image_url: string | null
  state_history: IncidentState[]
  distance_threshold: number | null
  time_threshold: number | null
  review_status: ReviewStatus
  review_note: string | null
  reviewed_by: string | null
  reviewed_at: string | null
  class_evidence: Record<string, { frames: number; max_confidence: number }> | null
}

export type ZoneKind = 'ignore' | 'watch'

/** Points are [x, y] in 0–1 across the frame. */
export type ZonePoint = [number, number]

export type Zone = {
  id: string
  name: string
  type: ZoneKind
  points: ZonePoint[]
  time_threshold?: number
}

export type ZonesResponse = {
  zones: Zone[]
  frame: { width: number; height: number } | null
}

export type AuditEntry = {
  id: number
  created_at: string
  actor: string | null
  action: string
  detail: string | null
}

export type AuditQuery = {
  actor?: string
  action?: string
  start?: string
  end?: string
  limit?: number
  offset?: number
}

export type AuditSearchResponse = { entries: AuditEntry[]; total: number }

export type AuditVerification = {
  ok: boolean
  first_bad_id: number | null
  unhashed_entries: number
}

function auditQueryString(params: AuditQuery) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  return search.toString()
}

export class UnauthorizedError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: 'same-origin',
    signal: AbortSignal.timeout(10000),
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })

  if (res.status === 401) {
    throw new UnauthorizedError('Authentication required')
  }

  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.message ?? `Request failed (${res.status})`)
  }
  return data as T
}

const json = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

/** Fetches a file download (CSV, PDF) as a Blob. Errors are thrown the same way as JSON requests. */
async function fetchFile(path: string): Promise<Blob> {
  const res = await fetch(path, {
    credentials: 'same-origin',
    signal: AbortSignal.timeout(60000),
  })
  if (res.status === 401) throw new UnauthorizedError('Authentication required')
  if (!res.ok) throw new Error(`Download failed (${res.status})`)
  return res.blob()
}

export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export const api = {
  login: (username: string, password: string) =>
    request<{ status: string; user: User }>('/api/login', json({ username, password })),

  logout: () => request<{ status: string }>('/api/logout', { method: 'POST' }),

  setupStatus: () =>
    request<{ setup_required: boolean; setup_code_required: boolean }>('/api/setup/status'),

  completeSetup: (setupCode: string, username: string, password: string) =>
    request<{ status: string; user: User }>('/api/setup', json({ setup_code: setupCode, username, password })),

  me: () => request<User>('/api/me'),

  changeOwnPassword: (currentPassword: string, newPassword: string) =>
    request<{ status: string }>('/api/me/password', json({ current_password: currentPassword, new_password: newPassword })),

  getSettings: () => request<Settings>('/api/settings'),

  updateSettings: (payload: Record<string, unknown>) =>
    request<{ status: string; settings: Settings }>('/api/settings', { method: 'POST', body: JSON.stringify(payload) }),

  getAlerts: () => request<Alert[]>('/api/alerts'),

  getCameraStatus: () => request<CameraStatus>('/api/camera/status'),

  getIncidents: () => request<Incident[]>('/api/incidents'),

  getIncident: (id: number) => request<Incident>(`/api/incidents/${id}`),

  reviewIncident: (id: number, action: ReviewAction, note?: string) =>
    request<{ status: string; incident: Incident }>(`/api/incidents/${id}/review`, json({ action, note })),

  deleteIncident: (id: number) => request<{ success: boolean }>(`/api/incidents/${id}`, { method: 'DELETE' }),

  clearIncidents: () => request<{ success: boolean }>('/api/incidents/clear', { method: 'POST' }),

  purgeIncidents: (start: string, end: string) =>
    request<{ status: string; deleted: number }>('/api/incidents/purge', json({ start, end })),

  exportIncidentsCsv: () => fetchFile('/api/incidents/export.csv'),

  incidentReportPdf: (id: number) => fetchFile(`/api/incidents/${id}/report.pdf`),

  getNotice: () => request<Notice>('/api/notice'),

  getZones: () => request<ZonesResponse>('/api/zones'),

  saveZones: (zones: Zone[]) =>
    request<{ status: string; zones: Zone[] }>('/api/zones', json({ zones })),

  listUsers: () => request<User[]>('/api/users'),

  createUser: (username: string, password: string, role: Role) =>
    request<{ status: string; user: User }>('/api/users', json({ username, password, role })),

  updateUser: (id: number, changes: Partial<{ role: Role; is_active: boolean; unlock: boolean; new_password: string }>) =>
    request<{ status: string; user: User }>(`/api/users/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }),

  deleteUser: (id: number) => request<{ status: string }>(`/api/users/${id}`, { method: 'DELETE' }),

  searchAudit: (params: AuditQuery) => request<AuditSearchResponse>(`/api/audit/search?${auditQueryString(params)}`),

  auditActions: () => request<string[]>('/api/audit/actions'),

  verifyAudit: () => request<AuditVerification>('/api/audit/verify'),

  exportAuditCsv: (params: AuditQuery) => fetchFile(`/api/audit/export.csv?${auditQueryString(params)}`),
}
