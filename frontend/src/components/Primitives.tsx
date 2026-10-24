import { AlertTriangle, ArrowUpRight, Check, Database, LoaderCircle, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'

export function LoadingState({ label = 'Loading intelligence' }: { label?: string }) {
  return <div className="state-block"><LoaderCircle className="spin" /><h2>{label}</h2><p>The evidence plane will resolve when the backend responds.</p></div>
}

export function ErrorState({ title = 'The backend could not be reached', message, retry }: { title?: string; message: string; retry?: () => void }) {
  return <div className="state-block error"><AlertTriangle /><h2>{title}</h2><p>{message}</p>{retry && <button className="button dark" onClick={retry}>Try again</button>}</div>
}

export function EmptyState({ action }: { action: ReactNode }) {
  return <div className="state-block empty"><Database /><h2>No analysed titles yet</h2><p>Add a Japanese title and Kizuna will create the first evidence snapshot for India.</p>{action}</div>
}

export function Stat({ value, label, suffix }: { value: string | number; label: string; suffix?: string }) {
  return <div className="stat"><div><strong>{value}</strong>{suffix && <span>{suffix}</span>}</div><small>{label}</small></div>
}

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.replaceAll('_', ' ')
  return <span className={`badge ${status}`}><span />{normalized}</span>
}

export function SectionHeading({ title, note }: { title: string; note?: string }) {
  return <div className="section-heading"><h2>{title}</h2>{note && <p>{note}</p>}</div>
}

export function ScoreField({ score, confidence, interval, classification, origin, meaning }: { score: number; confidence: number; interval: [number, number]; classification: string; origin?: 'trained_model' | 'deterministic_fallback'; meaning?: string }) {
  return <section className="score-field">
    <div className="score-main"><span>Market potential</span><strong>{Math.round(score)}</strong><em>/ 100</em></div>
    <div className="score-support">
      <div className="score-badges"><StatusBadge status={classification} />{origin&&<StatusBadge status={origin}/>}</div>
      <dl>
        <div><dt>Evidence confidence</dt><dd>{Math.round(confidence)}%</dd></div>
        <div><dt>Expected range</dt><dd>{Math.round(interval[0])} to {Math.round(interval[1])}</dd></div>
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
