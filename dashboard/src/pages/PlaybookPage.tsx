import { ArrowLeft, CheckCircle2, Download, ShieldAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { PageHeader, SignalRail } from '../components/AppShell'
import { ErrorState, LoadingState, SectionHeading } from '../components/Primitives'
import type { Analysis } from '../types'

export function PlaybookPage({ connected }: { connected: boolean }){
  const{analysisId=''}=useParams();const[analysis,setAnalysis]=useState<Analysis|null>(null);const[error,setError]=useState('');const[accepted,setAccepted]=useState(false)
  const load=()=>api.getAnalysis(analysisId).then(setAnalysis).catch(e=>setError(e.message));useEffect(()=>{void load()},[analysisId])
  if(error)return <div className="page"><ErrorState message={error} retry={load}/></div>
  if(!analysis)return <div className="page"><LoadingState label="Opening launch playbook"/></div>
  if(!analysis.result)return <div className="page"><ErrorState title="No recommendation yet" message="Complete the analysis before reviewing its playbook."/></div>
  const r=analysis.result,reco=r.recommendation
  const download=()=>{const blob=new Blob([JSON.stringify({analysis_id:analysis.id,result:r},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`kizuna-playbook-${analysis.id}.json`;a.click();URL.revokeObjectURL(url)}
  return <div className="page playbook-page"><PageHeader title="Launch playbook" description="A reviewable rollout plan generated from the frozen analysis and its strongest regional signals." action={<div className="action-pair"><Link className="button ghost" to={`/analysis/${analysisId}`}><ArrowLeft size={16}/>Decision</Link><button className="button dark" onClick={download}><Download size={16}/>Export evidence</button></div>}/><SignalRail connected={connected} label={`${r.decision_classification.replaceAll('_',' ').toUpperCase()} / ${r.confidence_level.toUpperCase()} CONFIDENCE`}/>
    <section className="decision-statement"><h2>{reco.decision}</h2><p>{reco.marketing_positioning}</p></section>
    <div className="playbook-grid"><section><SectionHeading title="Release plan"/><dl className="decision-list"><div><dt>Platform</dt><dd>{reco.platform}</dd></div><div><dt>Launch window</dt><dd>{reco.launch_window}</dd></div><div><dt>Priority markets</dt><dd>{reco.priority_markets.join(' · ')}</dd></div><div><dt>Localization</dt><dd>{reco.localization.join(' · ')}</dd></div></dl></section><section><SectionHeading title="Audience"/>{reco.target_audience.map(item=><p className="ruled-item" key={item}>{item}</p>)}</section></div>
    <section><SectionHeading title="Campaign sequence" note="Actions are ordered as a controlled learning loop."/><ol className="campaign-sequence">{reco.campaign_actions.map((item,index)=><li key={item}><span>{String(index+1).padStart(2,'0')}</span><p>{item}</p></li>)}</ol></section>
    <section className="risk-plane"><SectionHeading title="Risks to validate" note="These statements travel with the recommendation and should be resolved before higher investment."/>{reco.risks.map(risk=><div key={risk}><ShieldAlert/><p>{risk}</p></div>)}</section>
    <section className={`approval-plane ${accepted?'accepted':''}`}><div>{accepted?<CheckCircle2/>:<span className="approval-mark"/>}<div><h2>{accepted?'Recommendation accepted for planning':'Human decision required'}</h2><p>{accepted?'This local approval is visible for the current session. Durable audit persistence is still a backend requirement.':'The model produces decision support. An analyst remains responsible for accepting the launch direction.'}</p></div></div><button className={`button ${accepted?'ghost':'dark'}`} onClick={()=>setAccepted(!accepted)}>{accepted?'Withdraw local approval':'Accept for planning'}</button></section>
    <footer className="version-footer"><span>Model {r.model_version}</span><span>Features {r.feature_version}</span><span>Scoring {r.scoring_version}</span></footer>
  </div>
}
