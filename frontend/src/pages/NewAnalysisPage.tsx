import { ArrowLeft, Check, LoaderCircle, SearchCheck, Sparkles } from 'lucide-react'
import { FormEvent, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { PageHeader, SignalRail } from '../components/AppShell'
import { Select } from '../components/Select'
import { FoxMark } from '../components/FoxMark'
import { fromJapanese, splitList, useI18n } from '../i18n'
import { useFormValidity } from '../i18n/forms'
import { contentFormats } from '../lib/formats'
import { buildSeoSuggestion } from '../lib/seo'

const genres = ['Action','Adventure','Comedy','Drama','Fantasy','Horror','Mystery','Psychological','Romance','Sci-Fi','Slice of Life','Sports','Supernatural']
const states = ['Maharashtra','Karnataka','Delhi NCR','Tamil Nadu','Telangana','West Bengal','Kerala','Uttar Pradesh']
const languages = ['Hindi','Tamil','Telugu','Kannada','Bengali','Malayalam','English']
const sources = ['Original','Manga','Novel','Game','Existing franchise']
const platforms = ['OTT','Theatrical','Television','Digital-first','Undecided']
const franchises = ['New IP','Manga adaptation','Sequel or spin-off','Existing franchise']
const audiences = ['Kids','Teens','Young adults','Adults','Family']
const ageRatings: [string, string][] = [['all_ages', 'All ages'], ['7_plus', '7+'], ['13_plus', '13+'], ['16_plus', '16+'], ['18_plus', '18+']]
const budgets = [{ value: 'low', label: 'Low' }, { value: 'medium', label: 'Medium' }, { value: 'high', label: 'High' }]
const ageOptions = [{ value: '', label: 'Not set' }, ...ageRatings.map(([value, label]) => ({ value, label }))]
const audienceOptions = [{ value: '', label: 'Not set' }, ...audiences]

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
  const { t, lang } = useI18n()
  const navigate = useNavigate()
  const mounted = useRef(true)
  const releaseDialog = useRef<HTMLDialogElement>(null)
  const releasePeriods = useMemo(upcomingReleaseQuarters, [])
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])
  const [form, setForm] = useState({ name:'', english_title:'', synopsis:'', content_format:'anime_series', primary_genre:'Fantasy', source_material:'Original', expected_release_period:releasePeriods[0]?.value ?? '', target_platform:'OTT', marketing_budget:'medium', studio:'', director:'', episode_count:'', age_rating:'', target_audience:'', franchise_status:'New IP', trailer_url:'', themes:'identity, friendship', target_languages:['Hindi'], target_states:['Maharashtra'] })
  const [status, setStatus] = useState<'idle'|'submitting'|'running'|'failed'>('idle')
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('Ready for intake')
  const [error, setError] = useState('')
  const [themesEdited, setThemesEdited] = useState<string | null>(null)
  const themesText = themesEdited ?? (lang === 'ja' ? 'アイデンティティ、友情' : 'identity, friendship')
  // Themes are matched against English tags, so Japanese words are sent as their English keys.
  const parseThemes = (text: string) => splitList(text).map((token) => /[ぁ-んァ-ヶ一-龠]/.test(token) ? (fromJapanese(token) ?? token).toLowerCase() : token)
  const validity = useFormValidity()
  const seo = useMemo(() => buildSeoSuggestion(form.name, form.synopsis, form.primary_genre, splitList(themesText), lang), [form, themesText, lang])
  const update = (key: string, value: unknown) => setForm((current) => ({ ...current, [key]: value }))
  const toggle = (key: 'target_languages'|'target_states', value: string) => update(key, form[key].includes(value) ? form[key].filter((item) => item !== value) : [...form[key], value])
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError(''); setStatus('submitting')
    try {
      const projects = await api.listProjects()
      const project = projects[0] || await api.createProject({ name: t('Kizuna Launch Portfolio'), description: t('Titles assessed through the dedicated Kizuna Signal website.') })
      const title = await api.createTitle(project.id, {
        ...form, genres: [], themes: parseThemes(themesText),
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
    <PageHeader title="Analyse a new title" description="Create a frozen pre-release evidence snapshot, then compare launch strategies." action={<Link className="button ghost" to="/"><ArrowLeft size={16}/> {t('Portfolio')}</Link>} />
    <SignalRail connected={connected} label={status === 'running' ? (lang === 'ja' || stage === 'Ready for intake' ? t(stage) : stage.toUpperCase()) : 'TITLE INTAKE'} />
    {status === 'running' ? <section className="running-plane" aria-live="polite"><div className="job-orbit"><span style={{'--progress': `${progress}%`} as CSSProperties} /><strong>{progress}%</strong></div><div><FoxMark className="fox-mark-pulse run-fox" size={44} /><h2>{t('Building the evidence snapshot')}</h2><p>{t(stage)}</p><div className="progress-track" role="progressbar" aria-label={t('Analysis progress')} aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><span style={{transform:`scaleX(${progress / 100})`}} /></div><small>{t('Keep this page open. The backend is preserving every completed stage.')}</small></div></section> : <form onSubmit={submit} className="intake-layout" {...validity}>
      <div className="form-plane">
        <div className="form-section"><h2>{t('Title and story')}</h2><div className="field-grid two"><label>{t('Original title')}<input required minLength={1} value={form.name} onChange={(e)=>update('name',e.target.value)} placeholder={t('Project Hikari')} /></label><label>{t('English title')}<input value={form.english_title} onChange={(e)=>update('english_title',e.target.value)} placeholder={t('Optional')} /></label></div><label>{t('Synopsis')}<textarea required minLength={40} value={form.synopsis} onChange={(e)=>update('synopsis',e.target.value)} placeholder={t('Describe the premise, stakes and emotional hook in at least 40 characters.')} /></label><div className="field-grid three"><label>{t('Content format')}<Select ariaLabel="Content format" value={form.content_format} onChange={(v)=>update('content_format',v)} options={contentFormats} /></label><label>{t('Primary genre')}<Select ariaLabel="Primary genre" value={form.primary_genre} onChange={(v)=>update('primary_genre',v)} options={genres} /></label><label>{t('Source material')}<Select ariaLabel="Source material" value={form.source_material} onChange={(v)=>update('source_material',v)} options={sources} /></label></div><label>{t('Themes')}<input value={themesText} onChange={(e)=>setThemesEdited(e.target.value)} placeholder={t('identity, friendship, belonging')} /></label></div>
        <div className="form-section"><h2>{t('India launch assumptions')}</h2><div className="field-grid three"><label>{t('Release period')}<button className="select-trigger" type="button" aria-haspopup="dialog" onClick={()=>releaseDialog.current?.showModal()}>{t(form.expected_release_period)}</button></label><label>{t('Platform')}<Select ariaLabel="Platform" value={form.target_platform} onChange={(v)=>update('target_platform',v)} options={platforms} /></label><label>{t('Marketing budget')}<Select ariaLabel="Marketing budget" value={form.marketing_budget} onChange={(v)=>update('marketing_budget',v)} options={budgets} /></label></div><fieldset><legend>{t('Target languages')}</legend><div className="choice-grid">{languages.map((item)=><label className={form.target_languages.includes(item)?'selected':''} key={item}><input type="checkbox" checked={form.target_languages.includes(item)} onChange={()=>toggle('target_languages',item)}/><span className="choice-checkbox" aria-hidden="true"><Check size={11}/></span><span>{t(item)}</span></label>)}</div></fieldset><fieldset><legend>{t('Priority states')}</legend><div className="choice-grid">{states.map((item)=><label className={form.target_states.includes(item)?'selected':''} key={item}><input type="checkbox" checked={form.target_states.includes(item)} onChange={()=>toggle('target_states',item)}/><span className="choice-checkbox" aria-hidden="true"><Check size={11}/></span><span>{t(item)}</span></label>)}</div></fieldset>
          <dialog className="release-dialog" ref={releaseDialog} aria-labelledby="release-dialog-title"><div className="release-dialog-head"><div><span className="eyebrow">{t('PLANNING WINDOW')}</span><h3 id="release-dialog-title">{t('Choose a release quarter')}</h3><p>{t('Select from the next six years of quarterly windows.')}</p></div><button className="release-dialog-close" type="button" aria-label={t('Close release period picker')} onClick={()=>releaseDialog.current?.close()}>×</button></div><div className="release-years">{Array.from(new Set(releasePeriods.map((period)=>period.year))).map((year)=><section className="release-year" key={year}><h4>{lang==='ja'?`${year}年`:year}</h4><div className="release-quarter-grid">{releasePeriods.filter((period)=>period.year===year).map((period)=><button type="button" className={form.expected_release_period===period.value?'selected':''} key={period.value} aria-pressed={form.expected_release_period===period.value} onClick={()=>{update('expected_release_period',period.value);releaseDialog.current?.close()}}>{t('Q{q}',{q:period.quarter})}</button>)}</div></section>)}</div></dialog>
        </div>
        <div className="form-section"><h2>{t('Production context')}</h2><div className="field-grid two"><label>{t('Studio')}<input value={form.studio} onChange={(e)=>update('studio',e.target.value)} placeholder={t('Optional')} /></label><label>{t('Franchise status')}<Select ariaLabel="Franchise status" value={form.franchise_status} onChange={(v)=>update('franchise_status',v)} options={franchises} /></label></div><div className="field-grid two"><label>{t('Director')}<input value={form.director} onChange={(e)=>update('director',e.target.value)} placeholder={t('Optional')} /></label><label>{t('Episodes or runtime units')}<input type="number" min={1} max={2000} value={form.episode_count} onChange={(e)=>update('episode_count',e.target.value)} placeholder={t('e.g. 12')} /></label></div><div className="field-grid two"><label>{t('Age rating')}<Select ariaLabel="Age rating" value={form.age_rating} onChange={(v)=>update('age_rating',v)} options={ageOptions} /></label><label>{t('Target audience')}<Select ariaLabel="Target audience" value={form.target_audience} onChange={(v)=>update('target_audience',v)} options={audienceOptions} /></label></div><label>{t('Trailer URL')}<input type="url" value={form.trailer_url} onChange={(e)=>update('trailer_url',e.target.value)} placeholder="https://youtube.com/watch?v=…" /></label></div>
      </div>
      <aside className="intake-aside"><div className="seo-sheet"><div className="aside-title"><SearchCheck/><h2>{t('SEO preflight')}</h2></div><p>{t('This deterministic preflight is saved as metadata. Review the title and synopsis before publishing.')}</p><dl><div><dt>{t('Meta title')}</dt><dd>{seo.metaTitle}</dd></div><div><dt>{t('Description')}</dt><dd>{form.synopsis || t('The synopsis preview will appear here.')}</dd></div><div><dt>{t('Slug')}</dt><dd>/{seo.slug || t('title-slug')}</dd></div><div><dt>{t('Keywords')}</dt><dd>{seo.keywords.join(' · ')}</dd></div></dl></div>{error&&<div className="form-error" role="alert">{t(error)}</div>}<button className="button dark wide" disabled={!connected||status==='submitting'}>{status==='submitting'?<><LoaderCircle className="spin" size={16}/>{t('Preparing…')}</>:<><Sparkles size={16}/>{t('Run market analysis')}</>}</button><p className="submission-note">{t('Submitting creates a persistent title, analysis job and versioned result snapshot.')}</p></aside>
    </form>}
  </div>
}
