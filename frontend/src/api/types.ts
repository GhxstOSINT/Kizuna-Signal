export type User = { id: string; name: string; email?: string | null; avatar_url?: string | null }
export type AuthProvider = { id: 'google' | 'github'; label: string; enabled: boolean }
export type Project = { id: string; name: string; organization_name?: string; description?: string; created_at: string }
export type Title = {
  id: string; project_id: string; name: string; english_title?: string; synopsis: string
  content_format: string; primary_genre: string; genres: string[]; themes: string[]
  source_material: string; expected_release_period: string; target_platform: string
  target_languages: string[]; target_states: string[]; marketing_budget: string
  studio?: string; franchise_status?: string; trailer_url?: string; director?: string | null
  episode_count?: number | null; age_rating?: string | null; target_audience?: string | null; created_at: string
}
export type Job = {
  id: string; analysis_id: string; status: AnalysisStatus; progress: number; stage: string
  error_message?: string; created_at: string; updated_at: string
}
export type AnalysisStatus = 'queued' | 'running' | 'completed' | 'partially_completed' | 'failed'
export type SourceStatus = {
  source: string; status: 'available' | 'cached' | 'unavailable'; freshness_score: number
  quality_score: number; metrics: Record<string, number>; warnings: string[]; provenance: Record<string, string>
}
export type Region = {
  state: string; score: number; confidence: number; recommended_language: string
  preferred_platform: string; reasons: string[]
}
export type Driver = { name: string; contribution: number; direction: 'positive' | 'negative'; evidence: string }
export type Comparable = { title: string; similarity: number; market_signal: number; reasons: string[] }
export type Recommendation = {
  decision: string; platform: string; priority_markets: string[]; localization: string[]
  target_audience: string[]; launch_window: string; marketing_positioning: string
  campaign_actions: string[]; risks: string[]
}
export type AnalysisResult = {
  analysis_id: string; title_id: string; market_potential_score: number; decision_classification: string
  confidence_score: number; confidence_level: 'low' | 'medium' | 'high'; confidence_interval: [number, number]
  component_scores: Record<string, number>; regional_scores: Region[]; comparable_titles: Comparable[]
  positive_drivers: Driver[]; negative_drivers: Driver[]; source_status: SourceStatus[]
  data_quality_warnings: string[]; recommendation: Recommendation; model_version: string
  feature_version: string; scoring_version: string
  score_origin: 'trained_model' | 'deterministic_fallback'; score_meaning: string
  model_warnings: string[]; component_details: Record<string, unknown>[]
  model_evaluation: Record<string, string | number | null>
}
export type ModelCard = {
  model_version: string; task: string; trained_at?: string; n_labelled_titles: number; n_states: number
  training_data: Record<string, unknown>; evaluation: Record<string, unknown>
  success_model: Record<string, unknown> | null; limitations: string[]
}
export type Analysis = {
  id: string; title_id: string; status: AnalysisStatus; result: AnalysisResult | null
  warnings: string[]; model_version: string; feature_version: string; scoring_version: string
  error_message?: string; created_at: string; completed_at?: string
}
export type Scenario = {
  id: string; analysis_id: string; name: string; overrides: Record<string, unknown>
  result: { base_score: number; scenario_score: number; score_delta: number; base_confidence: number
    scenario_confidence: number; confidence_delta: number; cost_level: string; reach_level: string
    recommendation: Recommendation; applied_overrides: Record<string, unknown> }
  created_at: string
}
export type PortfolioItem = { project: Project; title: Title; analysis: Analysis }
