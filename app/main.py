"""FastAPI アプリ。起動: uvicorn app.main:app --reload"""
from collections import Counter, defaultdict
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai, config, db
from .analytics import (COMPETITION_WEIGHTS, OPPORTUNITY_LABELS, OPPORTUNITY_WEIGHTS, SIGNAL_LABELS, Analytics)

app = FastAPI(title="採用マーケティング・インテリジェンス", version="0.1.0")
_conn = None


def get_conn():
    global _conn
    if _conn is None:
        _conn = db.connect()
        db.init_schema(_conn)
    return _conn


def get_analytics(conn=Depends(get_conn)) -> Analytics:
    return Analytics(conn)


def _sources(conn, ids):
    ids = sorted({i for i in ids if i})
    if not ids:
        return []
    q = ",".join("?" * len(ids))
    return db.rows(conn, f"SELECT * FROM source_log WHERE source_id IN ({q})", ids)


# ------------------------------------------------------------------ meta
@app.get("/api/meta")
def meta(a: Analytics = Depends(get_analytics)):
    demo = db.one(a.conn, "SELECT COUNT(*) n FROM source_log WHERE reliability='DEMO'")["n"]
    return {
        "target": a.target,
        "demo_data": demo > 0,
        "counts": {"universities": len(a.universities), "faculties": len(a.faculties), "companies": len(a.companies)},
        "regions": sorted({u["region"] for u in a.universities.values() if u["region"]}),
        "fields": sorted({f["field"] for f in a.faculties.values() if f["field"]}),
        "weights": {"competition": [{"key": k, "label": SIGNAL_LABELS[k], "weight": w,
                                     "available": k not in a.unavailable_signals} for k, w in COMPETITION_WEIGHTS.items()],
                    "opportunity": [{"key": k, "label": OPPORTUNITY_LABELS[k], "weight": w} for k, w in OPPORTUNITY_WEIGHTS.items()]},
        "competitor_options": [{"company_id": c["company_id"], "name": c["name"]} for c in a.global_competitors(30)],
        "ai_enabled": config.AI_ENABLED,
    }


# ------------------------------------------------------------------ search
@app.get("/api/search")
def search(q: str = "", a: Analytics = Depends(get_analytics)):
    q = q.strip()
    unis = [u for u in a.universities.values() if not q or q in u["name"]]
    out = []
    for u in sorted(unis, key=lambda u: u["name"]):
        facs = [{"faculty_id": f["faculty_id"], "faculty": f["faculty"], "department": f["department"], "field": f["field"]}
                for f in a.faculties.values() if f["university_id"] == u["university_id"]]
        out.append({**u, "faculties": facs})
    # 学部名での検索（例: 「商学部」）
    if q and not unis:
        for f in a.faculties.values():
            if q in f["faculty"]:
                u = a.universities[f["university_id"]]
                out.append({**u, "faculties": [{"faculty_id": f["faculty_id"], "faculty": f["faculty"],
                                                "department": f["department"], "field": f["field"]}]})
    return out


# ------------------------------------------------------------------ 9-1 ランキング
@app.get("/api/ranking")
def ranking(region: Optional[str] = None, establishment: Optional[str] = None, field: Optional[str] = None,
            faculty: Optional[str] = None, q: Optional[str] = None, min_graduates: Optional[int] = None,
            competitor: Optional[str] = None, target_listed: Optional[str] = None,
            a: Analytics = Depends(get_analytics)):
    filters = {k: v for k, v in dict(region=region, establishment=establishment, field=field, faculty=faculty, q=q,
                                      min_graduates=min_graduates, competitor=competitor,
                                      target_listed=target_listed).items() if v not in (None, "")}
    return {"filters": filters, "rows": a.ranking(filters)}


