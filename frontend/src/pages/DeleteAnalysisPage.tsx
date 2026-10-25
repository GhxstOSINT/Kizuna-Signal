import { LoaderCircle, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { PageHeader, SignalRail } from '../components/AppShell'
import { formatLabel } from '../lib/formats'
import { ErrorState, LoadingState, StatusBadge } from '../components/Primitives'
import type { Analysis, Title } from '../api/types'

export function DeleteAnalysisPage({ connected }: { connected: boolean }) {
  const { analysisId = '' } = useParams()
  const navigate = useNavigate()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [title, setTitle] = useState<Title | null>(null)
  const [loadError, setLoadError] = useState('')
  const [deleteError, setDeleteError] = useState('')
  const [deleting, setDeleting] = useState(false)
  useEffect(() => {
    let cancelled = false
    api.getAnalysis(analysisId)
      .then(async (next) => {
        const titles = await api.listProjects().then((projects) => Promise.all(projects.map((project) => api.listTitles(project.id))))
        if (cancelled) return
        setAnalysis(next)
        setTitle(titles.flat().find((item) => item.id === next.title_id) ?? null)
      })
      .catch((e) => { if (!cancelled) setLoadError(e instanceof Error ? e.message : 'Analysis could not be loaded.') })
    return () => { cancelled = true }
  }, [analysisId])

  const confirm = async () => {
    setDeleting(true); setDeleteError('')
    try {
      await api.deleteAnalysis(analysisId)
      navigate('/', { replace: true })
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : 'The analysis could not be deleted.')
      setDeleting(false)
    }
  }

  if (loadError) return <div className="page"><ErrorState title="Analysis not found" message={loadError} /></div>
  if (!analysis) return <div className="page"><LoadingState label="Opening analysis" /></div>
  const name = title?.name ?? 'this title'
  return <div className="page">
    <PageHeader title="Delete analysis" description="Review what will be removed before you confirm." />
    <SignalRail connected={connected} label="CONFIRM DELETION" />
    <section className="delete-confirm" aria-labelledby="delete-heading">
      <span>{title ? `${formatLabel(title.content_format)} · ${title.primary_genre}` : 'Analysis'}</span>
      <h2 id="delete-heading">Delete the analysis for “{name}”?</h2>
      <p><StatusBadge status={analysis.result ? analysis.result.decision_classification : analysis.status} /></p>
      <p>This permanently removes:</p>
      <ul>
        <li>The analysis snapshot and its evidence sources</li>
        <li>Every scenario saved against it</li>
        <li>The title itself, if this is its only analysis</li>
      </ul>
      {deleteError && <div className="form-error" role="alert">{deleteError}</div>}
      <div className="action-pair">
        <button type="button" className="button danger" onClick={confirm} disabled={deleting || !connected}>
          {deleting ? <><LoaderCircle className="spin" size={16} />Deleting…</> : <><Trash2 size={16} />Delete analysis</>}
        </button>
        <Link className="button ghost" to="/" aria-disabled={deleting}>Cancel</Link>
      </div>
    </section>
  </div>
}
