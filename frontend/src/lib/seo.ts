import { translate, type Lang } from '../i18n'

export type SeoSuggestion = { displayTitle: string; metaTitle: string; description: string; keywords: string[]; slug: string }

const latinSlug = (name: string) => name.toLowerCase().normalize('NFKD').replace(/[^a-z0-9\s-]/g, '').trim().replace(/\s+/g, '-')

export function buildSeoSuggestion(name: string, synopsis: string, genre: string, themes: string[], lang: Lang = 'en'): SeoSuggestion {
  if (lang === 'ja') {
    const cleanName = name.trim() || '名称未設定の日本作品'
    const genreJa = genre ? translate(genre, undefined, 'ja') : '日本作品'
    const hook = synopsis.trim().replace(/\s+/g, ' ').split(/[。.!?！？]/)[0]?.slice(0, 80)
    const keywords = Array.from(new Set([genreJa, ...themes.map((theme) => translate(theme, undefined, 'ja')), '日本', 'インド', '公開'].filter(Boolean))).slice(0, 8)
    return {
      displayTitle: cleanName,
      metaTitle: `${cleanName}｜インド市場における${genreJa}の展望`.slice(0, 40),
      description: `${hook ? `${hook}。` : `${cleanName}の公開前市場展望。`}地域別の需要、ローカライズ、ローンチの根拠をご確認ください。`.slice(0, 110),
      keywords,
      slug: cleanName.replace(/\s+/g, '-'),
    }
  }
  const cleanName = name.trim() || 'Untitled Japanese release'
  const hook = synopsis.trim().replace(/\s+/g, ' ').split(/[.!?]/)[0]?.slice(0, 118)
  const keywords = Array.from(new Set([genre, ...themes, 'Japanese', 'India', 'release'].filter(Boolean))).slice(0, 8)
  return {
    displayTitle: cleanName,
    metaTitle: `${cleanName}: ${genre || 'Japanese title'} market outlook in India`.slice(0, 60),
    description: `${hook || `Pre-release market outlook for ${cleanName}`} Explore regional demand, localization and launch evidence for India.`.slice(0, 155),
    keywords,
    slug: latinSlug(cleanName),
  }
}