# ------------------------------------------------------------------ 10 学部詳細
@app.get("/api/faculties/{fid}")
def faculty_detail(fid: str, a: Analytics = Depends(get_analytics)):
    if fid not in a.faculties:
        raise HTTPException(404, "学部が見つかりません")
    f = a.faculties[fid]
    u = a.universities[f["university_id"]]
    opp = a.opportunity_all()[fid]
    comps = a.fac_companies.get(fid, {})
    companies = sorted(
        [{"company_id": cid, "name": a.companies[cid]["name"], "industry": a.companies[cid]["industry"],
          "count": v["count"], "raw_names": sorted(set(v["raw"])), "source_id": v["source_id"]} for cid, v in comps.items()],
        key=lambda r: (r["count"] is None, -(r["count"] or 0), r["name"]))
    unresolved = [{"raw_name": r["company_name_raw"], "count": r["count"], "source_id": r["source_id"]}
                  for r in a.unresolved.get(fid, [])]
    industries_by_year = {y: rows for y, rows in sorted(a.industries.get(fid, {}).items())}
    tgt = comps.get(a.target_id)
    tgt_ind = a.target.get("industry")
    neighbors = [c for c in companies if c["company_id"] != a.target_id and c["industry"] == tgt_ind]
    ind_year, inds = a.latest_industries(fid)
    proximity = [{"industry": r["industry"], "ratio": r["ratio"], "proximity": a.proximity.get(r["industry"])}
                 for r in inds if r["industry"] != tgt_ind and (a.proximity.get(r["industry"]) or 0) >= 0.6]
    src_ids = [f["source_id"], u["source_id"]] + [o["source_id"] for o in a.outcomes.get(fid, [])] \
        + [c["source_id"] for c in companies] + [r["source_id"] for rows in industries_by_year.values() for r in rows]
    return {
        "faculty": f, "university": u, "label": a.faculty_label(fid),
        "outcomes": a.outcomes.get(fid, []),
        "employment_year": a.emp_year.get(fid),
        "companies": companies, "unresolved_companies": unresolved,
        "industries_by_year": industries_by_year,
        "target": {
            "company_id": a.target_id, "name": a.target["name"],
            "listed": (tgt is not None) if comps else None,
            "count": tgt["count"] if tgt else None,
            "raw_names": sorted(set(tgt["raw"])) if tgt else [],
            "neighbors": neighbors, "proximity": proximity, "proximity_year": ind_year,
        },
        "opportunity": opp,
        "competitors": a.faculty_competitors(fid, 10),
        "sources": _sources(a.conn, src_ids),
    }


# ------------------------------------------------------------------ 11 競合企業詳細
@app.get("/api/companies/{cid}")
def company_detail(cid: str, faculty_id: Optional[str] = None, a: Analytics = Depends(get_analytics)):
    if cid not in a.companies:
        raise HTTPException(404, "企業が見つかりません")
    c = a.companies[cid]
    facs = a.company_facs.get(cid, set())
    overlap = sorted(facs & a.target_facs)
    overlap_rows = [{"faculty_id": f, "label": a.faculty_label(f), "count": a.fac_companies[f][cid]["count"],
                     "target_count": a.fac_companies[f][a.target_id]["count"]} for f in overlap]
    regions = Counter(a.universities[a.faculties[f]["university_id"]]["region"] for f in facs)
    fields = Counter(a.faculties[f]["field"] for f in facs)
    attrs_c = {r["attribute"]: r for r in db.rows(a.conn, "SELECT * FROM company_attribute WHERE company_id=?", (cid,))}
    attrs_t = {r["attribute"]: r for r in db.rows(a.conn, "SELECT * FROM company_attribute WHERE company_id=?", (a.target_id,))}
    order = ["給与", "勤務地", "転勤", "キャリア", "職種", "IT/DX", "グローバル", "商品企画", "若手裁量", "安定性", "ブランド力"]
    keys = order + sorted(set(attrs_c) | set(attrs_t) - set(order))
    comparison = [{"attribute": k,
                   "target": (attrs_t.get(k) or {}).get("value"), "target_source": (attrs_t.get(k) or {}).get("source_id"),
                   "competitor": (attrs_c.get(k) or {}).get("value"), "competitor_source": (attrs_c.get(k) or {}).get("source_id")}
                  for k in keys if k in attrs_c or k in attrs_t]
    st, sc = a.signals.get(a.target_id, {}), a.signals.get(cid, {})
    signal_cmp = [{"signal": label, "target": st.get(key), "competitor": sc.get(key)} for key, label in [
        ("favorites", "ONE CAREER お気に入り数"), ("rating", "ONE CAREER 評価"), ("selection_reviews", "選考体験談数"),
        ("intern_reviews", "インターン体験談数"), ("rank_文系", "人気ランキング（文系）"), ("rank_理系", "人気ランキング（理系）")]]
    signal_cmp.insert(0, {"signal": "大卒初任給（円）", "target": a.target.get("starting_salary"), "competitor": c.get("starting_salary")})
    row = a.company_row(cid, faculty_id if faculty_id in a.faculties else None)
    src_ids = [c["source_id"]] + [r["source_id"] for r in attrs_c.values()] + [r["source_id"] for r in attrs_t.values()]
    src_ids += [r["source_id"] for r in db.rows(a.conn, "SELECT DISTINCT source_id FROM review_signal WHERE company_id IN (?,?)", (cid, a.target_id))]
    return {
        "company": c, "attributes": attrs_c, "competition": row,
        "overlap_faculties": overlap_rows,
        "overlap_universities": sorted({a.universities[a.faculties[f]["university_id"]]["name"] for f in overlap}),
        "appearance": {"faculties": len(facs), "universities": len(a.company_unis.get(cid, ())),
                       "regions": dict(regions), "fields": dict(fields)},
        "signals": sc, "theme_mentions": a.theme_mentions.get(cid, {}),
        "target_theme_mentions": a.theme_mentions.get(a.target_id, {}),
        "comparison": comparison, "signal_comparison": signal_cmp,
        "target": {"company_id": a.target_id, "name": a.target["name"]},
        "sources": _sources(a.conn, src_ids),
    }


