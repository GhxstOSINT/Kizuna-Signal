// Content formats offered in the dashboard. Values match backend ContentFormat;
// the anime_* values map onto the trained model's formats in backend/app/services/state_frame.py.
export const contentFormats = [
  { value: 'anime_series', label: 'Anime series' },
  { value: 'anime_film', label: 'Anime film' },
  { value: 'anime_short', label: 'Anime short series' },
  { value: 'anime_ova', label: 'Anime OVA' },
  { value: 'anime_ona', label: 'Anime ONA (web release)' },
  { value: 'anime_special', label: 'Anime special' },
  { value: 'live_action_series', label: 'Live-action series' },
  { value: 'live_action_film', label: 'Live-action film' },
  { value: 'game', label: 'Game' },
  { value: 'other', label: 'Other' },
]

// Older rows were saved as "series", "film" or "animated film"; fold them into the current values.
const legacy: Record<string, string> = { series: 'anime_series', film: 'anime_film', animated_film: 'anime_film', special: 'anime_special' }

export function canonicalFormat(value: string): string {
  const key = value.trim().toLowerCase().replace(/[\s-]+/g, '_')
  return legacy[key] ?? key
}

export function formatLabel(value: string): string {
  const key = canonicalFormat(value)
  return contentFormats.find((item) => item.value === key)?.label ?? value.replaceAll('_', ' ')
}
