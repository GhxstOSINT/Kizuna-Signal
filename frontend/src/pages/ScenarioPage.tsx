import { ArrowLeft, LoaderCircle, Save } from 'lucide-react'
import { FormEvent, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { PageHeader, SignalRail } from '../components/AppShell'
import { ErrorState, LoadingState, ScoreField, SectionHeading } from '../components/Primitives'
import { Select } from '../components/Select'
import { fromJapanese, splitList, useI18n } from '../i18n'
import type { Analysis, Scenario } from '../api/types'

const scenarioPlatforms = ['OTT', 'Theatrical', 'Television', 'Digital-first']
const localizationModes = [{ value: 'subtitles', label: 'Subtitles' }, { value: 'dub', label: 'Primary-language dub' }, { value: 'multilingual_dub', label: 'Multilingual dub' }]
const budgets = [{ value: 'low', label: 'Low' }, { value: 'medium', label: 'Medium' }, { value: 'high', label: 'High' }]

export function ScenarioPage({ connected }: { connected: boolean }) {
  const { t, lang } = useI18n()
  const { analysisId='' } = useParams()
  const [analysis,setAnalysis]=useState<Analysis|null>(null)
  const [scenarios,setScenarios]=useState<Scenario[]>([])
  const [error,setError]=useState('')
  const [saving,setSaving]=useState(false)
  const [form,setForm]=useState({target_platform:'OTT',localization_mode:'multilingual_dub',marketing_budget:'medium'})
  // The three text boxes start with an example in the interface language until they are edited.
  const [edited,setEdited]=useState<Record<string,string>>({})
  const example={name:t('Regional-first multilingual launch'),states:['Maharashtra','Tamil Nadu','Karnataka'].map(x=>t(x)).join(lang==='ja'?'、':', '),languages:['Hindi','Tamil','Telugu'].map(x=>t(x)).join(lang==='ja'?'、':', ')}
  const text={name:edited.name??example.name,states:edited.states??example.states,languages:edited.languages??example.languages}
  const toEnglish=(value:string)=>splitList(value).map(x=>fromJapanese(x)??x)
  const load=()=>Promise.all([api.getAnalysis(analysisId),api.listScenarios(analysisId)]).then(([a,s])=>{setAnalysis(a);setScenarios(s)}).catch((e)=>setError(e.message))
  useEffect(() => { void load() },[analysisId])
  const submit=async(e:FormEvent)=>{e.preventDefault();setSaving(true);setError('');try{await api.createScenario(analysisId,{...form,name:text.name,target_states:toEnglish(text.states),target_languages:toEnglish(text.languages)});await load()}catch(err){setError(err instanceof Error?err.message:'Scenario could not be saved.')}finally{setSaving(false)}}
  if(error&&!analysis)return <div className="page"><ErrorState message={error} retry={load}/></div>
  if(!analysis)return <div className="page"><LoadingState label="Opening scenario workbench"/></div>
  if(!analysis.result)return <div className="page"><ErrorState title="Complete the base analysis first" message="Scenarios require a frozen result."/></div>
  const base=analysis.result
  return <div className="page scenario-page"><PageHeader title="Scenario workbench" description="Apply controlled launch assumptions without changing the frozen base analysis." action={<Link className="button ghost" to={`/analysis/${analysisId}`}><ArrowLeft size={16}/>{t('Decision')}</Link>}/><SignalRail connected={connected} label="FROZEN BASE / SAVED SCENARIOS"/>
    <div className="scenario-layout"><section><SectionHeading title="Base strategy" note="The backend-authoritative reference point."/><ScoreField score={base.market_potential_score} confidence={base.confidence_score} interval={base.confidence_interval} classification={base.decision_classification}/></section><form className="scenario-form" onSubmit={submit}><h2>{t('Proposed strategy')}</h2><label>{t('Scenario name')}<input value={text.name} onChange={e=>setEdited({...edited,name:e.target.value})}/></label><div className="field-grid two"><label>{t('Localization')}<Select ariaLabel="Localization" value={form.localization_mode} onChange={(v)=>setForm({...form,localization_mode:v})} options={localizationModes} /></label><label>{t('Platform')}<Select ariaLabel="Platform" value={form.target_platform} onChange={(v)=>setForm({...form,target_platform:v})} options={scenarioPlatforms} /></label><label>{t('Budget')}<Select ariaLabel="Budget" value={form.marketing_budget} onChange={(v)=>setForm({...form,marketing_budget:v})} options={budgets} /></label></div><label>{t('Target states')}<input value={text.states} onChange={e=>setEdited({...edited,states:e.target.value})}/></label><label>{t('Target languages')}<input value={text.languages} onChange={e=>setEdited({...edited,languages:e.target.value})}/></label>{error&&<div className="form-error" role="alert">{t(error)}</div>}<button className="button dark wide" disabled={saving}>{saving?<><LoaderCircle className="spin" size={16}/>{t('Evaluating…')}</>:<><Save size={16}/>{t('Evaluate and save')}</>}</button></form></div>
    <section><SectionHeading title="Saved comparisons" note="Every scenario remains attached to this analysis for review."/>{scenarios.length===0?<div className="quiet-plane">{t('No saved scenario yet. Configure a strategy above and evaluate it.')}</div>:<div className="scenario-history">{scenarios.map(s=><article key={s.id}><div><span>{new Date(s.created_at).toLocaleDateString(lang==='ja'?'ja-JP':undefined)}</span><h3>{s.name}</h3></div><div className="scenario-delta"><strong>{Math.round(s.result.scenario_score)}</strong><span>{t('{delta} score', { delta: `${s.result.score_delta>=0?'+':''}${s.result.score_delta.toFixed(1)}` })}</span></div><dl><div><dt>{t('Confidence')}</dt><dd>{Math.round(s.result.scenario_confidence)}%</dd></div><div><dt>{t('Cost')}</dt><dd>{t(s.result.cost_level)}</dd></div><div><dt>{t('Reach')}</dt><dd>{t(s.result.reach_level)}</dd></div></dl><p>{t(s.result.recommendation.decision)}</p></article>)}</div>}</section>
  </div>
}
