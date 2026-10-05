"""AI（Claude）による仮説生成（14章）。

AI に任せるもの: 要約・競合候補整理・学生市場特徴・テーマ分類・比較・訴求仮説・施策案
AI に任せないもの: 根拠のない応募人数推定・架空の併願率/辞退率・体験談1件からの一般化・出典のない事実生成

API キーが未設定・呼び出し失敗時は、同じスキーマのルールベース出力にフォールバックする。
"""
import hashlib
import json
import logging
from datetime import datetime, timezone

from . import config, db
from .insights import THEMES, classify_keywords

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """あなたは新卒採用のマーケティング・アナリストです。
与えられた「公開情報から集計したデータ（JSON）」だけを根拠に、自社（{target}）が対象の大学・学部の学生市場を
どう攻略すべきかの仮説を日本語で作成します。

厳守するルール:
- 事実として書いてよいのは入力データにある内容だけです。各主張には根拠となる入力データの source_id を evidence に付けてください。
- 入力に無い数値（応募者数・併願率・辞退率・内定承諾率など）を推定・創作してはいけません。
- 人数が null の就職先は「人数非公開」であり 0 人ではありません。
- 学生意識調査は母集団全体の傾向です。この学部の学生の意見として断定せず「一般的傾向として」と扱ってください。
- ONE CAREER 等の件数は応募者数ではありません。関心度のシグナルとしてのみ扱ってください。
- 推奨訴求・施策は「仮説」です。断定せず、検証方法が分かる書き方にしてください。
- データの reliability が DEMO の場合は caveats に「デモデータに基づく」旨を必ず含めてください。
- 簡潔に。各項目は1〜2文で。"""

