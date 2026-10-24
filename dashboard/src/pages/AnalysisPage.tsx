import { ArrowRight, Beaker, FileText, MapPin } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { PageHeader, SignalRail } from '../components/AppShell'
import { ErrorState, LoadingState, ScoreField, SectionHeading, StatusBadge } from '../components/Primitives'
import type { Analysis } from '../types'

const label = (value: string) => value.replaceAll('_',' ').replace(/\b\w/g,(c)=>c.toUpperCase())

export function AnalysisPage({ connected }: { connected: boolean }) {
  const { analysisId = '' } = useParams()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
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
  if (error) return <div className="page"><ErrorState message={error} retry={()=>setRefresh(value=>value+1)}/></div>
  if (!analysis) return <div className="page"><LoadingState label="Opening analysis"/></div>
  if (!analysis.result) return <div className="page"><PageHeader title="Analysis in progress" description="The backend has created the snapshot and this page will update automatically."/><SignalRail connected={connected} label={analysis.status.toUpperCase()}/><div className="state-block" aria-live="polite"><StatusBadge status={analysis.status}/><h2>{label(analysis.status)}</h2><p>{analysis.error_message || 'Evidence stages are still running. You can safely reload or return later.'}</p></div></div>
  const r = analysis.result
  return <div className="page analysis-page">
    <PageHeader title="Decision intelligence" description="A frozen, versioned result with evidence, regional opportunity and launch guidance." action={<div className="action-pair"><Link className="button ghost" to={`/analysis/${analysisId}/scenarios`}><Beaker size={16}/>Scenario lab</Link><Link className="button dark" to={`/analysis/${analysisId}/playbook`}><FileText size={16}/>Launch playbook</Link></div>} />
    <SignalRail connected={connected} label={`${r.model_version} / ${r.scoring_version}`} />
    <ScoreField score={r.market_potential_score} confidence={r.confidence_score} interval={r.confidence_interval} classification={r.decision_classification}/>
    {r.data_quality_warnings.length>0&&<section className="warning-band"><strong>Evidence notes</strong><div>{r.data_quality_warnings.map((warning)=><p key={warning}>{warning}</p>)}</div></section>}
    <section className="component-plane"><SectionHeading title="What shaped the score" note="Five backend-owned components combine into the market-potential result."/><div className="component-list">{Object.entries(r.component_scores).sort((a,b)=>b[1]-a[1]).map(([key,value])=><div className="component-row" key={key}><span>{label(key)}</span><div className="component-track"><i style={{width:`${value}%`}}/></div><strong>{Math.round(value)}</strong></div>)}</div></section>
    <section><SectionHeading title="Regional opportunity" note="The strongest current state-language-platform combinations."/><div className="region-grid">{r.regional_scores.slice(0,8).map((region,index)=><article className="region-lane" key={region.state}><div className="region-rank">{String(index+1).padStart(2,'0')}</div><div><h3>{region.state}</h3><p><MapPin size={13}/>{region.recommended_language} · {region.preferred_platform}</p></div><div className="region-meter"><i style={{width:`${region.score}%`}}/></div><strong>{Math.round(region.score)}</strong><details><summary>Why this market</summary>{region.reasons.map((reason)=><p key={reason}>{reason}</p>)}</details></article>)}</div></section>
    <section className="drivers-plane"><SectionHeading title="Evidence ledger" note="Positive and negative contributions are shown with their backend explanation."/><div className="driver-columns"><div><h3>Signals supporting investment</h3>{r.positive_drivers.map((driver)=><article className="driver" key={driver.name}><div><strong>{driver.name}</strong><p>{driver.evidence}</p></div><span>+{driver.contribution.toFixed(1)}</span></article>)}</div><div><h3>Signals requiring caution</h3>{r.negative_drivers.length?r.negative_drivers.map((driver)=><article className="driver negative" key={driver.name}><div><strong>{driver.name}</strong><p>{driver.evidence}</p></div><span>−{driver.contribution.toFixed(1)}</span></article>):<p className="quiet">No material negative driver was emitted by this result.</p>}</div></div></section>
    <section><SectionHeading title="Comparable evidence" note="Similarity is contextual evidence, not proof of identical commercial performance."/><div className="comparable-table" role="table">{r.comparable_titles.map((item)=><div className="comparable-row" role="row" key={item.title}><div><strong>{item.title}</strong><p>{item.reasons.join(' · ')}</p></div><span>{Math.round(item.similarity*100)}% similar</span><span>{Math.round(item.market_signal)} signal</span></div>)}</div></section>
    <section><SectionHeading title="Source health" note="Every source carries availability, freshness, quality, provenance and warnings."/><div className="source-table">{r.source_status.map((source)=><article className="source-row" key={source.source}><div><StatusBadge status={source.status}/><strong>{label(source.source)}</strong></div><dl><div><dt>Freshness</dt><dd>{Math.round(source.freshness_score*100)}%</dd></div><div><dt>Quality</dt><dd>{Math.round(source.quality_score*100)}%</dd></div><div><dt>Mode</dt><dd>{source.provenance.mode || 'unspecified'}</dd></div></dl><p>{source.warnings.join(' ') || 'No source warning.'}</p></article>)}</div></section>
    <section className="next-actions"><div><h2>Turn the result into a decision.</h2><p>Compare controlled changes, then review the recommended launch sequence.</p></div><Link to={`/analysis/${analysisId}/scenarios`}>Open scenario lab <ArrowRight/></Link></section>
  </div>
}
