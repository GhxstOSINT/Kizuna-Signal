import { ArrowLeft, LoaderCircle, Save } from 'lucide-react'
import { FormEvent, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { PageHeader, SignalRail } from '../components/AppShell'
import { ErrorState, LoadingState, ScoreField, SectionHeading } from '../components/Primitives'
import { useI18n } from '../i18n'
import type { Analysis, Scenario } from '../api/types'

const scenarioPlatforms = ['OTT', 'Theatrical', 'Television', 'Digital-first']

export function ScenarioPage({ connected }: { connected: boolean }) {
  const { t, lang } = useI18n()
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
  return <div className="page scenario-page"><PageHeader title="Scenario workbench" description="Apply controlled launch assumptions without changing the frozen base analysis." action={<Link className="button ghost" to={`/analysis/${analysisId}`}><ArrowLeft size={16}/>{t('Decision')}</Link>}/><SignalRail connected={connected} label="FROZEN BASE / SAVED SCENARIOS"/>
    <div className="scenario-layout"><section><SectionHeading title="Base strategy" note="The backend-authoritative reference point."/><ScoreField score={base.market_potential_score} confidence={base.confidence_score} interval={base.confidence_interval} classification={base.decision_classification}/></section><form className="scenario-form" onSubmit={submit}><h2>{t('Proposed strategy')}</h2><label>{t('Scenario name')}<input value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label><div className="field-grid two"><label>{t('Localization')}<select value={form.localization_mode} onChange={e=>setForm({...form,localization_mode:e.target.value})}><option value="subtitles">{t('Subtitles')}</option><option value="dub">{t('Primary-language dub')}</option><option value="multilingual_dub">{t('Multilingual dub')}</option></select></label><label>{t('Platform')}<select value={form.target_platform} onChange={e=>setForm({...form,target_platform:e.target.value})}>{scenarioPlatforms.map(p=><option key={p} value={p}>{t(p)}</option>)}</select></label><label>{t('Budget')}<select value={form.marketing_budget} onChange={e=>setForm({...form,marketing_budget:e.target.value})}><option value="low">{t('Low')}</option><option value="medium">{t('Medium')}</option><option value="high">{t('High')}</option></select></label></div><label>{t('Target states')}<input value={form.target_states} onChange={e=>setForm({...form,target_states:e.target.value})}/></label><label>{t('Target languages')}<input value={form.target_languages} onChange={e=>setForm({...form,target_languages:e.target.value})}/></label>{error&&<div className="form-error" role="alert">{t(error)}</div>}<button className="button dark wide" disabled={saving}>{saving?<><LoaderCircle className="spin" size={16}/>{t('Evaluating…')}</>:<><Save size={16}/>{t('Evaluate and save')}</>}</button></form></div>
    <section><SectionHeading title="Saved comparisons" note="Every scenario remains attached to this analysis for review."/>{scenarios.length===0?<div className="quiet-plane">{t('No saved scenario yet. Configure a strategy above and evaluate it.')}</div>:<div className="scenario-history">{scenarios.map(s=><article key={s.id}><div><span>{new Date(s.created_at).toLocaleDateString(lang==='ja'?'ja-JP':undefined)}</span><h3>{s.name}</h3></div><div className="scenario-delta"><strong>{Math.round(s.result.scenario_score)}</strong><span>{t('{delta} score', { delta: `${s.result.score_delta>=0?'+':''}${s.result.score_delta.toFixed(1)}` })}</span></div><dl><div><dt>{t('Confidence')}</dt><dd>{Math.round(s.result.scenario_confidence)}%</dd></div><div><dt>{t('Cost')}</dt><dd>{t(s.result.cost_level)}</dd></div><div><dt>{t('Reach')}</dt><dd>{t(s.result.reach_level)}</dd></div></dl><p>{s.result.recommendation.decision}</p></article>)}</div>}</section>
  </div>
}
