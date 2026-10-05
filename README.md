# 採用マーケティング・インテリジェンスツール（MVP）

公開情報を横断して「**どの大学・学部を、どの競合を意識して、どう攻略するか**」を判断する採用戦略支援ツール。
市場を知る → 競合を知る → 学生を知る → 採用戦略を決める、までを一画面の流れで支援します。

> ⚠️ 同梱の `data/sample/` は **デモ用の架空値** です（大学・企業名は MVP 対象に合わせていますが、人数・評価・順位は実績ではありません）。
> 画面上部にもデモ表示が出ます。実データは後述の CSV 形式で投入してください。

## クイックスタート

```bash
pip install -r requirements.txt
python scripts/generate_sample_data.py      # デモ用 CSV を生成（data/sample/）
python -m app.ingest data/sample --reset    # SQLite（rmi.db）に取り込み
uvicorn app.main:app --reload               # http://localhost:8000
```

AI 要約・攻略仮説は Claude（既定 `claude-opus-5-5`）を使います。`ANTHROPIC_API_KEY` を設定すると有効になり、
未設定・エラー時は **同じ出力形式のルールベース生成に自動でフォールバック** します（画面に生成エンジンを表示）。

| 環境変数 | 既定値 | 内容 |
|---|---|---|
| `RMI_DB_PATH` | `./rmi.db` | SQLite のパス |
| `RMI_TARGET_COMPANY_ID` | `nitori` | 自社（比較の基準）の company_id |
| `RMI_AI_ENABLED` | `1` | `0` で AI を使わない |
| `RMI_AI_MODEL` / `RMI_AI_EFFORT` | `claude-opus-5-5` / `medium` | AI モデルと effort |

## ブラウザ版デモ（インストール不要）

`python scripts/build_static_demo.py` で、全画面を1ファイルに埋め込んだ `dist/demo.html` を生成します。
サーバー無しでブラウザだけで開けます（AI 提案はルールベース、自由記述の分類はキーワード辞書で動作）。

## 画面（仕様書 9〜13章）

| 画面 | URL | 目的 |
|---|---|---|
| 重点大学・学部ランキング | `#/` | どこを見るべきか。攻略優先度・Market Fit・市場規模・自社掲載・親和性・競合強度・未開拓余地・信頼度・推奨アクション。地域/国公私/文理/学部/規模/競合企業/自社実績でフィルター |
| 大学・学部詳細 | `#/faculty/{id}` | 基本情報・過年度推移・業種構成・主な就職先（人数非公開は「非公開」表示）・自社接点・採用競合 TOP10・スコア内訳・出典 |
| 競合企業詳細 | `#/company/{id}` | なぜ競合か（シグナル内訳）・重なる大学/学部・地域/文理分布・ONE CAREER 指標・自社 vs 競合比較表 |
| 学生インサイト | `#/insights` | 企業選択の重視点・忌避要因（前年差）、体験談テーマ別言及件数、自由記述の AI テーマ分類 |
| 攻略提案 | `#/strategy/{id}` | 市場要約 → 競合 → 学生価値観 → 親和性 → 課題 → 訴求仮説 → 施策 → 検証方法。各主張に出典 ID |
| データソース | `#/sources` | 情報取得レベル（A/B/C）、未正規化の企業名、全出典 |

## MVP 完成条件（19章）との対応

`tests/test_api.py` が各条件をそのままテストしています（`python -m pytest`）。

1. 大学検索 `/api/search` ／ 2. 学部選択 ／ 3. 主要就職先 `/api/faculties/{id}` ／ 4. 自社掲載有無（不明は `null`）
5. 採用競合 TOP10 ／ 6. 競合詳細比較 `/api/companies/{id}` ／ 7. 学生市場シグナル `/api/insights`
8. 一次ソース遷移（全レスポンスに `sources`）／ 9・10. AI 要約・攻略仮説 `/api/strategy/{id}`

## スコアの考え方

スコアは **意思決定の補助** であり絶対評価ではありません。重みは `app/analytics.py` 冒頭で定義し、画面に内訳を表示します。

**採用競合スコア（7章）** — 事業競合ではなく「同じ学生市場に出現する企業」を競合とみなす。

| シグナル | 重み | 算出 |
|---|---|---|
| S1 学部内就職先重複 | 20% | 当該学部に掲載あり＝0.5＋人数シェア×0.5（人数非公開は中立値） |
| S2 自社掲載学部での同時出現 | 30% | 自社が掲載されている学部のうち、その企業も掲載されている割合 |
| S3 複数大学での出現 | 15% | 出現大学数 ÷ 企業データのある大学数 |
| S4 学生関心度 | 10% | ONE CAREER お気に入り数（最大値で正規化） |
| S5 就職人気ランキング | 10% | 最良順位から換算 |
| S6 業界近接性 | 15% | 自社業界からの近さ（`INDUSTRY_PROXIMITY`） |

