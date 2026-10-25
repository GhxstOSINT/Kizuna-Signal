import { AlertTriangle, ArrowUpRight, Check, Database, LoaderCircle, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { useI18n } from '../i18n'

export function LoadingState({ label = 'Loading intelligence' }: { label?: string }) {
  const { t } = useI18n()
  return <div className="state-block"><LoaderCircle className="spin" /><h2>{t(label)}</h2><p>{t('The evidence plane will resolve when the backend responds.')}</p></div>
}

export function ErrorState({ title = 'The backend could not be reached', message, retry }: { title?: string; message: string; retry?: () => void }) {
  const { t } = useI18n()
  return <div className="state-block error"><AlertTriangle /><h2>{t(title)}</h2><p>{t(message)}</p>{retry && <button className="button dark" onClick={retry}>{t('Try again')}</button>}</div>
}

export function EmptyState({ action }: { action: ReactNode }) {
  const { t } = useI18n()
  return <div className="state-block empty"><Database /><h2>{t('No analysed titles yet')}</h2><p>{t('Add a Japanese title and Kizuna will create the first evidence snapshot for India.')}</p>{action}</div>
}

export function Stat({ value, label, suffix }: { value: string | number; label: string; suffix?: string }) {
  const { t } = useI18n()
  return <div className="stat"><div><strong>{value}</strong>{suffix && <span>{suffix}</span>}</div><small>{t(label)}</small></div>
}

export function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n()
  const normalized = status.replaceAll('_', ' ')
  return <span className={`badge ${status}`}><span />{t(normalized)}</span>
}

export function SectionHeading({ title, note }: { title: string; note?: string }) {
  const { t } = useI18n()
  return <div className="section-heading"><h2>{t(title)}</h2>{note && <p>{t(note)}</p>}</div>
}

export function ScoreField({ score, confidence, interval, classification, origin, meaning }: { score: number; confidence: number; interval: [number, number]; classification: string; origin?: 'trained_model' | 'deterministic_fallback'; meaning?: string }) {
  const { t } = useI18n()
  return <section className="score-field">
    <div className="score-main"><span>{t('Market potential')}</span><strong>{Math.round(score)}</strong><em>/ 100</em></div>
    <div className="score-support">
      <div className="score-badges"><StatusBadge status={classification} />{origin&&<StatusBadge status={origin}/>}</div>
      <dl>
        <div><dt>{t('Evidence confidence')}</dt><dd>{Math.round(confidence)}%</dd></div>
        <div><dt>{t('Expected range')}</dt><dd>{t('{low} to {high}', { low: Math.round(interval[0]), high: Math.round(interval[1]) })}</dd></div>
      </dl>
      {meaning&&<p className="score-meaning">{meaning}</p>}
    </div>
  </section>
}

export function Capability({ good, title, detail }: { good: boolean; title: string; detail: string }) {
  return <div className="capability">{good ? <ShieldCheck /> : <AlertTriangle />}<div><strong>{title}</strong><p>{detail}</p></div>{good && <Check className="cap-check" />}</div>
}

export function InlineLink({ children }: { children: ReactNode }) {
  return <span className="inline-link">{children}<ArrowUpRight size={14} /></span>
}
