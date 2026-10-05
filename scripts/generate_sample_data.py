"""デモ用サンプルCSVを生成する。

!!! 注意 !!!
ここで生成される人数・評価・順位などの数値はすべて **架空のデモ値** です。
大学・企業名は MVP 対象（仕様書 18章）に合わせていますが、実績を示すものではありません。
各行の source_id は reliability='DEMO' の Source_Log を指し、UI 上でもデモ表示されます。
実運用では data/ 配下に実データの CSV を用意し `python -m app.ingest <dir> --reset` で置換してください。
"""
import csv
import hashlib
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "sample"
YEARS = [2023, 2024]
LATEST = 2024
RETRIEVED = "2026-10-01"

UNIVERSITIES = [
    # id, name, region, pref, establishment, students, level, url, tier
    ("waseda", "早稲田大学", "関東", "東京都", "私立", 38000, "A", "https://www.waseda.jp/", 3),
    ("keio", "慶應義塾大学", "関東", "東京都", "私立", 28000, "B", "https://www.keio.ac.jp/", 3),
    ("meiji", "明治大学", "関東", "東京都", "私立", 30000, "A", "https://www.meiji.ac.jp/", 2),
    ("aoyama", "青山学院大学", "関東", "東京都", "私立", 18000, "A", "https://www.aoyama.ac.jp/", 2),
    ("rikkyo", "立教大学", "関東", "東京都", "私立", 19000, "A", "https://www.rikkyo.ac.jp/", 2),
    ("chuo", "中央大学", "関東", "東京都", "私立", 25000, "A", "https://www.chuo-u.ac.jp/", 2),
    ("hosei", "法政大学", "関東", "東京都", "私立", 27000, "A", "https://www.hosei.ac.jp/", 2),
    ("hitotsubashi", "一橋大学", "関東", "東京都", "国立", 4400, "C", "https://www.hit-u.ac.jp/", 3),
    ("tsukuba", "筑波大学", "関東", "茨城県", "国立", 9800, "B", "https://www.tsukuba.ac.jp/", 2),
    ("chiba", "千葉大学", "関東", "千葉県", "国立", 10000, "B", "https://www.chiba-u.ac.jp/", 2),
    ("kobe", "神戸大学", "関西", "兵庫県", "国立", 11500, "B", "https://www.kobe-u.ac.jp/", 3),
    ("doshisha", "同志社大学", "関西", "京都府", "私立", 26000, "A", "https://www.doshisha.ac.jp/", 2),
    ("kansai", "関西大学", "関西", "大阪府", "私立", 28000, "A", "https://www.kansai-u.ac.jp/", 2),
    ("kwansei", "関西学院大学", "関西", "兵庫県", "私立", 24000, "A", "https://www.kwansei.ac.jp/", 2),
    ("hiroshima", "広島大学", "中国", "広島県", "国立", 10500, "C", "https://www.hiroshima-u.ac.jp/", 2),
    ("fukuoka", "福岡大学", "九州", "福岡県", "私立", 19000, "B", "https://www.fukuoka-u.ac.jp/", 1),
]

FACULTIES = {
    "waseda": [("政治経済学部", "文系"), ("商学部", "文系"), ("人間科学部", "文理融合"), ("基幹理工学部", "理系")],
    "keio": [("経済学部", "文系"), ("商学部", "文系"), ("理工学部", "理系")],
    "meiji": [("商学部", "文系"), ("経営学部", "文系"), ("情報コミュニケーション学部", "文系"), ("理工学部", "理系")],
    "aoyama": [("経営学部", "文系"), ("国際政治経済学部", "文系"), ("理工学部", "理系")],
    "rikkyo": [("経営学部", "文系"), ("社会学部", "文系"), ("異文化コミュニケーション学部", "文系")],
    "chuo": [("商学部", "文系"), ("法学部", "文系"), ("国際情報学部", "文理融合"), ("理工学部", "理系")],
    "hosei": [("経営学部", "文系"), ("キャリアデザイン学部", "文系"), ("情報科学部", "理系")],
    "hitotsubashi": [("商学部", "文系"), ("経済学部", "文系"), ("ソーシャル・データサイエンス学部", "文理融合")],
    "tsukuba": [("社会・国際学群", "文系"), ("理工学群", "理系"), ("情報学群", "理系")],
    "chiba": [("法政経学部", "文系"), ("工学部", "理系"), ("教育学部", "文系")],
    "kobe": [("経営学部", "文系"), ("経済学部", "文系"), ("工学部", "理系")],
    "doshisha": [("商学部", "文系"), ("経済学部", "文系"), ("文化情報学部", "文理融合"), ("理工学部", "理系")],
    "kansai": [("商学部", "文系"), ("外国語学部", "文系"), ("社会学部", "文系"), ("システム理工学部", "理系")],
    "kwansei": [("商学部", "文系"), ("経済学部", "文系"), ("国際学部", "文系"), ("工学部", "理系")],
    "hiroshima": [("経済学部", "文系"), ("工学部", "理系"), ("総合科学部", "文理融合")],
    "fukuoka": [("商学部", "文系"), ("経済学部", "文系"), ("工学部", "理系")],
}