@app.get("/api/competitors")
def competitors(limit: int = 20, a: Analytics = Depends(get_analytics)):
    return a.global_competitors(limit)


# ------------------------------------------------------------------ 12 学生インサイト
@app.get("/api/insights")
def insights(segment: str = "全体", a: Analytics = Depends(get_analytics)):
    rows = db.rows(a.conn, "SELECT * FROM student_signal WHERE segment=? ORDER BY year, value DESC", (segment,))
    years = sorted({r["year"] for r in rows})
    latest = years[-1] if years else None
    prev = years[-2] if len(years) > 1 else None
    by = defaultdict(dict)
    for r in rows:
        by[(r["metric"], r["theme"])][r["year"]] = r
    metrics = defaultdict(list)
    for (metric, theme), ys in by.items():
        cur = ys.get(latest)
        if not cur:
            continue
        p = ys.get(prev)
        metrics[metric].append({"theme": theme, "value": cur["value"], "unit": cur["unit"],
                                "delta": round(cur["value"] - p["value"], 1) if p and p["value"] is not None else None,
                                "source_id": cur["source_id"]})
    for m in metrics.values():
        m.sort(key=lambda r: -(r["value"] or 0))
    comps = [a.target_id] + [c["company_id"] for c in a.global_competitors(5)]
    themes = sorted({t for c in comps for t in a.theme_mentions.get(c, {})})
    review = [{"company_id": c, "name": a.companies[c]["name"],
               "mentions": {t: a.theme_mentions.get(c, {}).get(t) for t in themes}} for c in comps if c in a.companies]
    src = {r["source_id"] for r in rows} | {"demo-onecareer"}
    return {"segment": segment, "year": latest, "prev_year": prev, "metrics": metrics,
            "review_themes": themes, "review": review, "sources": _sources(a.conn, src)}


class ClassifyIn(BaseModel):
    texts: List[str]
    use_ai: bool = True


@app.post("/api/classify")
def classify(body: ClassifyIn):
    return ai.classify_texts(body.texts, use_ai=body.use_ai)


# ------------------------------------------------------------------ 13 攻略提案
@app.get("/api/strategy/{fid}")
def strategy(fid: str, use_ai: bool = Query(True), a: Analytics = Depends(get_analytics)):
    if fid not in a.faculties:
        raise HTTPException(404, "学部が見つかりません")
    out = ai.generate_strategy(a, fid, use_ai=use_ai)
    out["label"] = a.faculty_label(fid)
    out["opportunity"] = a.opportunity_all()[fid]
    return out


# ------------------------------------------------------------------ データ管理
@app.get("/api/sources")
def sources(a: Analytics = Depends(get_analytics)):
    rows = db.rows(a.conn, "SELECT * FROM source_log ORDER BY source_type, source_id")
    unresolved = Counter(r["company_name_raw"] for rs in a.unresolved.values() for r in rs)
    levels = Counter(u["disclosure_level"] for u in a.universities.values())
    return {"sources": rows, "unresolved_company_names": [{"raw_name": k, "rows": v} for k, v in unresolved.most_common()],
            "disclosure_levels": dict(levels),
            "universities": sorted(a.universities.values(), key=lambda u: (u["disclosure_level"], u["name"]))}


app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html")
