import { ArrowLeft, LoaderCircle, Save } from 'lucide-react'
import { FormEvent, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { PageHeader, SignalRail } from '../components/AppShell'
import { ErrorState, LoadingState, ScoreField, SectionHeading } from '../components/Primitives'
import type { Analysis, Scenario } from '../api/types'

export function ScenarioPage({ connected }: { connected: boolean }) {
  const { analysisId='' } = useParams()
  const [analysis,setAnalysis]=useState<Analysis|null>(null)
  const [scenarios,setScenarios]=useState<Scenario[]>([])
  const [error,setError]=useState('')
  const [saving,setSaving]=useState(false)
  const [form,setForm]=useState({name:'Regional-first multilingual launch',target_platform:'OTT',localization_mode:'multilingual_dub',marketing_budget:'medium',target_states:'Maharashtra,Tamil Nadu,Karnataka',target_languages:'Hindi,Tamil,Telugu'})
  const load=()=>Promise.all([api.getAnalysis(analysisId),api.listScenarios(analysisId)]).then(([a,s])=>{setAnalysis(a);setScenarios(s)}).catch((e)=>setError(e.message))
  useEffect(() => { void load() },[analysisId])
  const submit=async(e:FormEvent)=>{e.preventDefault();setSaving(true);setError('');try{await api.createScenario(analysisId,{...form,target_states:form.target_states.split(',').map(x=>x.trim()).filter(Boolean),target_languages:form.target_languages.split(',').map(x=>x.trim()).filter(Boolean)});await load()}catch(err){setError(err instanceof Error?err.message:'Scenario could not be saved.')}finally{setSaving(false)}}
  if(error&&!analysis)return <div className="page"><ErrorState message={error} retry={load}/></div>
  if(!analysis)return <div className="page"><LoadingState label="Opening scenario workbench"/></div>
  if(!analysis.result)return <div className="page"><ErrorState title="Complete the base analysis first" message="Scenarios require a frozen result."/></div>
  const base=analysis.result
  return <div className="page scenario-page"><PageHeader title="Scenario workbench" description="Apply controlled launch assumptions without changing the frozen base analysis." action={<Link className="button ghost" to={`/analysis/${analysisId}`}><ArrowLeft size={16}/>Decision</Link>}/><SignalRail connected={connected} label="FROZEN BASE / SAVED SCENARIOS"/>
    <div className="scenario-layout"><section><SectionHeading title="Base strategy" note="The backend-authoritative reference point."/><ScoreField score={base.market_potential_score} confidence={base.confidence_score} interval={base.confidence_interval} classification={base.decision_classification}/></section><form className="scenario-form" onSubmit={submit}><h2>Proposed strategy</h2><label>Scenario name<input value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label><div className="field-grid two"><label>Localization<select value={form.localization_mode} onChange={e=>setForm({...form,localization_mode:e.target.value})}><option value="subtitles">Subtitles</option><option value="dub">Primary-language dub</option><option value="multilingual_dub">Multilingual dub</option></select></label><label>Platform<select value={form.target_platform} onChange={e=>setForm({...form,target_platform:e.target.value})}><option>OTT</option><option>Theatrical</option><option>Television</option><option>Digital-first</option></select></label><label>Budget<select value={form.marketing_budget} onChange={e=>setForm({...form,marketing_budget:e.target.value})}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label></div><label>Target states<input value={form.target_states} onChange={e=>setForm({...form,target_states:e.target.value})}/></label><label>Target languages<input value={form.target_languages} onChange={e=>setForm({...form,target_languages:e.target.value})}/></label>{error&&<div className="form-error" role="alert">{error}</div>}<button className="button dark wide" disabled={saving}>{saving?<><LoaderCircle className="spin" size={16}/>Evaluating…</>:<><Save size={16}/>Evaluate and save</>}</button></form></div>
    <section><SectionHeading title="Saved comparisons" note="Every scenario remains attached to this analysis for review."/>{scenarios.length===0?<div className="quiet-plane">No saved scenario yet. Configure a strategy above and evaluate it.</div>:<div className="scenario-history">{scenarios.map(s=><article key={s.id}><div><span>{new Date(s.created_at).toLocaleDateString()}</span><h3>{s.name}</h3></div><div className="scenario-delta"><strong>{Math.round(s.result.scenario_score)}</strong><span>{s.result.score_delta>=0?'+':''}{s.result.score_delta.toFixed(1)} score</span></div><dl><div><dt>Confidence</dt><dd>{Math.round(s.result.scenario_confidence)}%</dd></div><div><dt>Cost</dt><dd>{s.result.cost_level}</dd></div><div><dt>Reach</dt><dd>{s.result.reach_level}</dd></div></dl><p>{s.result.recommendation.decision}</p></article>)}</div>}</section>
  </div>
}