# company_id, 正式名, 業界, 採用人数, 初任給, 人気度(0-1), 地域限定(None=全国), tier下限
COMPANIES = [
    ("nitori", "株式会社ニトリ", "小売", 500, 300000, 0.75, None, 1),
    ("fastretailing", "株式会社ファーストリテイリング", "小売", 400, 330000, 0.8, None, 1),
    ("aeon", "イオンリテール株式会社", "小売", 600, 270000, 0.55, None, 1),
    ("ryohin", "株式会社良品計画", "小売", 150, 280000, 0.6, None, 1),
    ("seven", "株式会社セブン‐イレブン・ジャパン", "小売", 300, 270000, 0.45, None, 1),
    ("rakuten", "楽天グループ株式会社", "IT・通信", 500, 310000, 0.7, None, 1),
    ("nttdata", "株式会社NTTデータ", "IT・通信", 600, 300000, 0.85, None, 2),
    ("fujitsu", "富士通株式会社", "IT・通信", 900, 290000, 0.7, None, 2),
    ("nec", "日本電気株式会社", "IT・通信", 700, 290000, 0.6, None, 2),
    ("softbank", "ソフトバンク株式会社", "IT・通信", 600, 300000, 0.7, None, 1),
    ("cyberagent", "株式会社サイバーエージェント", "IT・通信", 300, 340000, 0.65, None, 2),
    ("recruit", "株式会社リクルート", "広告・メディア", 400, 330000, 0.75, None, 2),
    ("accenture", "アクセンチュア株式会社", "コンサル", 1500, 430000, 0.9, None, 2),
    ("deloitte", "デロイト トーマツ コンサルティング合同会社", "コンサル", 400, 450000, 0.8, None, 3),
    ("pwc", "PwCコンサルティング合同会社", "コンサル", 400, 450000, 0.75, None, 3),
    ("mufg", "株式会社三菱UFJ銀行", "金融", 800, 300000, 0.85, None, 1),
    ("smbc", "株式会社三井住友銀行", "金融", 700, 300000, 0.8, None, 1),
    ("mizuho", "株式会社みずほフィナンシャルグループ", "金融", 700, 300000, 0.75, None, 1),
    ("tokiomarine", "東京海上日動火災保険株式会社", "金融", 500, 290000, 0.8, None, 2),
    ("nomura", "野村證券株式会社", "金融", 400, 300000, 0.65, None, 2),
    ("fukuokafg", "株式会社ふくおかフィナンシャルグループ", "金融", 200, 250000, 0.4, "九州", 1),
    ("hirogin", "株式会社広島銀行", "金融", 120, 240000, 0.35, "中国", 1),
    ("mitsubishicorp", "三菱商事株式会社", "商社", 150, 330000, 0.9, None, 3),
    ("itochu", "伊藤忠商事株式会社", "商社", 140, 330000, 0.9, None, 3),
    ("ana", "全日本空輸株式会社", "航空・旅行", 300, 260000, 0.75, None, 1),
    ("jal", "日本航空株式会社", "航空・旅行", 250, 260000, 0.7, None, 1),
    ("jtb", "株式会社JTB", "航空・旅行", 200, 240000, 0.5, None, 1),
    ("sony", "ソニーグループ株式会社", "メーカー", 400, 300000, 0.85, None, 2),
    ("panasonic", "パナソニック株式会社", "メーカー", 500, 280000, 0.6, None, 2),
    ("kao", "花王株式会社", "メーカー", 150, 280000, 0.7, None, 2),
    ("toyota", "トヨタ自動車株式会社", "メーカー", 700, 290000, 0.8, None, 2),
    ("hitachi", "株式会社日立製作所", "メーカー", 800, 290000, 0.75, None, 2),
    ("mazda", "マツダ株式会社", "メーカー", 300, 260000, 0.45, "中国", 1),
    ("suntory", "サントリーホールディングス株式会社", "食品", 150, 280000, 0.85, None, 2),
    ("ajinomoto", "味の素株式会社", "食品", 100, 280000, 0.75, None, 2),
    ("yamato", "ヤマト運輸株式会社", "物流", 400, 250000, 0.35, None, 1),
    ("nipponexpress", "NIPPON EXPRESSホールディングス株式会社", "物流", 400, 260000, 0.4, None, 1),
    ("mitsuifudosan", "三井不動産株式会社", "不動産", 50, 320000, 0.8, None, 3),
    ("daiwahouse", "大和ハウス工業株式会社", "不動産", 700, 280000, 0.6, None, 1),
    ("kepco", "関西電力株式会社", "インフラ", 400, 260000, 0.55, "関西", 1),
    ("jrwest", "西日本旅客鉄道株式会社", "インフラ", 500, 250000, 0.6, "関西", 1),
    ("kyuden", "九州電力株式会社", "インフラ", 300, 250000, 0.5, "九州", 1),
    ("public", "公務（国家・地方）", "公務", None, None, 0.7, None, 1),
]

