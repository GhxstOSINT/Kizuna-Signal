import type { Analysis, Job, ModelCard, PortfolioItem, Project, Scenario, StateSignal, StateSignalImportResult, Title } from './types'

const API = import.meta.env.VITE_API_URL || '/api/v1'

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
    const message = Array.isArray(detail) ? detail.map((item) => item.msg).join(', ') : detail
    throw new ApiError(message || `Request failed with status ${response.status}.`, response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json()
}

async function uploadCsv<T>(path: string, file: File, source: string): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  form.append('source', source)
  const response = await fetch(`${API}${path}`, { method: 'POST', body: form })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    const message = typeof detail === 'string' ? detail : detail?.message || (Array.isArray(detail) ? detail.map((item) => item.msg).join(', ') : '')
    throw new ApiError(message || `Request failed with status ${response.status}.`, response.status)
  }
  return response.json()
}

export const api = {
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
  listStateSignals: (titleId: string) => request<StateSignal[]>(`/titles/${titleId}/state-signals`),
  importStateSignals: (titleId: string, file: File, source: string) => uploadCsv<StateSignalImportResult>(`/titles/${titleId}/state-signals/import`, file, source),
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