STRATEGY_SCHEMA = {
    "type": "object",
    "properties": {
        "priority_comment": {"type": "string"},
        "market_summary": {"type": "string"},
        "market_characteristics": {"type": "array", "items": {"type": "string"}},
        "competitor_view": {"type": "string"},
        "student_values": {"type": "string"},
        "target_affinity": {"type": "string"},
        "issues": {"type": "array", "items": {"type": "string"}},
        "appeal_hypotheses": {"type": "array", "items": {"type": "string"}},
        "actions": {"type": "array", "items": {"type": "string"}},
        "validation": {"type": "array", "items": {"type": "string"}},
        "caveats": {"type": "array", "items": {"type": "string"}},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"claim": {"type": "string"}, "source_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["claim", "source_ids"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["priority_comment", "market_summary", "market_characteristics", "competitor_view", "student_values",
                 "target_affinity", "issues", "appeal_hypotheses", "actions", "validation", "caveats", "evidence"],
    "additionalProperties": False,
}

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "themes": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["index", "themes"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


def _client():
    if not config.AI_ENABLED:
        return None
    try:
        import anthropic
        return anthropic.Anthropic()
    except Exception as e:  # 認証情報なし等
        log.info("Claude client unavailable: %s", e)
        return None


def _call_json(system, user, schema, max_tokens=16000):
    """Claude を呼び出して JSON を返す。使えなければ None。"""
    client = _client()
    if client is None:
        return None
    import anthropic
    try:
        resp = client.beta.messages.create(
            model=config.AI_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": config.AI_EFFORT, "format": {"type": "json_schema", "schema": schema}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError:
        log.warning("Claude: 認証エラー（APIキーを確認）。ルールベースにフォールバック")
        return None
    except (anthropic.RateLimitError, anthropic.APIConnectionError) as e:
        log.warning("Claude: 一時的エラー %s。ルールベースにフォールバック", type(e).__name__)
        return None
    except anthropic.APIStatusError as e:
        log.warning("Claude: APIエラー %s %s", e.status_code, e.message)
        return None
    except Exception as e:  # 認証情報未設定など。AI は補助機能なので画面は止めない
        log.warning("Claude: 呼び出し不可 (%s)。ルールベースにフォールバック", e)
        return None
    if resp.stop_reason in ("refusal", "max_tokens"):
        log.warning("Claude: stop_reason=%s", resp.stop_reason)
        return None
    text = next((b.text for b in resp.content if b.type == "text"), None)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ------------------------------------------------------------------ strategy
def build_context(a, fid):
    """AI に渡す根拠データ（すべて source_id 付き）を組み立てる。"""
    f = a.faculties[fid]
    u = a.universities[f["university_id"]]
    opp = a.opportunity_all()[fid]
    out = a.latest_outcome(fid)
    ind_year, inds = a.latest_industries(fid)
    comps = a.fac_companies.get(fid, {})
    top_companies = sorted(comps.items(), key=lambda kv: -(kv[1]["count"] or 0))[:15]
    competitors = a.faculty_competitors(fid, 10)
    segment = f.get("field") if f.get("field") in ("文系", "理系") else "全体"
    ss = db.rows(a.conn, "SELECT theme, metric, value, unit, year, source_id FROM student_signal WHERE segment=? "
                         "AND year=(SELECT MAX(year) FROM student_signal) ORDER BY value DESC", (segment,))
    sources = {}

    def src(sid):
        if sid and sid not in sources:
            sources[sid] = db.one(a.conn, "SELECT source_id, source_name, url, target_year, reliability FROM source_log WHERE source_id=?", (sid,))
        return sid

    attrs = {r["attribute"]: r["value"] for r in db.rows(
        a.conn, "SELECT attribute, value, source_id FROM company_attribute WHERE company_id=?", (a.target_id,))}
    for r in db.rows(a.conn, "SELECT DISTINCT source_id FROM company_attribute WHERE company_id=?", (a.target_id,)):
        src(r["source_id"])
    ctx = {
        "target_company": {"name": a.target["name"], "industry": a.target.get("industry"), "public_attributes": attrs},
        "faculty": {"university": u["name"], "faculty": f["faculty"], "field": f.get("field"), "region": u["region"],
                    "establishment": u["establishment"], "disclosure_level": u["disclosure_level"],
                    "source_id": src(f["source_id"])},
        "career_outcome": out and {k: out[k] for k in ("year", "graduates", "employed", "further_study", "employment_rate")}
        | {"source_id": src(out["source_id"])},
        "industry_breakdown": {"year": ind_year, "rows": [{"industry": r["industry"], "count": r["count"], "ratio": r["ratio"],
                                                          "source_id": src(r["source_id"])} for r in inds]},
        "employment_companies": {"year": a.emp_year.get(fid), "rows": [
            {"company": a.companies[c]["name"], "industry": a.companies[c]["industry"], "count": v["count"],
             "source_id": src(v["source_id"])} for c, v in top_companies]},
        "target_listed": opp["target_listed"],
        "opportunity": {"score": opp["score"], "grade": opp["grade"], "rank": opp["rank"],
                        "components": opp["components"], "missing_components": opp["missing"]},
        "competitors": [{"name": c["name"], "industry": c["industry"], "competition_score": c["score"],
                         "count_in_faculty": c.get("count_in_faculty"), "cooccurrence_in_target_faculties": c["cooccurrence_count"],
                         "university_count": c["university_count"], "popularity_rank": c["popularity_rank"],
                         "onecareer_favorites": c["favorites"]} for c in competitors],
        "student_values_general": {"segment": segment, "rows": [dict(r, source_id=src(r["source_id"])) for r in ss]},
    }
    for sid in ("demo-onecareer", "demo-survey-ranking"):
        if db.one(a.conn, "SELECT 1 FROM source_log WHERE source_id=?", (sid,)):
            src(sid)
    ctx["sources"] = [s for s in sources.values() if s]
    return ctx


def generate_strategy(a, fid, use_ai=True):
    ctx = build_context(a, fid)
    payload = json.dumps(ctx, ensure_ascii=False, sort_keys=True, default=str)
    key = "strategy:" + hashlib.sha256((config.AI_MODEL + payload).encode()).hexdigest()
    if use_ai:
        cached = db.one(a.conn, "SELECT payload FROM ai_cache WHERE cache_key=?", (key,))
        if cached:
            return json.loads(cached["payload"])
        result = _call_json(SYSTEM_PROMPT.format(target=a.target["name"]),
                            "以下のデータに基づいて攻略仮説を作成してください。\n\n" + payload, STRATEGY_SCHEMA)
        if result:
            out = {"engine": "claude", "model": config.AI_MODEL, "result": result, "context": ctx}
            with db.transaction(a.conn):
                a.conn.execute("INSERT OR REPLACE INTO ai_cache VALUES (?,?,?)",
                               (key, json.dumps(out, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
            return out
    return {"engine": "rule", "model": None, "result": rule_based_strategy(a, fid, ctx), "context": ctx}


def _pct(x):
    return f"{x * 100:.0f}%" if x is not None else "—"


def rule_based_strategy(a, fid, ctx):
    """AI 非使用時のテンプレート生成。入力データの言い換えのみで新しい事実は作らない。"""
    fac = ctx["faculty"]
    name = f"{fac['university']} {fac['faculty']}"
    opp = ctx["opportunity"]
    inds = [r for r in ctx["industry_breakdown"]["rows"] if r["industry"] != "その他"][:4]
    comps = ctx["competitors"][:5]
    out = ctx["career_outcome"] or {}
    fac_src = [fac["source_id"]]
    ind_src = sorted({r["source_id"] for r in inds})
    comp_txt = "、".join(c["name"] for c in comps[:3])
    listed = ctx["target_listed"]
    target = ctx["target_company"]["name"]
    target_ind = ctx["target_company"]["industry"]

    chars, evidence, issues, appeals, actions = [], [], [], [], []
    if inds:
        ind_txt = "・".join(f"{r['industry']}({_pct(r['ratio'])})" for r in inds)
        chars.append(f"就職先の業種構成は {ind_txt} が上位。")
        evidence.append({"claim": f"業種構成上位: {ind_txt}", "source_ids": ind_src})
    else:
        chars.append("業種別の就職データは公開範囲外（または未取得）。")
    if out.get("graduates"):
        chars.append(f"卒業者 {out['graduates']:,} 名、就職者 {out.get('employed') or 0:,} 名（{out['year']}年度）。")
        evidence.append({"claim": f"卒業者数 {out['graduates']}（{out['year']}年度）", "source_ids": [out["source_id"]]})
    if comps:
        chars.append(f"採用競合スコア上位は {comp_txt}。")
        evidence.append({"claim": f"競合上位: {comp_txt}", "source_ids": sorted({r['source_id'] for r in ctx['employment_companies']['rows']})})

    sv = ctx["student_values_general"]["rows"]
    pref = [r for r in sv if r["metric"].startswith("企業選択")][:3]
    avoid = [r for r in sv if r["metric"].startswith("行きたくない")][:2]
    student_values = (f"{ctx['student_values_general']['segment']}学生の一般的傾向として、"
                      + "・".join(f"{r['theme']}({r['value']:.0f}{r['unit'] or ''})" for r in pref)
                      + " を重視。" + ("忌避要因は " + "・".join(r["theme"] for r in avoid) + "。" if avoid else "")
                      ) if pref else "学生意識調査データ未取得。"

    if listed is None:
        affinity = f"就職先企業の公開がないため {target} の掲載有無は不明。"
        issues.append("学部別の就職先が非公開で、競合・親和性の判断材料が不足している。")
        actions.append("キャリアセンター訪問・学内資料閲覧で学部別就職先を取得する")
    elif listed:
        affinity = f"{target} は就職先として掲載あり。既存の接点がある市場。"
        issues.append(f"{comp_txt} など{target_ind}以外の大手と比較される前提での差別化が必要。")
    else:
        affinity = f"{target} は就職先に掲載なし。業種構成上の親和性から未開拓余地を評価。"
        issues.append(f"学部内での {target} の認知・接点が弱い可能性（掲載なし）。")
        actions.append("同学部出身の社員・内定者の有無を確認し、OB/OG 接点を作る")

    comp_inds = {c["industry"] for c in comps if c["industry"]}
    if comp_inds - {target_ind}:
        appeals.append(f"{target_ind}企業としてのみ訴求すると、{'・'.join(sorted(comp_inds - {target_ind}))} 志望層との比較で優位を作りにくい。事業の幅（企画・物流・IT 等）を前面に出す仮説。")
    if "情報通信業" in comp_inds or "サービス業" in comp_inds:
        appeals.append("IT/DX 志向層に向け、DX・SCM・EC 等のキャリアの具体例を示す仮説。")
        actions.append("商品企画 / DX テーマの少人数イベント")
    if any(r["theme"] in ("転勤",) for r in avoid) or any(r["theme"] == "転勤が多い" for r in avoid):
        appeals.append("転勤忌避が一般的傾向として見られるため、配転をキャリア形成として具体例で説明する仮説。")
    if any(r["theme"] in ("キャリア", "キャリアが見えない") for r in pref + avoid):
        appeals.append("キャリア可視性を高めるため、職種別キャリアパスを提示する仮説。")
    appeals.append("若手から事業運営を経験できる点の訴求（自社公開情報の確認が前提）。")
    actions += ["同学部 OB/OG コンテンツの作成", "競合企業比較型のリクルータートーク", "キャリアパス可視化資料"]

    caveats = ["ルールベース生成（AI 未使用）。データの言い換えのみで新たな事実は含まない。",
               "学生意識はセグメント全体の一般的傾向であり、当該学部固有の値ではない。"]
    if any((s or {}).get("reliability") == "DEMO" for s in ctx["sources"]):
        caveats.insert(0, "デモデータ（架空値）に基づく出力。実データ投入後に再生成すること。")
    if opp["missing_components"]:
        caveats.append("欠損指標は中立値で補完: " + "、".join(opp["missing_components"]))

    return {
        "priority_comment": f"攻略優先度 {opp['grade']}（{opp['score']}点・{opp['rank']}位）。相対評価であり意思決定の補助。",
        "market_summary": f"{name}は{fac.get('field') or ''}の学生市場。" + "".join(chars[:2]),
        "market_characteristics": chars,
        "competitor_view": (f"同一市場の採用競合候補は {comp_txt} 等。事業競合とは異なり、同じ学部の就職先として出現する企業群。"
                            if comps else "就職先データが無く採用競合を特定できない。"),
        "student_values": student_values,
        "target_affinity": affinity,
        "issues": issues,
        "appeal_hypotheses": appeals,
        "actions": list(dict.fromkeys(actions)),
        "validation": ["イベント参加率・説明会後アンケートで訴求別の反応を比較する",
                       "翌年度の就職実績公開で掲載有無・人数の変化を確認する"],
        "caveats": caveats,
        "evidence": evidence + [{"claim": "所属情報", "source_ids": fac_src}],
    }


# ------------------------------------------------------------------ classify
def classify_texts(texts, use_ai=True):
    """定性テキストをテーマ分類する。本文は保存せず結果のみ返す。"""
    texts = [t for t in texts if t and t.strip()][:50]
    if use_ai and texts:
        themes = list(THEMES) + ["その他"]
        result = _call_json(
            "学生の就職活動に関する発言をテーマ分類します。テーマは次から選び、複数可: " + "、".join(themes),
            json.dumps([{"index": i, "text": t} for i, t in enumerate(texts)], ensure_ascii=False),
            CLASSIFY_SCHEMA, max_tokens=4000)
        if result:
            by_idx = {r["index"]: [t for t in r["themes"] if t in themes] or ["その他"] for r in result["results"]}
            return {"engine": "claude", "results": [{"text": t, "themes": by_idx.get(i, ["その他"])} for i, t in enumerate(texts)]}
    return {"engine": "keyword", "results": [{"text": t, "themes": [h["theme"] for h in classify_keywords(t)]} for t in texts]}
