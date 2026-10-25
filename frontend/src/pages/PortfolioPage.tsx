import { Plus, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { loadPortfolio } from '../api'
import { canonicalFormat, contentFormats, formatLabel } from '../lib/formats'
import { PageHeader, SignalRail } from '../components/AppShell'
import { EmptyState, ErrorState, LoadingState, Stat, StatusBadge } from '../components/Primitives'
import { Select } from '../components/Select'
import { useI18n } from '../i18n'
import type { PortfolioItem } from '../api/types'

const formatOptions = [{ value: 'all', label: 'All formats' }, ...contentFormats]

export function PortfolioPage({ connected }: { connected: boolean }) {
  const { t } = useI18n()
  const [items, setItems] = useState<PortfolioItem[]>([])
  const [query, setQuery] = useState('')
  const [format, setFormat] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = () => {
    setLoading(true); setError('')
    loadPortfolio().then(setItems).catch((e) => setError(e.message)).finally(() => setLoading(false))
  }
  useEffect(load, [])
  const visible = useMemo(() => items.filter(({ title }) =>
    title.name.toLowerCase().includes(query.toLowerCase()) && (format === 'all' || canonicalFormat(title.content_format) === format)
  ), [items, query, format])
  const results = items.map((item) => item.analysis.result).filter(Boolean)
  const average = results.length ? Math.round(results.reduce((sum, result) => sum + result!.market_potential_score, 0) / results.length) : 0
  const confidence = results.length ? Math.round(results.reduce((sum, result) => sum + result!.confidence_score, 0) / results.length) : 0
  const stateCount = new Set(results.flatMap((result) => result!.regional_scores.slice(0, 5).map((row) => row.state))).size

  return <div className="page portfolio-page">
    <PageHeader title="Portfolio" description="Pre-release intelligence for Japanese media entering India." action={<Link className="button dark" to="/new"><Plus size={16} /> {t('Analyse new title')}</Link>} />
    <div className="filter-row">
      <label className="search"><Search size={16} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('Search by title')} aria-label={t('Search titles')} /></label>
      <Select ariaLabel="Filter by content format" value={format} onChange={setFormat} options={formatOptions} />
    </div>
    <SignalRail connected={connected} label={t('{count} TITLES IN VIEW', { count: visible.length })} />
    <section className="portfolio-hero">
      <div><h2>{t('See the next signal before launch.')}</h2><p>{t('Compare market potential, evidence confidence and regional opportunity, then turn the strongest signals into a launch plan.')}</p></div>
    </section>
    <div className="stats-grid">
      <Stat value={visible.length} label="Titles in view" />
      <Stat value={average} suffix="/ 100" label="Average potential" />
      <Stat value={`${confidence}%`} label="Average confidence" />
      <Stat value={stateCount} label="Priority states" />
    </div>
    {loading ? <LoadingState /> : error ? <ErrorState message={error} retry={load} /> : visible.length === 0 ? <EmptyState action={<Link className="button dark" to="/new">{t('Start first analysis')}</Link>} /> : <section className="analysis-list">
      <div className="section-heading"><h2>{t('Analysis portfolio')}</h2><p>{t('Backend-authoritative snapshots ordered by their latest analysis.')}</p></div>
      {visible.map(({ title, analysis }) => {
        const result = analysis.result
        return <article className="title-row" key={analysis.id}>
          <div className="title-identity"><span>{t(formatLabel(title.content_format))} · {t(title.primary_genre)}</span><div className="title-heading-line"><h3>{title.name}</h3><StatusBadge status={result ? result.decision_classification : analysis.status} /></div><p>{title.synopsis}</p></div>
          {result ? <>
            <div className="title-score"><strong>{Math.round(result.market_potential_score)}</strong><span>/100</span><small>{t('Market potential')}</small></div>
            <div className="title-evidence"><dl><div><dt>{t('Confidence')}</dt><dd>{Math.round(result.confidence_score)}%</dd></div><div><dt>{t('Top market')}</dt><dd>{result.regional_scores[0] ? t(result.regional_scores[0].state) : t('Not available')}</dd></div><div><dt>{t('Language')}</dt><dd>{result.regional_scores[0] ? t(result.regional_scores[0].recommended_language) : t('Not available')}</dd></div></dl></div>
          </> : <div className="title-evidence"><p>{t('Analysis has not produced a result yet.')}</p></div>}
          <Link className="title-row-link" to={`/analysis/${analysis.id}`} aria-label={t('Open {name} analysis', { name: title.name })} />
        </article>
      })}
    </section>}
  </div>
}
