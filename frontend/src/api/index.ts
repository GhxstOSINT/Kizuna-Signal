import type { Analysis, AuthProvider, Job, ModelCard, PortfolioItem, Project, Scenario, Title, User } from './types'

export const API = import.meta.env.VITE_API_URL || '/api/v1'
/** Fired when the API says the session is gone, so the app can return to the sign-in page. */
export const UNAUTHORIZED_EVENT = 'kizuna-unauthorized'

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    const message = body?.error?.message || (Array.isArray(detail) ? detail.map((item) => item.msg).join(', ') : detail)
    // Only a call that needed a session signals it ended; /auth/me answering 401 just means "not signed in".
    if (response.status === 401 && path !== '/auth/me') window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    throw new ApiError(message || `Request failed with status ${response.status}.`, response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json()
}

export const api = {
  me: () => request<User>('/auth/me'),
  authProviders: () => request<{ providers: AuthProvider[] }>('/auth/providers'),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  readiness: () => request<{ status: string; database: string; demo_mode: boolean; model_status: 'ready' | 'fallback'; model_version: string; feature_version: string; scoring_version: string }>('/health/ready'),
  modelCard: () => request<ModelCard>('/model'),
  sourceHealth: () => request<{ mode: string; sources: { source: string; status: string; required: boolean }[]; policy: string }>('/sources/health'),
  listProjects: () => request<Project[]>('/projects'),
  listTitles: (projectId: string) => request<Title[]>(`/projects/${projectId}/titles`),
  getTitle: (titleId: string) => request<Title>(`/titles/${titleId}`),
  listAnalyses: (titleId: string) => request<Analysis[]>(`/titles/${titleId}/analyses`),
  getAnalysis: (id: string) => request<Analysis>(`/analyses/${id}`),
  deleteAnalysis: (id: string) => request<void>(`/analyses/${id}`, { method: 'DELETE' }),
  getJob: (id: string) => request<Job>(`/jobs/${id}`),
  createProject: (body: { name: string; description?: string }) => request<Project>('/projects', { method: 'POST', body: JSON.stringify(body) }),
  createTitle: (projectId: string, body: Record<string, unknown>) => request<Title>(`/projects/${projectId}/titles`, { method: 'POST', body: JSON.stringify(body) }),
  startAnalysis: (titleId: string) => request<{ analysis_id: string; job_id: string; status: string }>(`/titles/${titleId}/analyses`, { method: 'POST', body: '{}' }),
  listScenarios: (analysisId: string) => request<Scenario[]>(`/analyses/${analysisId}/scenarios`),
  createScenario: (analysisId: string, body: Record<string, unknown>) => request<Scenario>(`/analyses/${analysisId}/scenarios`, { method: 'POST', body: JSON.stringify(body) }),
}

export async function loadPortfolio(): Promise<PortfolioItem[]> {
  const projects = await api.listProjects()
  const rows = await Promise.all(projects.map(async (project) => {
    const titles = await api.listTitles(project.id)
    return Promise.all(titles.map(async (title) => {
      const analyses = await api.listAnalyses(title.id)
      const analysis = analyses.find((item) => item.result) || analyses[0]
      return analysis ? { project, title, analysis } : null
    }))
  }))
  return rows.flat().filter((row): row is PortfolioItem => Boolean(row))
}