ALIASES = [
    ("ニトリ", "nitori"), ("ニトリホールディングス", "nitori"), ("ニトリグループ", "nitori"),
    ("ユニクロ", "fastretailing"), ("ファーストリテイリンググループ", "fastretailing"),
    ("NTT DATA", "nttdata"), ("エヌ・ティ・ティ・データ", "nttdata"),
    ("NEC", "nec"), ("MUFG", "mufg"), ("三菱ＵＦＪ銀行", "mufg"), ("SMBC", "smbc"),
    ("みずほ銀行", "mizuho"), ("ANA", "ana"), ("ANAホールディングス", "ana"), ("JAL", "jal"),
    ("日本通運", "nipponexpress"), ("JR西日本", "jrwest"), ("ソニー", "sony"),
    ("楽天", "rakuten"), ("国家公務員", "public"), ("地方公務員", "public"), ("公務員", "public"),
    ("福岡銀行", "fukuokafg"), ("サントリー", "suntory"),
]

# 原文表記ゆれのデモ（正規化で同一IDに統合されることを確認できる）
RAW_VARIANTS = {
    "nitori": ["ニトリ", "(株)ニトリ", "株式会社ニトリ", "ニトリグループ"],
    "fastretailing": ["ファーストリテイリング", "ユニクロ"],
    "mufg": ["三菱UFJ銀行", "三菱ＵＦＪ銀行"],
    "nttdata": ["NTTデータ", "エヌ・ティ・ティ・データ"],
    "public": ["国家公務員", "地方公務員"],
}
UNRESOLVED_NAMES = ["(株)ｱｲﾘｽｵｰﾔﾏ", "地元信用金庫"]  # 企業マスタ未登録 → 未正規化レポートに出る

INDUSTRY_PROFILE = {
    "商経": {"金融": 0.24, "メーカー": 0.14, "IT・通信": 0.14, "小売": 0.10, "コンサル": 0.08, "商社": 0.04,
             "不動産": 0.05, "広告・メディア": 0.05, "物流": 0.03, "インフラ": 0.04, "航空・旅行": 0.03, "食品": 0.04, "公務": 0.06},
    "法": {"金融": 0.18, "公務": 0.22, "メーカー": 0.10, "IT・通信": 0.12, "インフラ": 0.07, "小売": 0.07, "コンサル": 0.06,
           "不動産": 0.06, "商社": 0.03, "広告・メディア": 0.03, "航空・旅行": 0.03},
    "国際": {"航空・旅行": 0.14, "メーカー": 0.14, "商社": 0.07, "IT・通信": 0.15, "金融": 0.14, "小売": 0.10,
             "コンサル": 0.07, "物流": 0.05, "食品": 0.05, "広告・メディア": 0.04, "公務": 0.05},
    "社会": {"IT・通信": 0.18, "広告・メディア": 0.13, "小売": 0.12, "金融": 0.14, "メーカー": 0.09, "公務": 0.11,
             "不動産": 0.06, "航空・旅行": 0.05, "食品": 0.04, "コンサル": 0.05, "物流": 0.03},
    "情報": {"IT・通信": 0.42, "コンサル": 0.13, "メーカー": 0.14, "金融": 0.08, "広告・メディア": 0.08, "小売": 0.06, "公務": 0.04},
    "理工": {"メーカー": 0.38, "IT・通信": 0.28, "インフラ": 0.10, "コンサル": 0.06, "不動産": 0.05, "金融": 0.03, "小売": 0.03, "公務": 0.04},
    "教育": {"公務": 0.45, "金融": 0.10, "小売": 0.10, "IT・通信": 0.10, "メーカー": 0.08, "インフラ": 0.05, "航空・旅行": 0.04},
}


