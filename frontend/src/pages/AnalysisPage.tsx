import { ArrowRight, Beaker, FileText, MapPin } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { PageHeader, SignalRail } from '../components/AppShell'
import { ErrorState, LoadingState, ScoreField, SectionHeading, StatusBadge } from '../components/Primitives'
import type { Analysis, Title } from '../api/types'

const label = (value: string) => value.replaceAll('_',' ').replace(/\b\w/g,(c)=>c.toUpperCase())

const ratings: Record<string, string> = { all_ages: 'All ages', '7_plus': '7+', '13_plus': '13+', '16_plus': '16+', '18_plus': '18+' }

function TitleDetails({ title }: { title: Title }) {
  const rows: [string, string | null | undefined][] = [
    ['Title', title.english_title ? `${title.name} / ${title.english_title}` : title.name],
    ['Format', title.content_format ? label(title.content_format) : null],
    ['Genre', title.primary_genre],
    ['Source', title.source_material],
    ['Studio', title.studio],
    ['Director', title.director],
    ['Episodes', title.episode_count ? String(title.episode_count) : null],
    ['Age rating', title.age_rating ? ratings[title.age_rating] ?? title.age_rating : null],
    ['Audience', title.target_audience],
    ['Franchise', title.franchise_status],
    ['Release', title.expected_release_period],
    ['Platform', title.target_platform],
    ['Budget', title.marketing_budget ? label(title.marketing_budget) : null],
    ['Languages', title.target_languages.join(', ')],
    ['States', title.target_states.join(', ')],
  ]
  return <section className="title-details"><SectionHeading title="Title details" note="The intake record saved by the backend for this analysis."/><dl>{rows.filter(([, value]) => value).map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl></section>
}

export function AnalysisPage({ connected }: { connected: boolean }) {
  const { analysisId = '' } = useParams()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [title, setTitle] = useState<Title | null>(null)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    let cancelled = false
    let timeout: number | undefined
    let delay = 1_500
    const poll = async () => {
      try {
        const next = await api.getAnalysis(analysisId)
        if (cancelled) return
        setAnalysis(next)
        setError('')
        if (!next.result && ['queued','running','partially_completed'].includes(next.status)) {
          timeout = window.setTimeout(() => { void poll() }, delay)
          delay = Math.min(Math.round(delay * 1.5), 5_000)
        }
      } catch (requestError) {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : 'Analysis could not be loaded.')
      }
    }
    void poll()
    return () => { cancelled = true; if (timeout) window.clearTimeout(timeout) }
  },[analysisId, refresh])
  const titleId = analysis?.title_id
  useEffect(() => {
    if (!titleId) return
    let cancelled = false
    api.getTitle(titleId).then((next) => { if (!cancelled) setTitle(next) }).catch(() => { if (!cancelled) setTitle(null) })
    return () => { cancelled = true }
  }, [titleId])
  if (error) return <div className="page"><ErrorState message={error} retry={()=>setRefresh(value=>value+1)}/></div>
  if (!analysis) return <div className="page"><LoadingState label="Opening analysis"/></div>
  if (!analysis.result) return <div className="page"><PageHeader title="Analysis in progress" description="The backend has created the snapshot and this page will update automatically."/><SignalRail connected={connected} label={analysis.status.toUpperCase()}/><div className="state-block" aria-live="polite"><StatusBadge status={analysis.status}/><h2>{label(analysis.status)}</h2><p>{analysis.error_message || 'Evidence stages are still running. You can safely reload or return later.'}</p></div></div>
  const r = analysis.result
  return <div className="page analysis-page">
    <PageHeader title="Decision intelligence" description="A frozen, versioned result with evidence, regional opportunity and launch guidance." action={<div className="action-pair"><Link className="button ghost" to={`/analysis/${analysisId}/scenarios`}><Beaker size={16}/>Scenario lab</Link><Link className="button dark" to={`/analysis/${analysisId}/playbook`}><FileText size={16}/>Launch playbook</Link></div>} />
    <SignalRail connected={connected} label={`${r.model_version} / ${r.scoring_version}`} />
    {title&&<TitleDetails title={title}/>}
    <ScoreField score={r.market_potential_score} confidence={r.confidence_score} interval={r.confidence_interval} classification={r.decision_classification} origin={r.score_origin} meaning={r.score_meaning}/>
    {r.data_quality_warnings.length>0&&<section className="warning-band"><strong>Evidence notes</strong><div>{r.data_quality_warnings.map((warning)=><p key={warning}>{warning}</p>)}</div></section>}
    {r.score_origin==='trained_model'&&<section className="model-proof"><SectionHeading title="Model validation" note="Historical holdout results describe ranking performance on past titles. They are not a guarantee for a new release."/><div className="model-proof-grid"><article><strong>{r.model_evaluation.labelled_titles??'—'}</strong><span>Labelled titles used</span></article><article><strong>{r.model_evaluation.oof_titles??'—'}</strong><span>Out-of-fold titles</span></article><article><strong>{typeof r.model_evaluation.spearman==='number'?r.model_evaluation.spearman.toFixed(2):'—'}</strong><span>Mean Spearman ranking</span></article><article><strong>{typeof r.model_evaluation.top3_hit==='number'?`${Math.round(r.model_evaluation.top3_hit*100)}%`:'—'}</strong><span>Top-three hit rate</span></article></div><p className="model-proof-note">Validation: {r.model_evaluation.scheme||'not reported'}. India-specific commercial outcomes are not part of this training target.</p></section>}
    <section className="component-plane"><SectionHeading title="What shaped the score" note={r.score_origin==='trained_model'?'Only measured components that passed held-out validation contribute to this score. Unavailable and unvalidated components are excluded.':'The fallback components combine into this market-potential result.'}/><div className="component-list">{Object.entries(r.component_scores).sort((a,b)=>b[1]-a[1]).map(([key,value])=><div className="component-row" key={key}><span>{label(key)}</span><div className="component-track"><i style={{width:`${value}%`}}/></div><strong>{Math.round(value)}</strong></div>)}</div>{r.component_details.length>0&&<div className="component-detail-list">{r.component_details.map((item)=>{const key=String(item.key);const status=String(item.status);return <article key={key}><strong>{label(key)}</strong><span>{status.replaceAll('_',' ')}</span><p>{typeof item.reason==='string'?item.reason:`${Number(item.weight)*100}% configured weight; ${item.validation_spearman??'not reported'} held-out Spearman.`}</p></article>})}</div>}</section>
    <section><SectionHeading title="Regional opportunity" note="The strongest current state-language-platform combinations."/><div className="region-grid">{r.regional_scores.slice(0,8).map((region,index)=><article className="region-lane" key={region.state}><div className="region-rank">{String(index+1).padStart(2,'0')}</div><div><h3>{region.state}</h3><p><MapPin size={13}/>{region.recommended_language} · {region.preferred_platform}</p></div><div className="region-meter"><i style={{width:`${region.score}%`}}/></div><strong>{Math.round(region.score)}</strong><details><summary>Why this market</summary>{region.reasons.map((reason)=><p key={reason}>{reason}</p>)}</details></article>)}</div></section>
    <section className="drivers-plane"><SectionHeading title="Evidence ledger" note="Positive and negative contributions are shown with their backend explanation."/><div className="driver-columns"><div><h3>Signals supporting investment</h3>{r.positive_drivers.map((driver)=><article className="driver" key={driver.name}><div><strong>{driver.name}</strong><p>{driver.evidence}</p></div><span>+{driver.contribution.toFixed(1)}</span></article>)}</div><div><h3>Signals requiring caution</h3>{r.negative_drivers.length?r.negative_drivers.map((driver)=><article className="driver negative" key={driver.name}><div><strong>{driver.name}</strong><p>{driver.evidence}</p></div><span>−{driver.contribution.toFixed(1)}</span></article>):<p className="quiet">No material negative driver was emitted by this result.</p>}</div></div></section>
    <section><SectionHeading title="Comparable evidence" note="Similarity is contextual evidence, not proof of identical commercial performance."/><div className="comparable-table" role="table">{r.comparable_titles.map((item)=><div className="comparable-row" role="row" key={item.title}><div><strong>{item.title}</strong><p>{item.reasons.join(' · ')}</p></div><span>{Math.round(item.similarity*100)}% similar</span><span>{Math.round(item.market_signal)} signal</span></div>)}</div></section>
    <section><SectionHeading title="Source health" note="Every source carries availability, freshness, quality, provenance and warnings."/><div className="source-table">{r.source_status.map((source)=><article className="source-row" key={source.source}><div><StatusBadge status={source.status}/><strong>{label(source.source)}</strong></div><dl><div><dt>Freshness</dt><dd>{Math.round(source.freshness_score*100)}%</dd></div><div><dt>Quality</dt><dd>{Math.round(source.quality_score*100)}%</dd></div><div><dt>Mode</dt><dd>{source.provenance.mode || 'unspecified'}</dd></div></dl><p>{source.warnings.join(' ') || 'No source warning.'}</p></article>)}</div></section>
    <section className="next-actions"><div><h2>Turn the result into a decision.</h2><p>Compare controlled changes, then review the recommended launch sequence.</p></div><Link to={`/analysis/${analysisId}/scenarios`}>Open scenario lab <ArrowRight/></Link></section>
  </div>
}
