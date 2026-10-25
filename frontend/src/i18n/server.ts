// Japanese for the sentences the API writes. Results are stored with their English text, so they are
// translated here when shown. A placeholder written {name|t} is itself translated (states, languages, genres).
type Rule = [string, string]

const RULES: Rule[] = [
  // API errors and job stages
  ['Title not found', 'タイトルが見つかりません'],
  ['Analysis not found', '分析が見つかりません'],
  ['Project not found', 'プロジェクトが見つかりません'],
  ['Analysis has not completed', '分析はまだ完了していません'],
  ['Analysis is {status|t}', '分析は現在「{status|t}」です'],
  ['Request failed with status {n}.', 'リクエストが失敗しました（ステータス {n}）。'],
  ['No trained state model found; run backend/scripts/train/train_state_model.py', '学習済みの州モデルが見つかりません。backend/scripts/train/train_state_model.py を実行してください'],
  ['Optional source failure lowers confidence but does not fabricate evidence.', 'オプションのソースが失敗すると信頼度は下がりますが、エビデンスが捏造されることはありません。'],
  ['Analysis failed unexpectedly. Please retry; if it persists, contact support.', '分析が予期せず失敗しました。再試行してください。改善しない場合はサポートへご連絡ください。'],
  ['Title no longer exists', 'タイトルはすでに存在しません'],
  ['collecting public evidence', '公開エビデンスを収集中'],
  ['building content profile and comparable titles', 'コンテンツプロファイルと類似タイトルを作成中'],
  ['running trained market and regional model', '学習済みの市場・地域モデルを実行中'],
  ['generating explanations and confidence interval', '説明と信頼区間を生成中'],
  ['building launch playbook', 'ローンチプレイブックを作成中'],
  ['analysis completed', '分析が完了しました'],
  ['analysis failed', '分析に失敗しました'],
  ['A bounded relative market-opportunity index, not a revenue forecast.', '収益予測ではなく、範囲を限定した相対的な市場機会指数です。'],
  ['The trained model was unavailable, so this snapshot uses the deterministic fallback.', '学習済みモデルが利用できなかったため、このスナップショットは決定論的フォールバックを使用しています。'],
  ['share of the {n} csv/ titles scoring below this one, x100 (regional part in-sample for the {m} state-labelled titles)', 'このタイトルよりスコアが低い {n} 件のCSVタイトルの割合（×100）。地域部分は、州ラベル付き {m} 件のタイトルによる学習内評価です'],
  ['out-of-fold, expanding time windows, franchise-separated, real rows only; final models refit on all titles', '時間窓を拡張するアウトオブフォールド検証、フランチャイズ分離、実データのみ。最終モデルは全タイトルで再学習'],

  // Comparable titles
  ['Genre overlap: {list|t}', 'ジャンルの一致: {list|t}'],
  ['Theme overlap: {list|t}', 'テーマの一致: {list|t}'],
  ['General audience and format proximity', '一般層と形式の近さ'],

  // Confidence and data-quality notes
  ['Not measured, so excluded from the score: {list|t}', '未計測のため、スコアから除外: {list|t}'],
  ['Analysis completed without: {list|t}.', '次を除いて分析を完了しました: {list|t}。'],
  ['No localization language was supplied; regional recommendations use inferred defaults.', 'ローカライズ言語が指定されなかったため、地域の推奨には推定の既定値を使用しています。'],
  ['Limited theme metadata reduces comparable-title specificity.', 'テーマのメタデータが限られているため、類似タイトルの精度が下がります。'],
  ['No title-specific demand or engagement evidence was found; the score reflects content fit and genre benchmarks only.', 'タイトル固有の需要やエンゲージメントのエビデンスが見つからなかったため、スコアはコンテンツ適合とジャンルのベンチマークのみを反映しています。'],
  ['An unreleased title has no Google Trends window before launch, so demand momentum is not scored.', '未公開のタイトルには公開前のGoogleトレンドの期間がないため、需要の勢いはスコアに含めていません。'],
  ['Trailer engagement is not collected yet, so engagement quality is not scored.', '予告編のエンゲージメントはまだ収集していないため、エンゲージメントの質はスコアに含めていません。'],
  ['No comparable titles were found.', '類似タイトルが見つかりませんでした。'],
  ['Fewer than three comparable titles were found.', '見つかった類似タイトルは3件未満です。'],
  ['This title is unlike the titles the model was trained on.', 'このタイトルは、モデルが学習したタイトルとは性質が異なります。'],
  ['There is no franchise history for this title.', 'このタイトルにはフランチャイズの実績がありません。'],
  ['The model was trained on a small set of titles, so its results are exploratory.', 'モデルは少数のタイトルで学習しているため、結果は探索的なものです。'],
  ['Some states have too few training titles for a reliable result.', '一部の州は学習タイトルが少なく、信頼できる結果が得られません。'],
  ['The training data includes synthetic rows.', '学習データには合成データの行が含まれています。'],
  ['Success-model outcome tables are unavailable', '成功モデルの成果テーブルは利用できません'],

  // Drivers and regional reasons
  ['Model component {v}/100 with {w}% configured weight; held-out Spearman {r}.', 'モデル要素 {v}/100、設定ウェイト {w}%、保留データでのスピアマン {r}。'],
  ['Ranked {n} of {c} states by predicted relative demand lift.', '予測される相対的な需要増では、{c} 州中 {n} 位です。'],
  ['Expected share of modelled India demand is {p}%.', 'モデル化したインド全体の需要に占める想定シェアは {p}% です。'],
  ['The state estimate uses {a} real labelled titles and {b} synthetic rows.', 'この州の推定には、実データのラベル付きタイトル {a} 件と、合成データ {b} 行を使用しています。'],
  ['Population {pop}M and {urban}% urban (Census {year}).', '人口 {pop}M、都市人口比率 {urban}%（{year}年国勢調査）。'],
  ['Google Trends interest {v}/100 in {s|t}, shrunk to {n} for small-state noise.', '{s|t}のGoogleトレンド関心度は {v}/100（小規模な州のノイズを考慮し {n} に補正）。'],
  ['Google Trends interest {v}/100 in {s|t}.', '{s|t}のGoogleトレンド関心度は {v}/100 です。'],
  ['No Google Trends reading for this state.', 'この州のGoogleトレンドの値はありません。'],
  ['Planned localization/targeting covers {s|t} ({l|t}).', '計画中のローカライズ／ターゲティングは{s|t}（{l|t}）を含みます。'],
  ['Survey affinity index {i} (100 = state average, n={n}).', 'アンケート親和性指数 {i}（100 = 州平均、n={n}）。'],
  ['Regional baseline indicates {l|t} audience opportunity.', '地域のベースラインは、{l|t}の視聴者層に機会があることを示しています。'],
  ['Title-level potential contributes {n}/100 to this region.', 'タイトル全体のポテンシャルが、この地域に {n}/100 寄与しています。'],
  ['The proposed localization includes {l|t}.', '提案するローカライズには{l|t}が含まれます。'],
  ['Content-India fit', 'コンテンツのインド適合'],
  ['Component score {v}/100 under scoring version {ver}.', 'スコアリングバージョン {ver} における要素スコアは {v}/100 です。'],
  ['Localization plan not specified', 'ローカライズ計画が未指定です'],
  ['No target Indian language was provided in the title assumptions.', 'タイトルの前提条件に、対象となるインドの言語が指定されていません。'],
  ['Incomplete public evidence', '公開エビデンスが不完全です'],
  ['Unavailable sources: {list}.', '利用できないソース: {list}。'],

  // Recommendation and playbook
  ['Proceed with a multilingual regional-first launch.', '多言語での、地域を優先したローンチを進めます。'],
  ['Proceed with a controlled regional pilot before national expansion.', '全国展開の前に、管理された地域パイロットを実施します。'],
  ['Run trailer and localization tests before committing major investment.', '大きな投資を決める前に、予告編とローカライズのテストを実施します。'],
  ['Limit investment and collect stronger demand evidence.', '投資を抑え、より強い需要のエビデンスを集めます。'],
  ['Dub in {l|t}', '{l|t}の吹き替え'],
  ['Subtitle in {l|t}', '{l|t}の字幕'],
  ['Urban viewers aged 16-30', '16〜30歳の都市部の視聴者'],
  ['Existing {g|t} and Japanese-content audiences', '既存の{g|t}・日本コンテンツのファン層'],
  ['Mainstream crossover audiences', '主流層へのクロスオーバー層'],
  ['Evidence confidence is not yet sufficient for a high-investment national launch.', '大規模な投資を伴う全国ローンチには、エビデンスの信頼度がまだ十分ではありません。'],
  ['Localization preferences were inferred and should be validated with audience testing.', 'ローカライズの好みは推定によるものです。視聴者テストで検証してください。'],
  ['Public demand proxies do not equal revenue or platform completion outcomes.', '公開されている需要の代理指標は、収益やプラットフォームでの視聴完了の成果と同じではありません。'],
  ['Position the title around its {g|t} identity, emotional hook and strongest comparable-title audiences.', 'このタイトルを、{g|t}としての個性、感情的なフック、最も強い類似タイトルのファン層を軸に位置づけます。'],
  ['Release a localized teaser and compare language-variant engagement.', 'ローカライズしたティザーを公開し、言語ごとのエンゲージメントを比較します。'],
  ['Run community and creator activation in {list|t}.', '{list|t}で、コミュニティとクリエイターの活性化施策を実施します。'],
  ['Increase campaign investment only after regional engagement validation.', '地域でのエンゲージメントを検証してから、キャンペーン投資を増やします。'],

  // Sources
  ['{name} is unavailable; analysis continued without this source.', '{name}は利用できません。このソースなしで分析を続行しました。'],
  ['{name} is not configured; no data was used.', '{name}は設定されていないため、データは使用していません。'],
  ['{name} failed unexpectedly; no data was used.', '{name}が予期せず失敗したため、データは使用していません。'],
  ['Google Trends values are normalized relative interest, not absolute volume.', 'Googleトレンドの値は正規化された相対的な関心度であり、絶対的な量ではありません。'],
  ['Public YouTube video statistics are global and not exact India-only views.', '公開されているYouTubeの動画統計は全世界の値であり、インドだけの正確な視聴数ではありません。'],
  ['Wikipedia activity indicates information seeking, not content consumption.', 'Wikipediaでの活動は情報収集を示すものであり、コンテンツの消費を示すものではありません。'],
  ['Census context is from {year} tables; it describes population and language, not current viewing behaviour.', '国勢調査の背景情報は{year}年の統計表に基づきます。人口と言語を示すもので、現在の視聴行動を示すものではありません。'],
  ['Survey signal comes only from rows labelled as exploratory proxies (preference, rating or synthetic data), not measured viewing rates.', 'アンケートのシグナルは、探索的な代理指標（嗜好、評価、合成データ）とラベル付けされた行のみに基づき、実測の視聴率ではありません。'],
  ['Survey data has no rows for this title\'s genres or content type.', 'アンケートデータに、このタイトルのジャンルやコンテンツ形式に該当する行がありません。'],
  ['No target languages or states were supplied; addressable market not measured.', '対象言語や対象州が指定されなかったため、獲得可能な市場は計測していません。'],
  ['No survey data loaded; state preferences rely on search interest only.', 'アンケートデータが読み込まれていないため、州ごとの嗜好は検索への関心のみに基づいています。'],
  ['Survey file issue: {detail}', 'アンケートファイルの問題: {detail}'],
  ['Survey data is from {y} or earlier and may not reflect current viewing.', 'アンケートデータは{y}年以前のもので、現在の視聴状況を反映していない可能性があります。'],
  ['{n} of {m} survey rows have no year, so their age cannot be checked.', 'アンケートの {m} 行のうち {n} 行に年の記載がなく、データの古さを確認できません。'],
  ['Google Trends is rate limiting this server; retrying in ~{n}s.', 'Googleトレンドがこのサーバーへのアクセスを制限しています。約 {n} 秒後に再試行します。'],
  ['Google Trends rate limit reached; interest not measured for now.', 'Googleトレンドのレート制限に達したため、関心度は今回計測していません。'],
  ['Google Trends request failed: {reason}', 'Googleトレンドへのリクエストが失敗しました: {reason}'],
  ['Google Trends returned no usable data for this title.', 'Googleトレンドから、このタイトルの有効なデータは返されませんでした。'],
  ['Google Trends reports no search interest for this title in India.', 'Googleトレンドでは、このタイトルへのインドでの検索関心は確認されていません。'],
  ['State-level Google Trends interest skipped: rate limit reached.', '州別のGoogleトレンド関心度はスキップしました（レート制限に達したため）。'],
  ['Native-script Google Trends searches skipped: rate limit reached.', '現地語表記でのGoogleトレンド検索はスキップしました（レート制限に達したため）。'],
  ['Imported viewing data (per-capita index {i}/100) shifts this market by {v} points.', '取り込んだ視聴データ（人口当たり指数 {i}/100）により、この市場のスコアは {v} ポイント変動します。'],
  ['State-level Google Trends interest unavailable: {reason}', '州別のGoogleトレンド関心度は利用できません: {reason}'],
  ['Google Trends returned no state-level interest for this title.', 'Googleトレンドから、このタイトルの州別の関心度は返されませんでした。'],
  ['Wikimedia request failed: {reason}', 'Wikimediaへのリクエストが失敗しました: {reason}'],
  ['Wikimedia returned a response in an unexpected format.', 'Wikimediaから、想定外の形式の応答が返されました。'],
  ['No confident Wikipedia article match for this title; interest not measured.', 'このタイトルに確実に一致するWikipedia記事がないため、関心度は計測していません。'],
  ['Matched Wikipedia articles returned no page-view data.', '一致したWikipedia記事から、ページビューのデータは返されませんでした。'],
  ['Wikipedia article match is approximate ({title}); verify it is the right title.', 'Wikipedia記事との一致は近似です（{title}）。正しいタイトルか確認してください。'],
  ['Wikipedia page-view history is short; the article may be new or recently renamed.', 'Wikipediaのページビュー履歴が短く、記事が新しいか、最近名称が変更された可能性があります。'],
  ['YouTube request failed: {reason}', 'YouTubeへのリクエストが失敗しました: {reason}'],
  ['YouTube returned a response in an unexpected format.', 'YouTubeから、想定外の形式の応答が返されました。'],
  ['No YouTube videos found for this title.', 'このタイトルのYouTube動画は見つかりませんでした。'],
  ['YouTube results did not clearly match this title; interest not measured.', 'YouTubeの検索結果がこのタイトルと明確に一致しなかったため、関心度は計測していません。'],
  ['AniList is rate limiting this server; retry in ~{n}s.', 'AniListがこのサーバーへのアクセスを制限しています。約 {n} 秒後に再試行してください。'],
  ['AniList rate limit reached; metadata not collected.', 'AniListのレート制限に達したため、メタデータは収集していません。'],
  ['AniList request failed: {reason}', 'AniListへのリクエストが失敗しました: {reason}'],
  ['AniList returned a response in an unexpected format.', 'AniListから、想定外の形式の応答が返されました。'],
  ['AniList has no matching title and no comparable genre pool.', 'AniListに、一致するタイトルも、比較できるジャンルの母集団もありません。'],
  ['AniList popularity is a global fan-community signal, not Indian viewership; comparables are drawn from the most popular titles in the genre.', 'AniListの人気は世界のファンコミュニティによるシグナルであり、インドでの視聴数ではありません。類似作品は、ジャンル内で最も人気のあるタイトルから選んでいます。'],
  ['Title is not listed on AniList yet; only genre comparables are used.', 'このタイトルはまだAniListに掲載されていないため、ジャンルの類似作品のみを使用しています。'],
  ['PROXY synthetic: probit-normal simulation, seed {seed}; not measured data', '代理指標（合成）: プロビット正規シミュレーション、シード {seed}。実測データではありません'],
]

