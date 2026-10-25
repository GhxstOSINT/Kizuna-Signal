import { MapPin } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useI18n } from '../i18n'
import { INDIA_MAP } from '../lib/indiaMap'
import type { Region } from '../api/types'

// Region names the backend can send that differ from the map's.
const ALIASES: Record<string, string> = { 'Delhi NCR': 'Delhi' }
const mapName = (state: string) => ALIASES[state] ?? state

export function RegionMap({ regions }: { regions: Region[] }) {
  const { t } = useI18n()
  const ranked = useMemo(() => [...regions].sort((a, b) => b.score - a.score), [regions])
  const [selected, setSelected] = useState(ranked[0]?.state ?? '')
  const byMapName = useMemo(() => new Map(ranked.map((region, index) => [mapName(region.state), { region, rank: index + 1 }])), [ranked])
  if (!ranked.length) return null

  const low = ranked[ranked.length - 1].score
  const high = ranked[0].score
  // Colour is relative to this analysis, so a narrow spread (say 74 to 80) is still readable.
  const heat = (score: number) => (high === low ? 100 : ((score - low) / (high - low)) * 100)
  const fill = (score: number) => `color-mix(in srgb, var(--heat-hi) ${heat(score).toFixed(0)}%, var(--heat-lo))`

  const active = ranked.find((region) => region.state === selected) ?? ranked[0]
  const activeMapName = mapName(active.state)
  const activeRank = ranked.indexOf(active) + 1
  const states = [...INDIA_MAP.states].sort((a, b) => Number(a.name === activeMapName) - Number(b.name === activeMapName))

  const shape = (name: string) => {
    const entry = byMapName.get(name)
    return {
      className: `map-state${entry ? '' : ' no-data'}${name === activeMapName ? ' selected' : ''}`,
      style: entry ? { fill: fill(entry.region.score) } : undefined,
      onMouseEnter: entry ? () => setSelected(entry.region.state) : undefined,
      onClick: entry ? () => setSelected(entry.region.state) : undefined,
    }
  }

  return <div className="region-map">
    <figure className="region-map-figure">
      <svg viewBox={`0 0 ${INDIA_MAP.width} ${INDIA_MAP.height}`} role="img" aria-label={t('Heatmap of India by state market opportunity')}>
        {states.map((state) => {
          const props = shape(state.name)
          return <g key={state.name}>
            <path d={state.d} {...props}><title>{t(state.name)}{byMapName.has(state.name) ? ` · ${Math.round(byMapName.get(state.name)!.region.score)}` : ''}</title></path>
            {state.marker && <circle cx={state.marker[0]} cy={state.marker[1]} r={5} {...props} />}
          </g>
        })}
      </svg>
      <figcaption className="map-legend">
        <span>{t('Lower')} · {Math.round(low)}</span>
        <i aria-hidden="true" />
        <span>{Math.round(high)} · {t('Higher')}</span>
      </figcaption>
      <p className="map-note">{t('Colour is relative to the regions scored in this analysis.')}</p>
    </figure>
    <aside className="region-detail" aria-live="polite">
      <span className="region-detail-rank">{t('Rank')} {String(activeRank).padStart(2, '0')} / {ranked.length}</span>
      <h3>{t(active.state)}</h3>
      <div className="region-detail-score"><strong>{Math.round(active.score)}</strong><span>/100 · {t('Confidence')} {Math.round(active.confidence)}%</span></div>
      <p className="region-detail-meta"><MapPin size={13} />{t(active.recommended_language)} · {t(active.preferred_platform)}</p>
      {active.reasons.length > 0 && <ul>{active.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}
      <ol className="region-ranking" aria-label={t('All regions by score')}>
        {ranked.map((region, index) => <li key={region.state}>
          <button type="button" className={region.state === active.state ? 'active' : ''} aria-pressed={region.state === active.state} onClick={() => setSelected(region.state)}>
            <span>{String(index + 1).padStart(2, '0')}</span><span>{t(region.state)}</span><span>{Math.round(region.score)}</span>
          </button>
        </li>)}
      </ol>
    </aside>
  </div>
}
