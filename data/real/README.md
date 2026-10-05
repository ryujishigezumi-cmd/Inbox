# 実データ（公開情報）

大学ごとに `data/real/<university_id>/` へ標準形式の CSV を置き、次で取り込みます。

```bash
python scripts/load_real_data.py          # DB を作り直して data/real/ を全部取り込む
```

- 各フォルダ：`sources.csv` `universities.csv` `faculties.csv` `career_outcomes.csv`
  `employment_industries.csv` `employment_companies.csv`（ある分だけ）
- `employment_companies.csv` には任意で `industry_raw`（大学が掲載した業種見出し）を付けられます。
  企業マスタはこの列と企業名から自動生成します（`data/real/_generated/`、手で編集しない）。
- 業種は大学の公開区分のまま書けば、取り込み時に標準区分（`app/industries.py`）へ寄せて合算します。
- 表記ゆれの統合は `_common/alias_merge.csv`（alias → 代表名）で補えます。
- 数値は公開資料に書かれた値だけを転記し、推計や補完はしません。人数が非公開なら空欄にします。
