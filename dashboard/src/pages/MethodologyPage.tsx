import { Database, MapPin, Sigma } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { PageHeader, SignalRail } from '../components/AppShell'
import { Capability, SectionHeading, Stat } from '../components/Primitives'
import type { ModelCard } from '../types'

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

const heat=(value:number)=>`color-mix(in srgb, var(--green) ${Math.round(Math.max(0,Math.min(1,(value-60)/30))*70)}%, var(--panel))`
const genreLabel=(value:string)=>value.replaceAll('_',' ')
const count=(value:number)=>new Intl.NumberFormat('en-IN').format(value)

function ModelSection({card}:{card:ModelCard}){
  if(!card.active||!card.dataset||!card.metrics||!card.conformal)return null
  const{dataset,metrics}=card
  const states=Object.keys(dataset.state_genre_profile)
  const genres=Object.keys(dataset.state_genre_profile[states[0]])
  return <section><SectionHeading title="Census-weighted regional model" note="Trained on a synthetic dataset built from Census 2011 state weights. Its fit scores describe the simulator, not real-world accuracy."/>
    <div className="stats-grid"><Stat value={count(dataset.rows)} label="Synthetic training rows"/><Stat value={metrics.holdout_r2.toFixed(2)} suffix={`/ ${metrics.r2_ceiling.toFixed(2)} ceiling`} label="Holdout R²"/><Stat value={metrics.holdout_mae.toFixed(1)} suffix="pts" label="Holdout mean error"/><Stat value={`±${card.conformal.q80.toFixed(1)}`} label="80% interval"/></div>
    <p className="model-note">Real-data check: across {metrics.real_data_check.titles} labelled released titles, the model's national view correlates {metrics.real_data_check.spearman.toFixed(2)} (rank) with recorded India performance. That is a weak signal on a small sample. {dataset.census_note} Top states ({dataset.top_states.join(', ')}) carry a ×{dataset.top_state_affinity_inflation} genre-affinity inflation.</p>
    <div className="heat-wrap"><table className="heat-table"><caption>Mean modelled demand by state and genre</caption><thead><tr><th>State</th>{genres.map(g=><th key={g}>{genreLabel(g)}</th>)}</tr></thead><tbody>{states.map(s=><tr key={s}><th>{s}</th>{genres.map(g=>{const cell=dataset.state_genre_profile[s][g];return <td key={g} style={{background:heat(cell.mean_demand)}} title={`${count(cell.rows)} rows`}>{Math.round(cell.mean_demand)}</td>})}</tr>)}</tbody></table></div>
  </section>
}

export function MethodologyPage({connected}:{connected:boolean}){
  const[card,setCard]=useState<ModelCard|null>(null)
  useEffect(()=>{api.modelCard().then(setCard).catch(()=>setCard(null))},[])
  const[health,setHealth]=useState<{mode:string;sources:{source:string;status:string}[];policy:string}|null>(null)
  useEffect(()=>{api.sourceHealth().then(setHealth).catch(()=>setHealth(null))},[])
  const sources=health?.sources||[{source:'anilist',status:'unconfigured'},{source:'google_trends',status:'unconfigured'},{source:'youtube',status:'unconfigured'},{source:'wikimedia',status:'unconfigured'},{source:'regional_context',status:'unconfigured'}]
  return <div className="page methodology-page">
    <PageHeader title="Methodology and system truth" description="How Kizuna turns inputs into a decision, and what the current build can honestly claim."/>
    <SignalRail connected={connected} label={health?.mode?.toUpperCase()||'SOURCE HEALTH UNAVAILABLE'}/>
    <section className="method-hero"><div><Sigma/><h2>Opportunity and confidence are separate.</h2></div><p>The market-potential score compares launch opportunity. Confidence describes evidence coverage, freshness, quality and comparable strength. Neither guarantees revenue, viewership or prediction accuracy.</p></section>
    <section><SectionHeading title="Current scoring contract" note="Five weighted components, bounded and versioned by the backend. State scores blend in the regional model."/><div className="formula"><span>Market potential</span>{components.map(([name,weight])=><div key={name}><strong>{weight}</strong><p>{name}</p></div>)}</div><div className="method-rows">{components.map(([name,weight,detail])=><article key={name}><strong>{name}</strong><span>{weight}</span><p>{detail}</p></article>)}</div></section>
    <section><SectionHeading title="Capability status" note="A quick view of what is connected and what remains unavailable."/><div className="capability-list"><Capability good={connected} title="Analysis service" detail={connected?'Serves the dashboard analysis API.':'Not reachable from this browser.'}/><Capability good={Boolean(card?.active)} title="Regional demand model" detail={card?.active?`${card.model_version} sets each state's baseline from a ${count(card.dataset?.rows||0)}-row synthetic dataset, then real Google Trends state interest adjusts it.`:'Not available. State scores fall back to fixed regional baselines.'}/><Capability good={false} title="Accuracy calibration" detail="Scores combine live public signals; no real launch-outcome dataset exists yet to validate their predictive accuracy."/><Capability good={Boolean(health)} title="Source adapter" detail="Live public APIs when enabled; unavailable sources lower confidence and never create evidence."/></div></section>
    {card&&<ModelSection card={card}/>}
    <section><SectionHeading title="Evidence sources" note="Source coverage is shown separately from provider mode and result provenance."/><div className="dataset-grid">{sources.map(source=>{const status=source.status.toLowerCase();const unavailable=status==='unavailable'||status==='unconfigured';return <article key={source.source}><SourceLogo source={source.source}/><strong>{sourceNames[source.source]||source.source.replaceAll('_',' ')}</strong><span className={`source-status ${unavailable?'is-unavailable':''}`}><i/>{source.status.replaceAll('_',' ')}</span><p>{sourceDescriptions[source.source]||'Regional signals for launch planning.'}</p></article>})}</div></section>
    <section className="governance-plane"><Database/><div><h2>Production data requirements</h2><p>Store raw responses, collection times, geography, licensing, retries and provenance before using live evidence to validate model claims.</p></div></section>
  </div>
}
