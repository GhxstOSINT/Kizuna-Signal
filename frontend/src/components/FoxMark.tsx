/**
 * The Kizuna fox as a minimal geometric mark: a faceted head, two slanted eyes and a small nose.
 * `solid` is the full-colour logo; `outline` is a quiet single-colour version for empty and error states.
 */
export function FoxMark({ variant = 'solid', size = 32, className = '' }: { variant?: 'solid' | 'outline'; size?: number; className?: string }) {
  const outline = variant === 'outline'
  return <svg className={`fox-mark fox-mark-${variant} ${className}`} width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" focusable="false">
    <path className="fox-mark-head" d="M4 5 L17 14 H31 L44 5 L42 27 L24 45 L6 27 Z" fill={outline ? 'none' : '#f2761f'} stroke={outline ? 'currentColor' : 'none'} strokeWidth="2" strokeLinejoin="round" />
    {!outline && <path className="fox-mark-muzzle" d="M6 27 L16 25 L24 31 L32 25 L42 27 L24 45 Z" fill="#fff1e0" />}
    {outline && <path d="M6 27 L16 25 L24 31 L32 25 L42 27" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />}
    <g className="fox-mark-eyes" fill={outline ? 'currentColor' : '#2a140a'}>
      <path d="M13 20 L20 22.5 L13 25 Z" />
      <path d="M35 20 L28 22.5 L35 25 Z" />
    </g>
    <path d="M21.5 41 L26.5 41 L24 44.5 Z" fill={outline ? 'currentColor' : '#2a140a'} />
  </svg>
}