学部を指定しない全体スコアは S1 を除いて再正規化します。

**攻略優先度（8章・100点）** — 市場規模20／就職市場力15／自社親和性20／競合市場性15／業界適合性10／未開拓余地10／データ信頼度10。
欠損指標は 0 ではなく中立値（0.4）で補完し「欠損」と明示。優先度ランクは相対評価（上位20%=A、次30%=B、次30%=C、残り=D）。

## データ品質ルール（16章）の実装

- **人数なし ≠ 0人**：CSV の人数が空欄なら `count = NULL`。画面では「非公開」と表示し、集計で 0 扱いしない
- **年度の分離**：`source_log` に対象年度・公開日・取得日を別カラムで保持。学部ごとに最新年度の就職先のみを使い年度を混ぜない
- **企業名の正規化**：原文（`company_name_raw`）を保持しつつ、`app/normalize.py`（NFKC・法人格/「グループ」「ホールディングス」除去）＋別名辞書で `company_id` に統合。未解決はデータソース画面に一覧表示
- **学部・学科の分離**：`faculty_master` に学部と学科を別カラムで保持
- **出典必須**：全ファクト行に `source_id` が必須。未登録 ID は取り込みエラー
- **ONE CAREER**：体験談本文は保存せず、件数・評価・テーマ別言及数などのメタデータのみ。件数を応募者数として扱わない

## AI の役割（14章）

`app/ai.py`。システムプロンプトで「入力データ以外の事実を書かない」「応募数・併願率・辞退率を推定しない」
「人数 null は非公開」「学生調査は一般的傾向」「各主張に source_id」を指示し、JSON Schema による構造化出力で受け取ります。
結果は入力データのハッシュでキャッシュ（`ai_cache`）し、データ再投入時に破棄されます。

## 実データの投入

`python -m app.ingest <dir> --reset` で、ディレクトリ内の以下の CSV（UTF-8、ヘッダ行あり）を取り込みます。存在するファイルだけ取り込まれます。
`--reset` を付けなければ既存データに追加投入できます（例：大学を1校ずつ実データに差し替える）。就職先・学生シグナル・体験談シグナルは、CSV に含まれる学部×年度などの範囲だけが置き換わり、それ以外は残ります。
列定義は `data/sample/` の各ファイルを参照してください。

| ファイル | 主な列 |
|---|---|
| `sources.csv` | source_id, url, source_name, source_type, retrieved_at, published_at, target_year, scope, reliability |
| `universities.csv` | university_id, name, region, prefecture, establishment, student_count, disclosure_level(A/B/C), source_id |
| `faculties.csv` | faculty_id, university_id, faculty, department, field(文系/理系/文理融合), student_count, source_id |
| `career_outcomes.csv` | university_id, faculty_id, year, graduates, employed, further_study, employment_rate, source_id |
| `employment_companies.csv` | university_id, faculty_id, year, company_name_raw, count(空欄=非公開), listed, source_id |
| `employment_industries.csv` | university_id, faculty_id, year, industry, count, ratio, source_id |
| `companies.csv` / `company_aliases.csv` | 企業マスタ／別名辞書（alias, company_id） |
| `company_attributes.csv` | company_id, attribute(給与/勤務地/転勤/キャリア…), value, source_id |
| `student_signals.csv` | year, segment, theme, metric, value, unit, source_id |
| `review_signals.csv` | company_id, year, segment, theme, signal_type(favorites/rating/selection_reviews/intern_reviews/popularity_rank/theme_mentions), value, source_id |

ONE CAREER 等のデータを大量に取得する場合は、正式なサービス契約・利用許諾を前提としてください。

## 構成

```
app/
  schema.sql     データモデル（15章）
  ingest.py      CSV 取り込み・品質ルール
  normalize.py   企業名正規化
  analytics.py   採用競合スコア・攻略優先度
  ai.py          Claude による要約・攻略仮説・テーマ分類（ルールベース fallback 付き）
  insights.py    テーマ辞書
  main.py        FastAPI（/api/*）
static/          画面（依存なしの HTML/JS）
scripts/generate_sample_data.py   デモデータ生成
tests/           pytest
```

## 今後の拡張（21章）

社内 ATS（応募・内定・承諾・辞退）を接続する場合は、`faculty_id` / `company_id` をキーにテーブルを追加し、
`Analytics` に実績シグナルを加える想定です。外部市場データ × 社内採用実績の統合で「来年度攻略すべき学部 TOP50」等へ発展させます。
