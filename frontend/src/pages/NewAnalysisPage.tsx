import { ArrowLeft, Check, LoaderCircle, SearchCheck, Sparkles } from 'lucide-react'
import { FormEvent, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { PageHeader, SignalRail } from '../components/AppShell'
import { buildSeoSuggestion } from '../lib/seo'

const genres = ['Action','Adventure','Comedy','Drama','Fantasy','Horror','Mystery','Psychological','Romance','Sci-Fi','Slice of Life','Sports','Supernatural']
const states = ['Maharashtra','Karnataka','Delhi NCR','Tamil Nadu','Telangana','West Bengal','Kerala','Uttar Pradesh']
const languages = ['Hindi','Tamil','Telugu','Kannada','Bengali','Malayalam','English']

function upcomingReleaseQuarters() {
  const now = new Date()
  let year = now.getFullYear()
  let quarter = Math.floor(now.getMonth() / 3) + 2
  if (quarter > 4) { year += 1; quarter = 1 }
  return Array.from({ length: 24 }, (_, index) => {
    const offset = quarter - 1 + index
    const optionYear = year + Math.floor(offset / 4)
    const optionQuarter = (offset % 4) + 1
    return { year: optionYear, quarter: optionQuarter, value: `Q${optionQuarter} ${optionYear}` }
  })
}

export function NewAnalysisPage({ connected }: { connected: boolean }) {
  const navigate = useNavigate()
  const mounted = useRef(true)
  const releaseDialog = useRef<HTMLDialogElement>(null)
  const releasePeriods = useMemo(upcomingReleaseQuarters, [])
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])
  const [form, setForm] = useState({ name:'', english_title:'', synopsis:'', content_format:'series', primary_genre:'Fantasy', source_material:'Original', expected_release_period:releasePeriods[0]?.value ?? '', target_platform:'OTT', marketing_budget:'medium', studio:'', director:'', episode_count:'', age_rating:'', target_audience:'', franchise_status:'New IP', trailer_url:'', themes:'identity, friendship', target_languages:['Hindi'], target_states:['Maharashtra'] })
  const [status, setStatus] = useState<'idle'|'submitting'|'running'|'failed'>('idle')
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('Ready for intake')
  const [error, setError] = useState('')
  const seo = useMemo(() => buildSeoSuggestion(form.name, form.synopsis, form.primary_genre, form.themes.split(',').map((x) => x.trim()).filter(Boolean)), [form])
  const update = (key: string, value: unknown) => setForm((current) => ({ ...current, [key]: value }))
  const toggle = (key: 'target_languages'|'target_states', value: string) => update(key, form[key].includes(value) ? form[key].filter((item) => item !== value) : [...form[key], value])
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError(''); setStatus('submitting')
    try {
      const projects = await api.listProjects()
      const project = projects[0] || await api.createProject({ name: 'Kizuna Launch Portfolio', description: 'Titles assessed through the dedicated Kizuna Signal website.' })
      const title = await api.createTitle(project.id, {
        ...form, genres: [], themes: form.themes.split(',').map((x) => x.trim()).filter(Boolean),
        studio: form.studio || null, director: form.director || null, episode_count: form.episode_count ? Number(form.episode_count) : null, age_rating: form.age_rating || null, target_audience: form.target_audience || null, franchise_status: form.franchise_status || null, trailer_url: form.trailer_url || null,
        metadata_extra: { seo_preflight: seo },
      })
      const started = await api.startAnalysis(title.id)
      if (!mounted.current) return
      setStatus('running')
      const poll = async (): Promise<void> => {
        let delay = 900
        while (mounted.current) {
          const job = await api.getJob(started.job_id)
          if (!mounted.current) return
          setProgress(job.progress); setStage(job.stage)
          if (job.status === 'completed' || job.status === 'partially_completed') { navigate(`/analysis/${started.analysis_id}`); return }
          if (job.status === 'failed') throw new Error(job.error_message || 'The analysis failed.')
          await new Promise((resolve) => window.setTimeout(resolve, delay))
          delay = Math.min(Math.round(delay * 1.35), 3_000)
        }
      }
      await poll()
    } catch (e) { if (mounted.current) { setError(e instanceof Error ? e.message : 'Analysis could not be started.'); setStatus('failed') } }
  }
  return <div className="page intake-page">
    <PageHeader title="Analyse a new title" description="Create a frozen pre-release evidence snapshot, then compare launch strategies." action={<Link className="button ghost" to="/"><ArrowLeft size={16}/> Portfolio</Link>} />
    <SignalRail connected={connected} label={status === 'running' ? stage.toUpperCase() : 'TITLE INTAKE'} />
    {status === 'running' ? <section className="running-plane" aria-live="polite"><div className="job-orbit"><span style={{'--progress': `${progress}%`} as CSSProperties} /><strong>{progress}%</strong></div><div><h2>Building the evidence snapshot</h2><p>{stage}</p><div className="progress-track" role="progressbar" aria-label="Analysis progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><span style={{transform:`scaleX(${progress / 100})`}} /></div><small>Keep this page open. The backend is preserving every completed stage.</small></div></section> : <form onSubmit={submit} className="intake-layout">
      <div className="form-plane">
        <div className="form-section"><h2>Title and story</h2><div className="field-grid two"><label>Original title<input required minLength={1} value={form.name} onChange={(e)=>update('name',e.target.value)} placeholder="Project Hikari" /></label><label>English title<input value={form.english_title} onChange={(e)=>update('english_title',e.target.value)} placeholder="Optional" /></label></div><label>Synopsis<textarea required minLength={40} value={form.synopsis} onChange={(e)=>update('synopsis',e.target.value)} placeholder="Describe the premise, stakes and emotional hook in at least 40 characters." /></label><div className="field-grid three"><label>Format<select value={form.content_format} onChange={(e)=>update('content_format',e.target.value)}><option value="series">Series</option><option value="film">Film</option><option value="special">Special</option></select></label><label>Primary genre<select value={form.primary_genre} onChange={(e)=>update('primary_genre',e.target.value)}>{genres.map((g)=><option key={g}>{g}</option>)}</select></label><label>Source material<select value={form.source_material} onChange={(e)=>update('source_material',e.target.value)}><option>Original</option><option>Manga</option><option>Novel</option><option>Game</option><option>Existing franchise</option></select></label></div><label>Themes<input value={form.themes} onChange={(e)=>update('themes',e.target.value)} placeholder="identity, friendship, belonging" /></label></div>
        <div className="form-section"><h2>India launch assumptions</h2><div className="field-grid three"><label>Release period<button className="release-period-trigger" type="button" aria-haspopup="dialog" onClick={()=>releaseDialog.current?.showModal()}>{form.expected_release_period}<span aria-hidden="true">▾</span></button></label><label>Platform<select value={form.target_platform} onChange={(e)=>update('target_platform',e.target.value)}><option>OTT</option><option>Theatrical</option><option>Television</option><option>Digital-first</option><option>Undecided</option></select></label><label>Marketing budget<select value={form.marketing_budget} onChange={(e)=>update('marketing_budget',e.target.value)}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label></div><fieldset><legend>Target languages</legend><div className="choice-grid">{languages.map((item)=><label className={form.target_languages.includes(item)?'selected':''} key={item}><input type="checkbox" checked={form.target_languages.includes(item)} onChange={()=>toggle('target_languages',item)}/><span className="choice-checkbox" aria-hidden="true"><Check size={11}/></span><span>{item}</span></label>)}</div></fieldset><fieldset><legend>Priority states</legend><div className="choice-grid">{states.map((item)=><label className={form.target_states.includes(item)?'selected':''} key={item}><input type="checkbox" checked={form.target_states.includes(item)} onChange={()=>toggle('target_states',item)}/><span className="choice-checkbox" aria-hidden="true"><Check size={11}/></span><span>{item}</span></label>)}</div></fieldset>
          <dialog className="release-dialog" ref={releaseDialog} aria-labelledby="release-dialog-title"><div className="release-dialog-head"><div><span className="eyebrow">PLANNING WINDOW</span><h3 id="release-dialog-title">Choose a release quarter</h3><p>Select from the next six years of quarterly windows.</p></div><button className="release-dialog-close" type="button" aria-label="Close release period picker" onClick={()=>releaseDialog.current?.close()}>×</button></div><div className="release-years">{Array.from(new Set(releasePeriods.map((period)=>period.year))).map((year)=><section className="release-year" key={year}><h4>{year}</h4><div className="release-quarter-grid">{releasePeriods.filter((period)=>period.year===year).map((period)=><button type="button" className={form.expected_release_period===period.value?'selected':''} key={period.value} aria-pressed={form.expected_release_period===period.value} onClick={()=>{update('expected_release_period',period.value);releaseDialog.current?.close()}}>Q{period.quarter}</button>)}</div></section>)}</div></dialog>
        </div>
        <div className="form-section"><h2>Production context</h2><div className="field-grid two"><label>Studio<input value={form.studio} onChange={(e)=>update('studio',e.target.value)} placeholder="Optional" /></label><label>Franchise status<select value={form.franchise_status} onChange={(e)=>update('franchise_status',e.target.value)}><option>New IP</option><option>Manga adaptation</option><option>Sequel or spin-off</option><option>Existing franchise</option></select></label></div><div className="field-grid two"><label>Director<input value={form.director} onChange={(e)=>update('director',e.target.value)} placeholder="Optional" /></label><label>Episodes or runtime units<input type="number" min={1} max={2000} value={form.episode_count} onChange={(e)=>update('episode_count',e.target.value)} placeholder="e.g. 12" /></label></div><div className="field-grid two"><label>Age rating<select value={form.age_rating} onChange={(e)=>update('age_rating',e.target.value)}><option value="">Not set</option><option value="all_ages">All ages</option><option value="7_plus">7+</option><option value="13_plus">13+</option><option value="16_plus">16+</option><option value="18_plus">18+</option></select></label><label>Target audience<select value={form.target_audience} onChange={(e)=>update('target_audience',e.target.value)}><option value="">Not set</option><option>Kids</option><option>Teens</option><option>Young adults</option><option>Adults</option><option>Family</option></select></label></div><label>Trailer URL<input type="url" value={form.trailer_url} onChange={(e)=>update('trailer_url',e.target.value)} placeholder="https://youtube.com/watch?v=…" /></label></div>
      </div>
      <aside className="intake-aside"><div className="seo-sheet"><div className="aside-title"><SearchCheck/><h2>SEO preflight</h2></div><p>This deterministic preflight is saved as metadata. Review the title and synopsis before publishing.</p><dl><div><dt>Meta title</dt><dd>{seo.metaTitle}</dd></div><div><dt>Description</dt><dd>{form.synopsis || 'The synopsis preview will appear here.'}</dd></div><div><dt>Slug</dt><dd>/{seo.slug || 'title-slug'}</dd></div><div><dt>Keywords</dt><dd>{seo.keywords.join(' · ')}</dd></div></dl></div>{error&&<div className="form-error" role="alert">{error}</div>}<button className="button dark wide" disabled={!connected||status==='submitting'}>{status==='submitting'?<><LoaderCircle className="spin" size={16}/>Preparing…</>:<><Sparkles size={16}/>Run market analysis</>}</button><p className="submission-note">Submitting creates a persistent title, analysis job and versioned result snapshot.</p></aside>
    </form>}
  </div>
}