def profile_key(faculty):
    for key, words in [("情報", ["情報", "データサイエンス"]), ("理工", ["理工", "工学"]), ("国際", ["国際", "外国語", "異文化"]),
                       ("法", ["法学", "法政経"]), ("社会", ["社会", "人間科学", "キャリア", "総合科学"]), ("教育", ["教育"])]:
        if any(w in faculty for w in words):
            return key
    return "商経"


def rng_for(*parts):
    seed = int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)
    return random.Random(seed)


def write(name, header, rows):
    with (OUT / f"{name}.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    demo_note = "デモ用の架空値。実データ取得時に置換すること"
    sources = [
        ("demo-portraits", "https://portraits.niad.ac.jp/", "大学ポートレート", "government", RETRIEVED, "", LATEST, "sample", "DEMO", demo_note),
        ("demo-mext", "https://www.e-stat.go.jp/stat-search?toukei=00400001", "文部科学省 学校基本調査", "government", RETRIEVED, "", LATEST, "sample", "DEMO", demo_note),
        ("demo-onecareer", "https://www.onecareer.jp/", "ONE CAREER（公開メタデータ）", "review", RETRIEVED, "", 2026, "sample", "DEMO", demo_note + "。体験談本文は保存しない"),
        ("demo-survey-mynavi", "https://career-research.mynavi.jp/", "マイナビ 学生就職意識調査", "survey", RETRIEVED, "", 2026, "sample", "DEMO", demo_note),
        ("demo-survey-ranking", "https://career-research.mynavi.jp/", "就職人気企業ランキング", "survey", RETRIEVED, "", 2026, "sample", "DEMO", demo_note),
        ("demo-company", "https://www.nitori.co.jp/recruit/", "企業採用サイト（各社）", "company", RETRIEVED, "", 2026, "sample", "DEMO", demo_note),
    ]
    for uid, name, *_rest in UNIVERSITIES:
        url = _rest[5]
        sources.append((f"demo-{uid}-career", url, f"{name} 公式サイト（就職実績）", "university", RETRIEVED,
                        f"{LATEST + 1}-06-01", LATEST, "sample", "DEMO", demo_note))
    write("sources", ["source_id", "url", "source_name", "source_type", "retrieved_at", "published_at",
                      "target_year", "scope", "reliability", "note"], sources)

    write("universities", ["university_id", "name", "region", "prefecture", "establishment", "student_count",
                           "disclosure_level", "source_id"],
          [(u[0], u[1], u[2], u[3], u[4], u[5], u[6], "demo-portraits") for u in UNIVERSITIES])

    write("companies", ["company_id", "name", "industry", "hiring_count", "starting_salary", "locations",
                        "transfer_policy", "career_system", "recruit_url", "source_id"],
          [(c[0], c[1], c[2], c[3] or "", c[4] or "", "全国" if not c[6] else c[6] + "中心", "", "", "", "demo-company")
           for c in COMPANIES])
    write("company_aliases", ["alias", "company_id"], ALIASES)

    attrs = []
    tmpl = {
        "小売": {"勤務地": "全国の店舗・本部", "転勤": "全国転勤あり（ジョブローテーション）", "職種": "店舗運営→本部職（商品・物流・IT 等）",
                 "IT/DX": "EC・店舗DX", "グローバル": "海外店舗・調達", "商品企画": "あり（製造小売型は企画〜販売まで）", "若手裁量": "店長等で早期に事業運営"},
        "IT・通信": {"勤務地": "首都圏中心", "転勤": "限定的", "職種": "SE・コンサル・営業", "IT/DX": "中核事業", "グローバル": "海外拠点あり",
                     "商品企画": "サービス企画", "若手裁量": "プロジェクト単位"},
        "コンサル": {"勤務地": "首都圏中心", "転勤": "原則なし（出張あり）", "職種": "コンサルタント", "IT/DX": "DX支援が主力",
                     "グローバル": "グローバルファーム", "商品企画": "なし（支援側）", "若手裁量": "高い（成果主義）"},
        "金融": {"勤務地": "全国支店", "転勤": "あり（定期異動）", "職種": "総合職（法人・リテール・本部）", "IT/DX": "デジタル部門拡大中",
                 "グローバル": "海外拠点あり", "商品企画": "金融商品企画", "若手裁量": "段階的"},
        "メーカー": {"勤務地": "本社・工場・営業所", "転勤": "あり", "職種": "技術・営業・企画", "IT/DX": "製造DX", "グローバル": "海外売上比率高",
                     "商品企画": "あり", "若手裁量": "部門による"},
    }
    for c in COMPANIES:
        t = tmpl.get(c[2], {})
        vals = {
            "給与": f"大卒初任給 {c[4]:,}円（サンプル）" if c[4] else "—",
            "キャリア": "（要取得：採用サイトのキャリアパス記載）",
            "安定性": "（要取得：有価証券報告書）",
            "ブランド力": f"人気度指標 {int(c[5] * 100)}（サンプル）",
        }
        for k in ["勤務地", "転勤", "職種", "IT/DX", "グローバル", "商品企画", "若手裁量"]:
            vals[k] = t.get(k, "（要取得）")
        if c[0] == "nitori":
            vals.update({"キャリア": "配置転換を通じた複数職種経験（サンプル記述）",
                         "商品企画": "製造物流IT小売業として企画〜物流〜販売まで一気通貫（サンプル記述）",
                         "IT/DX": "自社IT部門・EC・SCM（サンプル記述）"})
        for k, v in vals.items():
            attrs.append((c[0], k, v, "demo-company"))
    write("company_attributes", ["company_id", "attribute", "value", "source_id"], attrs)

    fac_rows, outcome_rows, emp_rows, ind_rows = [], [], [], []
    for (uid, uname, region, _p, _e, students, level, _url, tier) in UNIVERSITIES:
        src = f"demo-{uid}-career"
        for i, (fname, field) in enumerate(FACULTIES[uid]):
            fid = f"{uid}-{i + 1:02d}"
            r = rng_for(fid)
            fstudents = int(students / len(FACULTIES[uid]) * r.uniform(0.6, 1.3))
            fac_rows.append((fid, uid, fname, "", field, fstudents, "demo-portraits"))
            profile = INDUSTRY_PROFILE[profile_key(fname)]
            for year in YEARS:
                ry = rng_for(fid, year)
                grads = int(fstudents / 4 * ry.uniform(0.9, 1.05))
                study_rate = 0.35 if field == "理系" and establishment_is_national(_e) else (0.25 if field == "理系" else 0.05)
                further = int(grads * study_rate * ry.uniform(0.8, 1.2))
                employed = int((grads - further) * ry.uniform(0.92, 0.98))
                rate = round(employed / max(1, grads - further) * 100, 1)
                outcome_rows.append((uid, fid, year, grads, employed, further, rate, src))
                if level in ("A", "B"):
                    weights = {k: v * ry.uniform(0.8, 1.2) for k, v in profile.items()}
                    total = sum(weights.values()) + 0.08
                    for ind, w in sorted(weights.items(), key=lambda x: -x[1]):
                        cnt = int(employed * w / total)
                        ind_rows.append((uid, fid, year, ind, cnt, round(cnt / employed, 4), src))
                    other = employed - sum(r_[4] for r_ in ind_rows if r_[1] == fid and r_[2] == year)
                    ind_rows.append((uid, fid, year, "その他", other, round(other / employed, 4), src))
                if level == "C":
                    continue
                if level == "B" and year != LATEST:
                    continue
                emp_rows.extend(company_rows(uid, fid, fname, region, tier, level, year, employed, profile, src))
    write("faculties", ["faculty_id", "university_id", "faculty", "department", "field", "student_count", "source_id"], fac_rows)
    write("career_outcomes", ["university_id", "faculty_id", "year", "graduates", "employed", "further_study",
                              "employment_rate", "source_id"], outcome_rows)
    write("employment_industries", ["university_id", "faculty_id", "year", "industry", "count", "ratio", "source_id"], ind_rows)
    write("employment_companies", ["university_id", "faculty_id", "year", "company_name_raw", "count", "listed", "source_id"], emp_rows)

    # 学生意識（重視点・忌避要因）: 架空値
    themes = {"安定": 38, "給与": 34, "やりたい仕事": 41, "キャリア": 27, "専門性": 18, "勤務地": 25,
              "転勤": 12, "福利厚生": 30, "成長": 29, "ワークライフバランス": 36}
    avoid = {"転勤が多い": 41, "ノルマがきつい": 46, "休日が少ない": 37, "給与が低い": 33, "キャリアが見えない": 22}
    ss = []
    for year in (2025, 2026):
        for seg, adj in (("全体", 0), ("文系", 1), ("理系", -1)):
            r = rng_for("ss", year, seg)
            for t, v in themes.items():
                bump = (3 if t == "専門性" else 0) * (-adj) + (2 if t in ("勤務地", "安定") else 0) * adj
                ss.append((year, seg, t, "企業選択で重視する割合", round(v + bump + r.uniform(-3, 3) + (year - 2025), 1), "%", "demo-survey-mynavi"))
            for t, v in avoid.items():
                ss.append((year, seg, t, "行きたくない会社の条件として選んだ割合", round(v + r.uniform(-4, 4), 1), "%", "demo-survey-mynavi"))
    write("student_signals", ["year", "segment", "theme", "metric", "value", "unit", "source_id"], ss)

    # ONE CAREER 等のメタデータシグナル + 人気ランキング: 架空値
    rv = []
    ranked = sorted([c for c in COMPANIES if c[0] != "public"], key=lambda c: -c[5])
    review_themes = ["勤務地・転勤", "給与・待遇", "キャリア可視性", "仕事内容", "成長環境", "働き方"]
    for rank, c in enumerate(ranked, 1):
        r = rng_for("rv", c[0])
        pop = c[5]
        rv.append((c[0], 2026, "全体", "", "favorites", int(pop * 30000 * r.uniform(0.7, 1.3)), "demo-onecareer"))
        rv.append((c[0], 2026, "全体", "", "rating", round(3.0 + pop * 1.5 + r.uniform(-0.3, 0.3), 2), "demo-onecareer"))
        rv.append((c[0], 2026, "全体", "", "selection_reviews", int(pop * 1200 * r.uniform(0.5, 1.5)), "demo-onecareer"))
        rv.append((c[0], 2026, "全体", "", "intern_reviews", int(pop * 800 * r.uniform(0.5, 1.5)), "demo-onecareer"))
        if rank <= 30:
            for seg in ("文系", "理系"):
                tech = c[2] in ("メーカー", "IT・通信")
                jitter = r.randint(-4, 4) + (-6 if (seg == "理系") == tech else 4)
                rv.append((c[0], 2026, seg, "", "popularity_rank", max(1, rank * 3 + jitter), "demo-survey-ranking"))
        for t in review_themes:
            base = {"勤務地・転勤": 40 if c[2] in ("小売", "金融") else 10}.get(t, 20)
            rv.append((c[0], 2026, "全体", t, "theme_mentions", int(base * pop * r.uniform(0.5, 1.5)), "demo-onecareer"))
    write("review_signals", ["company_id", "year", "segment", "theme", "signal_type", "value", "source_id"], rv)
    print(f"sample CSV written to {OUT}")


def establishment_is_national(e):
    return e == "国立"


def company_rows(uid, fid, fname, region, tier, level, year, employed, profile, src):
    r = rng_for("emp", fid, year)
    scored = []
    for c in COMPANIES:
        cid, _n, ind, _h, _s, pop, reg, min_tier = c
        if reg and reg != region:
            continue
        w = profile.get(ind, 0.01) * (0.4 + pop) * (1.0 if tier >= min_tier else 0.25)
        if cid == "nitori":
            # ニトリの掲載は学部ごとにばらつく（未掲載＝未開拓余地の検証用）
            w *= 1.6 if rng_for("nitori", fid).random() < 0.55 else 0.0
        if w > 0:
            scored.append((w * r.uniform(0.5, 1.5), c))
    scored.sort(key=lambda x: -x[0])
    top = scored[: 18 if level == "A" else 10]
    rows = []
    for w, c in top:
        names = RAW_VARIANTS.get(c[0], [c[1]])
        raw = names[r.randrange(len(names))]
        cnt = max(1, int(employed * w * 0.06)) if level == "A" else ""
        rows.append((uid, fid, year, raw, cnt, 1, src))
    if level == "A" and r.random() < 0.3:
        # 企業名のみ公開（人数 NULL）の行を混在させる
        rows.append((uid, fid, year, UNRESOLVED_NAMES[r.randrange(len(UNRESOLVED_NAMES))], "", 1, src))
    return rows


if __name__ == "__main__":
    main()
