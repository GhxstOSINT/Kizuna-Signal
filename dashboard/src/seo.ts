export type SeoSuggestion = { displayTitle: string; metaTitle: string; description: string; keywords: string[]; slug: string }

export function buildSeoSuggestion(name: string, synopsis: string, genre: string, themes: string[]): SeoSuggestion {
  const cleanName = name.trim() || 'Untitled Japanese release'
  const hook = synopsis.trim().replace(/\s+/g, ' ').split(/[.!?]/)[0]?.slice(0, 118)
  const keywords = Array.from(new Set([genre, ...themes, 'Japanese', 'India', 'release'].filter(Boolean))).slice(0, 8)
  return {
    displayTitle: cleanName,
    metaTitle: `${cleanName}: ${genre || 'Japanese title'} market outlook in India`.slice(0, 60),
    description: `${hook || `Pre-release market outlook for ${cleanName}`} Explore regional demand, localization and launch evidence for India.`.slice(0, 155),
    keywords,
    slug: cleanName.toLowerCase().normalize('NFKD').replace(/[^a-z0-9\s-]/g, '').trim().replace(/\s+/g, '-'),
  }
}
