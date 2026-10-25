const entries: [RegExp, string, string][] = [
  [/portfolio/i, '作品', 'さくひん'],
  [/new title|analyse/i, '新規', 'しんき'],
  [/decision|analysis/i, '分析', 'ぶんせき'],
  [/playbook|launch/i, '計画', 'けいかく'],
  [/scenario/i, '戦略', 'せんりゃく'],
  [/method/i, '方法', 'ほうほう'],
]

export function japaneseFor(title: string) {
  const hit = entries.find(([pattern]) => pattern.test(title))
  return hit ? { kanji: hit[1], kana: hit[2] } : { kanji: '絆', kana: 'きずな' }
}