// Machine codes older results may carry, with the sentence each one stands for.
const CODES: Record<string, string> = {
  no_pre_release_demand: 'An unreleased title has no Google Trends window before launch, so demand momentum is not scored.',
  no_youtube_adapter: 'Trailer engagement is not collected yet, so engagement quality is not scored.',
  no_comparable_titles: 'No comparable titles were found.',
  few_comparables: 'Fewer than three comparable titles were found.',
  unlike_training_titles: 'This title is unlike the titles the model was trained on.',
  no_franchise_history: 'There is no franchise history for this title.',
  small_training_set: 'The model was trained on a small set of titles, so its results are exploratory.',
  sparse_state_training: 'Some states have too few training titles for a reliable result.',
  synthetic_augmented: 'The training data includes synthetic rows.',
}

const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const compiled = RULES.map(([en, ja]) => {
  const slots: string[] = []
  const pattern = escape(en).replace(/\\\{(\w+)(?:\\\|t)?\\\}/g, (_, slot: string) => { slots.push(slot); return '(.+?)' })
  return { regex: new RegExp(`^${pattern}$`), slots, ja }
})

/** Translate a sentence written by the API; returns null when no rule applies. `word` translates a placeholder value. */
export function translateServer(text: string, word: (value: string) => string, sentence: (value: string) => string | null): string | null {
  const quarter = /^Q([1-4]) (\d{4})$/.exec(text)
  if (quarter) return `${quarter[2]}年第${quarter[1]}四半期`
  const code = /^([a-z_]+)(?::\s.*)?$/.exec(text)
  if (code && CODES[code[1]]) return sentence(CODES[code[1]])
  for (const rule of compiled) {
    const match = rule.regex.exec(text)
    if (!match) continue
    return rule.ja.replace(/\{(\w+)(\|t)?\}/g, (_, slot: string, flag?: string) => {
      const value = match[rule.slots.indexOf(slot) + 1] ?? ''
      return flag ? word(value) : value
    })
  }
  return null
}
