"""分析エンジン：採用競合スコア（7章）と攻略優先度スコア（8章）。

スコアは「意思決定の補助」であり絶対評価ではない。すべての重みとシグナル内訳を
API で返し、なぜその値になったかを画面上で説明できるようにする。
"""
import math
from collections import defaultdict

from . import config, db

# Signal 6: 志望業界の近接性。自社業界（キー）から見た各業界の近さ（0-1）。
INDUSTRY_PROXIMITY = {
    "小売": {"小売": 1.0, "IT・通信": 0.7, "メーカー": 0.7, "物流": 0.7, "食品": 0.6, "商社": 0.6,
             "コンサル": 0.5, "金融": 0.5, "広告・メディア": 0.5, "航空・旅行": 0.5, "不動産": 0.4,
             "インフラ": 0.4, "公務": 0.3},
}
DEFAULT_PROXIMITY = 0.3

# 8章「業界適合性」：小売・IT・メーカー・金融等との親和性
FIT_INDUSTRIES = {"小売", "IT・通信", "メーカー", "金融"}

COMPETITION_WEIGHTS = {
    "s1_faculty_presence": 0.20,   # Signal 1: 当該学部での就職先重複
    "s2_cooccurrence": 0.30,       # Signal 2: 自社掲載学部での同時出現頻度
    "s3_multi_university": 0.15,   # Signal 3: 複数大学での同時出現
    "s4_student_interest": 0.10,   # Signal 4: ONE CAREER 等での学生関心度
    "s5_popularity": 0.10,         # Signal 5: 就職人気ランキング
    "s6_industry_proximity": 0.15, # Signal 6: 志望業界の近接性
}
SIGNAL_LABELS = {
    "s1_faculty_presence": "学部内就職先重複",
    "s2_cooccurrence": "自社掲載学部での同時出現",
    "s3_multi_university": "複数大学での出現",
    "s4_student_interest": "学生関心度（ONE CAREER）",
    "s5_popularity": "就職人気ランキング",
    "s6_industry_proximity": "業界近接性",
}

OPPORTUNITY_WEIGHTS = {  # 合計 100
    "market_size": 20, "market_power": 15, "affinity": 20, "competition_market": 15,
    "industry_fit": 10, "untapped": 10, "reliability": 10,
}
OPPORTUNITY_LABELS = {
    "market_size": "市場規模", "market_power": "就職市場力", "affinity": "自社親和性",
    "competition_market": "競合市場性", "industry_fit": "業界適合性", "untapped": "未開拓余地",
    "reliability": "データ信頼度",
}
RELIABILITY = {"A": 1.0, "B": 0.6, "C": 0.3}
NEUTRAL = 0.4  # データ欠損時の中立値（欠損を 0 とみなさない）


