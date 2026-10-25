import { AlertTriangle, Database, MapPin, Sigma } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { PageHeader, SignalRail } from '../components/AppShell'
import { Capability, SectionHeading } from '../components/Primitives'
import { useI18n } from '../i18n'
import type { ModelCard } from '../api/types'

const components=[['Content fit','25%','Checks title details, genre and localization fit.'],['Demand momentum','25%','Tracks changes in search and information interest.'],['Regional opportunity','20%','Estimates fit across languages and target markets.'],['Engagement quality','15%','Summarizes available attention and interaction signals.'],['Comparable performance','15%','Compares the title with similar reference works.']]
const sourceNames:Record<string,string>={google_trends:'Google Trends',youtube:'YouTube',wikimedia:'Wikimedia',anilist:'AniList',regional_context:'Regional Context'}
const sourceDescriptions:Record<string,string>={google_trends:'Search interest over time, used as a trend signal.',youtube:'Public video attention, not total platform viewership.',wikimedia:'Page activity used as an information interest proxy.',anilist:'Anime metadata, tags and community affinity.',regional_context:'Language coverage and state market context.'}

function SourceLogo({source}:{source:string}){
  if(source==='youtube')return <span className="source-logo youtube-logo" aria-hidden="true"><svg viewBox="0 0 48 36"><rect x="2" y="2" width="44" height="32" rx="10"/><path d="m20 11 12 7-12 7z"/></svg></span>
  if(source==='google_trends')return <span className="source-logo trends-logo" aria-hidden="true"><span>G</span><svg viewBox="0 0 48 30"><path d="M3 25 15 16l9 5L40 5"/><path d="M32 5h8v8"/></svg></span>
  if(source==='wikimedia')return <span className="source-logo wikimedia-logo" aria-hidden="true"><svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="19"/><path d="M5 24h38M24 5c7 6 10 12 10 19S31 37 24 43M24 5c-7 6-10 12-10 19s3 13 10 19"/></svg></span>
  if(source==='anilist')return <span className="source-logo anilist-logo" aria-hidden="true">A</span>
  return <span className="source-logo regional-logo" aria-hidden="true"><MapPin size={29} strokeWidth={2}/><i>IN</i></span>
}

export function MethodologyPage({connected}:{connected:boolean}){
  const { t, lang } = useI18n()
  const[health,setHealth]=useState<{mode:string;sources:{source:string;status:string}[];policy:string}|null>(null)
  const[model,setModel]=useState<ModelCard|null>(null)
  useEffect(()=>{api.sourceHealth().then(setHealth).catch(()=>setHealth(null));api.modelCard().then(setModel).catch(()=>setModel(null))},[])
  const sources=health?.sources||[{source:'anilist',status:'unconfigured'},{source:'google_trends',status:'unconfigured'},{source:'youtube',status:'unconfigured'},{source:'wikimedia',status:'unconfigured'},{source:'regional_context',status:'unconfigured'}]
  return <div className="page methodology-page">
    <PageHeader title="Methodology and system truth" description="How Kizuna turns inputs into a decision, and what the current build can honestly claim."/>
    <SignalRail connected={connected} label={health?.mode ? (lang === 'ja' ? t(health.mode) : health.mode.toUpperCase()) : 'SOURCE HEALTH UNAVAILABLE'}/>
    <section className="method-hero"><div><Sigma/><h2>{t('Opportunity and confidence are separate.')}</h2></div><p>{t('The market-potential score compares launch opportunity. Confidence describes evidence coverage, freshness, quality and comparable strength. Neither guarantees revenue, viewership or prediction accuracy.')}</p></section>
    <section><SectionHeading title="Current scoring contract" note={model?t('Trained model {version}. Displayed weights are nominal; only components with evidence that pass held-out validation contribute to a title score.',{version:model.model_version}):'The trained model is unavailable. New analyses will disclose use of the deterministic fallback.'}/><div className="formula"><span>{t('Market potential')}</span>{components.map(([name,weight])=><div key={name}><strong>{weight}</strong><p>{t(name)}</p></div>)}</div><div className="method-rows">{components.map(([name,weight,detail])=><article key={name}><strong>{t(name)}</strong><span>{weight}</span><p>{t(detail)}</p></article>)}</div></section>
    <section><SectionHeading title="Capability status" note="A quick view of what is connected and what remains unavailable."/><div className="capability-list"><Capability good={connected} title={t('Analysis service')} detail={connected?t('Serves and persists the complete dashboard analysis flow.'):t('Not reachable from this browser.')}/><Capability good={Boolean(model)} title={t('Trained model')} detail={model?t('{titles} labelled titles across {states} states. Loaded as {version}.',{titles:model.n_labelled_titles,states:model.n_states,version:model.model_version}):t('No deployable model artifact is currently loaded.')}/><Capability good={Boolean(model?.success_model)} title={t('Outcome calibration')} detail={model?.success_model?t('The success score uses held-out content and comparable validation, then ranks against the reference title set.'):t('The outcome-calibration model is unavailable.')}/><Capability good={Boolean(health)} title={t('Source adapter')} detail={t('Unavailable sources lower confidence and never create evidence.')}/></div></section>
    <section><SectionHeading title="Planned evidence sources" note="Source coverage is shown separately from provider mode and result provenance."/><div className="dataset-grid">{sources.map(source=>{const status=source.status.toLowerCase();const unavailable=status==='unavailable'||status==='unconfigured';return <article key={source.source}><SourceLogo source={source.source}/><strong>{sourceNames[source.source]||source.source.replaceAll('_',' ')}</strong><span className={`source-status ${unavailable?'is-unavailable':''}`}><i/>{t(source.status.replaceAll('_',' '))}</span><p>{t(sourceDescriptions[source.source]||'Regional signals for launch planning.')}</p></article>})}</div></section>
    <section className="governance-plane"><Database/><div><h2>{t('Production data requirements')}</h2><p>{t('Store raw responses, collection times, geography, licensing, retries and provenance before using live evidence to validate model claims.')}</p></div></section>
  </div>
}
