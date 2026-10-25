import { LoaderCircle, Upload } from 'lucide-react'
import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useI18n } from '../i18n'
import type { StateSignal, StateSignalImportResult } from '../api/types'
import { SectionHeading } from './Primitives'

type Summary = { source: string; rows: number; states: number; asOf: string }

function summarise(signals: StateSignal[]): Summary[] {
  const groups = new Map<string, StateSignal[]>()
  for (const signal of signals) {
    const key = `${signal.source}|${signal.metric}`
    groups.set(key, [...(groups.get(key) ?? []), signal])
  }
  return [...groups.entries()].map(([key, rows]) => ({
    source: key.replace('|', ' · '),
    rows: rows.length,
    states: new Set(rows.map((row) => row.state)).size,
    asOf: rows.reduce((latest, row) => (row.as_of > latest ? row.as_of : latest), rows[0].as_of),
  }))
}

/** Import partner or Ormax state data for a title and list what is stored. Applies to the next analysis. */
export function StateDataPanel({ titleId }: { titleId: string }) {
  const { t } = useI18n()
  const file = useRef<HTMLInputElement>(null)
  const [source, setSource] = useState('partner_import')
  const [signals, setSignals] = useState<StateSignal[]>([])
  const [result, setResult] = useState<StateSignalImportResult | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api.listStateSignals(titleId).then(setSignals).catch(() => setSignals([]))
  }, [titleId])
  useEffect(load, [load])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const chosen = file.current?.files?.[0]
    if (!chosen) { setError(t('Choose a CSV file first.')); return }
    setBusy(true); setError(''); setResult(null)
    try {
      setResult(await api.importStateSignals(titleId, chosen, source.trim() || 'partner_import'))
      if (file.current) file.current.value = ''
      load()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t('The CSV could not be imported.'))
    } finally {
      setBusy(false)
    }
  }

  const stored = summarise(signals)
  return <section className="state-data">
    <SectionHeading title="State-level data" note="Import partner, platform or Ormax viewing by state. It tilts state scores in the next analysis of this title." />
    <form className="state-data-form" onSubmit={submit}>
      <label>{t('CSV file')}<input ref={file} type="file" accept=".csv,text/csv" /></label>
      <label>{t('Source name')}<input value={source} onChange={(event) => setSource(event.target.value)} maxLength={80} /></label>
      <button className="button dark" disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <Upload size={16} />}{t('Import')}</button>
    </form>
    <p className="state-data-hint">{t('Columns: state, metric, value, as_of (optional), source (optional). Volume metrics are divided by state population.')}</p>
    {error && <div className="form-error" role="alert">{error}</div>}
    {result && <div className="state-data-result" aria-live="polite">
      <strong>{t('{n} rows imported', { n: result.imported })}</strong>
      {result.rejected_count > 0 && <p>{t('{n} rows rejected', { n: result.rejected_count })}: {result.rejected.slice(0, 3).map((item) => `${t('row')} ${item.row}: ${item.reason}`).join('; ')}</p>}
      <p>{t('Run the analysis again to apply it.')}</p>
    </div>}
    {stored.length > 0
      ? <div className="state-data-list">{stored.map((item) => <article key={item.source}><strong>{item.source}</strong><span>{t('{rows} rows, {states} states, as of {date}', { rows: item.rows, states: item.states, date: item.asOf })}</span></article>)}</div>
      : <p className="quiet">{t('No state-level data stored for this title yet.')}</p>}
  </section>
}