class Analytics:
    """DB 全体を読み込んで指標を計算する。MVP 規模（数十大学）ではリクエスト毎に生成して十分高速。"""

    def __init__(self, conn, target_id=None):
        self.conn = conn
        self.target_id = target_id or config.TARGET_COMPANY_ID
        self._load()

    # ------------------------------------------------------------------ load
    def _load(self):
        c = self.conn
        self.universities = {r["university_id"]: r for r in db.rows(c, "SELECT * FROM university_master")}
        self.faculties = {r["faculty_id"]: r for r in db.rows(c, "SELECT * FROM faculty_master")}
        self.companies = {r["company_id"]: r for r in db.rows(c, "SELECT * FROM company_master")}
        self.target = self.companies.get(self.target_id) or {"company_id": self.target_id, "name": self.target_id, "industry": None}
        self.proximity = INDUSTRY_PROXIMITY.get(self.target.get("industry"), {})

        self.outcomes = defaultdict(list)
        for r in db.rows(c, "SELECT * FROM career_outcome ORDER BY year"):
            self.outcomes[r["faculty_id"]].append(r)

        self.industries = defaultdict(lambda: defaultdict(list))  # fid -> year -> rows
        for r in db.rows(c, "SELECT * FROM employment_industry ORDER BY count DESC"):
            self.industries[r["faculty_id"]][r["year"]].append(r)

        # 学部ごとに最新年度の就職先を採用（年度を混ぜない）
        latest = {r["faculty_id"]: r["y"] for r in db.rows(
            c, "SELECT faculty_id, MAX(year) y FROM employment_company GROUP BY faculty_id")}
        self.emp_year = latest
        self.fac_companies = defaultdict(dict)   # fid -> cid -> {count, raw}
        self.unresolved = defaultdict(list)
        for r in db.rows(c, "SELECT * FROM employment_company WHERE listed=1"):
            if latest.get(r["faculty_id"]) != r["year"]:
                continue
            if not r["company_id"]:
                self.unresolved[r["faculty_id"]].append(r)
                continue
            cur = self.fac_companies[r["faculty_id"]].setdefault(
                r["company_id"], {"count": None, "raw": [], "source_id": r["source_id"]})
            if r["count"] is not None:
                cur["count"] = (cur["count"] or 0) + r["count"]
            cur["raw"].append(r["company_name_raw"])

        self.company_facs = defaultdict(set)
        self.company_unis = defaultdict(set)
        for fid, comps in self.fac_companies.items():
            uid = self.faculties[fid]["university_id"]
            for cid in comps:
                self.company_facs[cid].add(fid)
                self.company_unis[cid].add(uid)
        self.target_facs = self.company_facs.get(self.target_id, set())
        self.unis_with_company_data = {self.faculties[f]["university_id"] for f in self.fac_companies}

        self.signals = defaultdict(dict)
        self.theme_mentions = defaultdict(dict)
        for r in db.rows(c, "SELECT * FROM review_signal ORDER BY year"):
            if r["signal_type"] == "theme_mentions":
                self.theme_mentions[r["company_id"]][r["theme"]] = r["value"]
            elif r["signal_type"] == "popularity_rank":
                self.signals[r["company_id"]][f"rank_{r['segment']}"] = r["value"]
            else:
                self.signals[r["company_id"]][r["signal_type"]] = r["value"]
        favs = [s.get("favorites") or 0 for s in self.signals.values()]
        self.max_favorites = max(favs) if favs else 0

        self._global_cache = {}
        self._opportunity_cache = None

    # ------------------------------------------------------------- helpers
    def latest_outcome(self, fid):
        o = self.outcomes.get(fid)
        return o[-1] if o else None

    def latest_industries(self, fid):
        years = self.industries.get(fid)
        if not years:
            return None, []
        y = max(years)
        return y, years[y]

    def disclosure_level(self, fid):
        return self.universities[self.faculties[fid]["university_id"]]["disclosure_level"]

    def faculty_label(self, fid):
        f = self.faculties[fid]
        u = self.universities[f["university_id"]]
        return f"{u['name']} {f['faculty']}" + (f" {f['department']}" if f.get("department") else "")

    def best_rank(self, cid):
        s = self.signals.get(cid, {})
        ranks = [v for k, v in s.items() if k.startswith("rank_") and v]
        return min(ranks) if ranks else None

    # ------------------------------------------------ competition (7章)
    def global_signals(self, cid):
        if cid in self._global_cache:
            return self._global_cache[cid]
        facs = self.company_facs.get(cid, set())
        co = len(facs & self.target_facs)
        s2 = co / len(self.target_facs) if self.target_facs else 0.0
        s3 = len(self.company_unis.get(cid, ())) / max(1, len(self.unis_with_company_data))
        fav = self.signals.get(cid, {}).get("favorites")
        s4 = (fav / self.max_favorites) if (fav and self.max_favorites) else 0.0
        rank = self.best_rank(cid)
        s5 = max(0.0, 1 - (rank - 1) / 100) if rank else 0.0
        ind = self.companies.get(cid, {}).get("industry")
        s6 = self.proximity.get(ind, DEFAULT_PROXIMITY)
        out = {"s2_cooccurrence": s2, "s3_multi_university": s3, "s4_student_interest": s4,
               "s5_popularity": s5, "s6_industry_proximity": s6,
               "_cooccurrence_count": co, "_university_count": len(self.company_unis.get(cid, ())),
               "_faculty_count": len(facs)}
        self._global_cache[cid] = out
        return out

    def competition_score(self, cid, fid=None):
        g = self.global_signals(cid)
        sig = {k: v for k, v in g.items() if not k.startswith("_")}
        if fid is not None:
            comps = self.fac_companies.get(fid, {})
            if cid in comps:
                counts = [v["count"] for v in comps.values() if v["count"] is not None]
                cnt = comps[cid]["count"]
                share = (cnt / max(counts)) if (cnt is not None and counts) else 0.5  # 人数非公開は中立
                sig["s1_faculty_presence"] = 0.5 + 0.5 * share
            else:
                sig["s1_faculty_presence"] = 0.0
            weights = COMPETITION_WEIGHTS
        else:
            # 学部を指定しない（全体）場合は s1 を除いて再正規化
            weights = {k: v for k, v in COMPETITION_WEIGHTS.items() if k != "s1_faculty_presence"}
        total_w = sum(weights.values())
        score = sum(sig[k] * w for k, w in weights.items()) / total_w * 100
        breakdown = [{"key": k, "label": SIGNAL_LABELS[k], "value": round(sig[k], 3),
                      "weight": round(w / total_w, 3), "contribution": round(sig[k] * w / total_w * 100, 1)}
                     for k, w in weights.items()]
        return round(score, 1), breakdown

    def company_row(self, cid, fid=None):
        comp = self.companies.get(cid, {"name": cid, "industry": None})
        g = self.global_signals(cid)
        score, breakdown = self.competition_score(cid, fid)
        s = self.signals.get(cid, {})
        row = {
            "company_id": cid, "name": comp["name"], "industry": comp.get("industry"),
            "cooccurrence_count": g["_cooccurrence_count"], "university_count": g["_university_count"],
            "faculty_count": g["_faculty_count"],
            "favorites": s.get("favorites"), "rating": s.get("rating"),
            "selection_reviews": s.get("selection_reviews"), "intern_reviews": s.get("intern_reviews"),
            "popularity_rank": self.best_rank(cid),
            "score": score, "breakdown": breakdown,
        }
        if fid is not None and cid in self.fac_companies.get(fid, {}):
            row["count_in_faculty"] = self.fac_companies[fid][cid]["count"]
        return row

    def faculty_competitors(self, fid, limit=10):
        rows = [self.company_row(cid, fid) for cid in self.fac_companies.get(fid, {}) if cid != self.target_id]
        rows.sort(key=lambda r: -r["score"])
        return rows[:limit]

    def global_competitors(self, limit=20):
        cids = {c for f in self.target_facs for c in self.fac_companies[f]} - {self.target_id}
        rows = [self.company_row(cid) for cid in cids]
        rows.sort(key=lambda r: -r["score"])
        return rows[:limit]

    # ------------------------------------------------ opportunity (8章)
    def _industry_affinity_raw(self, fid):
        _, inds = self.latest_industries(fid)
        if inds:
            return sum((r["ratio"] or 0) * self.proximity.get(r["industry"], DEFAULT_PROXIMITY)
                       for r in inds if r["industry"] != "その他")
        comps = self.fac_companies.get(fid)
        if comps:  # 業種データがない場合は掲載企業の業種から推定
            vals = [self.proximity.get(self.companies[c]["industry"], DEFAULT_PROXIMITY) for c in comps if c in self.companies]
            return sum(vals) / len(vals) * 0.8 if vals else None
        return None

    def _fit_share(self, fid):
        _, inds = self.latest_industries(fid)
        if not inds:
            return None
        return sum((r["ratio"] or 0) for r in inds if r["industry"] in FIT_INDUSTRIES)

    def _market_power(self, fid):
        comps = self.fac_companies.get(fid)
        if not comps:
            return None
        major = {cid for cid in comps if self.best_rank(cid)}
        out = self.latest_outcome(fid)
        counts_known = all(v["count"] is not None for v in comps.values())
        if counts_known and out and out["employed"]:
            return min(1.0, sum(comps[c]["count"] for c in major) / out["employed"] / 0.35)
        return len(major) / len(comps) * 0.8

    def opportunity_all(self):
        if self._opportunity_cache is not None:
            return self._opportunity_cache
        fids = list(self.faculties)
        grads = {f: (self.latest_outcome(f) or {}).get("graduates") for f in fids}
        max_log = max((math.log1p(g) for g in grads.values() if g), default=1)
        aff_raw = {f: self._industry_affinity_raw(f) for f in fids}
        max_aff = max((v for v in aff_raw.values() if v is not None), default=1) or 1
        fit = {f: self._fit_share(f) for f in fids}
        max_fit = max((v for v in fit.values() if v is not None), default=1) or 1

        results = {}
        for f in fids:
            listed = f in self.target_facs
            has_company_data = bool(self.fac_companies.get(f))
            ind_aff = aff_raw[f] / max_aff if aff_raw[f] is not None else None
            comps = self.faculty_competitors(f, limit=5)
            comp_strength = sum(c["score"] for c in comps) / len(comps) if comps else None
            comp = {
                "market_size": math.log1p(grads[f]) / max_log if grads[f] else NEUTRAL,
                "market_power": self._market_power(f),
                "affinity": None,
                "competition_market": comp_strength / 100 if comp_strength is not None else None,
                "industry_fit": fit[f] / max_fit if fit[f] is not None else None,
                "untapped": None,
                "reliability": RELIABILITY.get(self.disclosure_level(f), 0.3),
            }
            if has_company_data:
                comp["affinity"] = 0.5 * (1.0 if listed else 0.0) + 0.5 * (ind_aff if ind_aff is not None else NEUTRAL)
                comp["untapped"] = (ind_aff if ind_aff is not None else NEUTRAL) if not listed else 0.3
            elif ind_aff is not None:
                comp["affinity"] = 0.5 * ind_aff + 0.5 * NEUTRAL  # 掲載有無が不明
            missing = [k for k, v in comp.items() if v is None]
            comp = {k: (NEUTRAL if v is None else v) for k, v in comp.items()}
            total = sum(comp[k] * w for k, w in OPPORTUNITY_WEIGHTS.items())
            results[f] = {
                "score": round(total, 1),
                "components": {k: round(v, 3) for k, v in comp.items()},
                "missing": missing,
                "target_listed": listed if has_company_data else None,
                "competition_strength": round(comp_strength, 1) if comp_strength is not None else None,
                "market_fit": round((comp["affinity"] + comp["industry_fit"]) / 2 * 100, 1),
                "top_competitors": [{"company_id": c["company_id"], "name": c["name"], "score": c["score"]} for c in comps[:3]],
            }
        # 優先度は相対評価（上位20%=A, 次30%=B, 次30%=C, 残り=D）
        ordered = sorted(results, key=lambda f: -results[f]["score"])
        n = len(ordered)
        strengths = sorted(r["competition_strength"] for r in results.values() if r["competition_strength"] is not None)
        self.competition_median = strengths[len(strengths) // 2] if strengths else None
        for i, f in enumerate(ordered):
            q = i / max(1, n)
            results[f]["grade"] = "A" if q < 0.2 else "B" if q < 0.5 else "C" if q < 0.8 else "D"
            results[f]["rank"] = i + 1
            results[f]["recommended_action"] = self.recommend_action(f, results[f])
        self._opportunity_cache = results
        return results

    def recommend_action(self, fid, res):
        comp = res["components"]
        level = self.disclosure_level(fid)
        if level == "C" or res["target_listed"] is None:
            return "公開情報が限定的：キャリアセンター訪問等で就職先データを取得"
        if not res["target_listed"] and comp["untapped"] >= 0.7:
            return "新規開拓：学部向け説明会・OB/OG発掘で接点づくり"
        median = getattr(self, "competition_median", None)
        if res["target_listed"] and median is not None and (res["competition_strength"] or 0) >= median:
            return "差別化訴求：競合比較型リクルータートーク・キャリアパス可視化"
        if res["target_listed"]:
            return "関係深化：既存ルート強化・同学部内定者/若手社員の活用"
        return "テスト施策：テーマ型イベントで反応を検証"

    def ranking(self, filters=None):
        filters = filters or {}
        opp = self.opportunity_all()
        out = []
        for fid, res in opp.items():
            f = self.faculties[fid]
            u = self.universities[f["university_id"]]
            o = self.latest_outcome(fid) or {}
            row = {
                "faculty_id": fid, "university_id": u["university_id"], "university": u["name"],
                "faculty": f["faculty"], "department": f.get("department"), "field": f.get("field"),
                "region": u["region"], "establishment": u["establishment"],
                "disclosure_level": u["disclosure_level"], "graduates": o.get("graduates"),
                **{k: res[k] for k in ("score", "grade", "rank", "market_fit", "target_listed",
                                       "competition_strength", "recommended_action", "top_competitors", "missing")},
                "components": res["components"],
            }
            if not _match(row, fid, filters, self):
                continue
            out.append(row)
        out.sort(key=lambda r: -r["score"])
        return out


def _match(row, fid, f, a: Analytics):
    if f.get("region") and row["region"] != f["region"]:
        return False
    if f.get("establishment"):
        want = f["establishment"]
        if want == "国公立" and row["establishment"] not in ("国立", "公立"):
            return False
        if want not in ("国公立",) and row["establishment"] != want:
            return False
    if f.get("field") and row["field"] != f["field"]:
        return False
    if f.get("q"):
        q = f["q"]
        if q not in row["university"] and q not in row["faculty"]:
            return False
    if f.get("faculty") and f["faculty"] not in row["faculty"]:
        return False
    if f.get("min_graduates") and (row["graduates"] or 0) < int(f["min_graduates"]):
        return False
    if f.get("competitor") and f["competitor"] not in a.fac_companies.get(fid, {}):
        return False
    if f.get("target_listed") in ("yes", "no"):
        want = f["target_listed"] == "yes"
        if row["target_listed"] is None or row["target_listed"] != want:
            return False
    return True
