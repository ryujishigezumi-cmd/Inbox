"""ブラウザだけで開けるデモ版（1ファイルの HTML）を作る。

サーバーの全 API 応答を事前に計算して埋め込み、画面（static/）はそのまま再利用する。
AI はルールベース生成、自由記述の分類はキーワード辞書で動く。

    python scripts/build_static_demo.py [出力パス]   # 既定: dist/demo.html
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["RMI_AI_ENABLED"] = "0"
# デモは常に同梱のサンプル（架空値）から作る。手元の rmi.db（実データの場合あり）は使わない
os.environ["RMI_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "demo.db")

from fastapi.testclient import TestClient  # noqa: E402

from app import config, ingest, main  # noqa: E402
from app.analytics import Analytics  # noqa: E402
from app.insights import THEMES  # noqa: E402

RESOLVER = r"""
window.RMI_STATIC = async (path, opts) => {
  const D = window.RMI_DATA;
  const u = new URL(path, "http://demo.local");
  const p = decodeURIComponent(u.pathname), q = u.searchParams;
  const notFound = () => { throw new Error("404 見つかりません"); };
  const src = (ids) => ids.map((i) => D.sourceMap[i]);
  if (p === "/api/meta") return D.meta;
  if (p === "/api/sources") return D.sources;
  if (p === "/api/insights") return D.insights[q.get("segment") || "全体"] || notFound();
  if (p.startsWith("/api/faculties/")) {
    const f = D.faculties[p.split("/").pop()] || notFound();
    return { ...f, sources: src(f.sources) };
  }
  if (p.startsWith("/api/strategy/")) {
    const s = D.strategies[p.split("/").pop()] || notFound();
    return { ...s, context: { sources: src(s.context.sources) } };
  }
  if (p.startsWith("/api/companies/")) {
    const cid = p.split("/").pop(), base = D.companies[cid];
    if (!base) notFound();
    const out = { ...base, sources: src(base.sources), signal_comparison: base.signal_comparison || D.emptySignals };
    // 学部を指定したときは、その学部の競合 TOP10 に入っていれば学部内のスコアを使う
    const fid = q.get("faculty_id");
    const row = fid && D.faculties[fid] && D.faculties[fid].competitors.find((c) => c.company_id === cid);
    return row ? { ...out, competition: row } : out;
  }
  if (p === "/api/search") {
    const s = (q.get("q") || "").trim();
    const unis = D.search.filter((u) => !s || u.name.includes(s));
    if (s && !unis.length) {
      return D.search.flatMap((u) => u.faculties.filter((f) => f.faculty.includes(s)).map((f) => ({ ...u, faculties: [f] })));
    }
    return unis;
  }
  if (p === "/api/ranking") {
    const f = {};
    for (const k of ["region", "establishment", "field", "faculty", "q", "min_graduates", "competitor", "target_listed"]) {
      if (q.get(k)) f[k] = q.get(k);
    }
    const rows = D.ranking.filter((r) => {
      if (f.region && r.region !== f.region) return false;
      if (f.establishment === "国公立" && !["国立", "公立"].includes(r.establishment)) return false;
      if (f.establishment && f.establishment !== "国公立" && r.establishment !== f.establishment) return false;
      if (f.field && r.field !== f.field) return false;
      if (f.q && !r.university.includes(f.q) && !r.faculty.includes(f.q)) return false;
      if (f.faculty && !r.faculty.includes(f.faculty)) return false;
      if (f.min_graduates && (r.graduates || 0) < Number(f.min_graduates)) return false;
      if (f.competitor && !(D.facCompanies[r.faculty_id] || []).includes(f.competitor)) return false;
      if (f.target_listed === "yes" && r.target_listed !== true) return false;
      if (f.target_listed === "no" && r.target_listed !== false) return false;
      return true;
    });
    return { filters: f, rows };
  }
  if (p === "/api/classify") {
    const texts = JSON.parse(opts.body).texts.filter((t) => t && t.trim()).slice(0, 50);
    return { engine: "keyword", results: texts.map((t) => {
      const themes = Object.entries(D.themes).filter(([, ws]) => ws.some((w) => t.includes(w))).map(([k]) => k);
      return { text: t, themes: themes.length ? themes : ["その他"] };
    }) };
  }
  notFound();
};
"""


def _compact(data):
    """1ページ 16MB 以内に収めるため、重複する情報を共有化する（表示内容は変えない）。"""
    sources = {}

    def ids(items):
        for src in items:
            sources[src["source_id"]] = src
        return [src["source_id"] for src in items]

    for part in ("faculties", "companies"):
        for v in data[part].values():
            v["sources"] = ids(v["sources"])
    empty_signals = None
    for v in data["companies"].values():
        if all(r["target"] is None and r["competitor"] is None for r in v["signal_comparison"]):
            empty_signals = [{"signal": r["signal"], "target": None, "competitor": None} for r in v["signal_comparison"]]
            del v["signal_comparison"]
    for v in data["strategies"].values():
        v["context"] = {"sources": ids(v["context"]["sources"])}
    data["sourceMap"] = sources
    data["emptySignals"] = empty_signals


def build(out: Path, real=False):
    if real:
        from scripts.load_real_data import main as load_real
        load_real(["--db", str(config.DB_PATH)])
    else:
        conn = ingest.reset_db(config.DB_PATH)
        ingest.ingest_dir(conn, config.SAMPLE_DIR)
        conn.close()
    main._conn = None
    client = TestClient(main.app)
    get = lambda path, **params: client.get(path, params=params).raise_for_status().json()  # noqa: E731
    a = Analytics(main.get_conn())

    data = {
        "meta": get("/api/meta"),
        "sources": get("/api/sources"),
        "search": get("/api/search"),
        "ranking": get("/api/ranking")["rows"],
        "insights": {s: get("/api/insights", segment=s) for s in ("全体", "文系", "理系")},
        "faculties": {f: get(f"/api/faculties/{f}") for f in a.faculties},
        "strategies": {f: get(f"/api/strategy/{f}", use_ai="false") for f in a.faculties},
        "companies": {c: get(f"/api/companies/{c}") for c in a.companies},
        "facCompanies": {f: sorted(cs) for f, cs in a.fac_companies.items()},
        "themes": THEMES,
    }
    _compact(data)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    index = (config.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    body = re.search(r"<body>(.*?)<script src=", index, re.S).group(1)
    if real:
        body = body.replace('<main id="app">', '<div class="banner">MVP対象16大学の公式資料（大学サイト・大学ポートレート）から転記した公開データです。'
                            '大学ごとに取得できた範囲が異なり、ONE CAREER・就職人気ランキング・企業の初任給は未収録です。'
                            'AI 提案はルールベース生成で表示しています。</div>\n<main id="app">', 1)
    body = body.replace(
        "実データは <code>python -m app.ingest &lt;dir&gt; --reset</code> で投入してください。",
        "ブラウザ版デモのため、AI 提案はルールベース生成、自由記述の分類はキーワード辞書で動きます。")
    css = (config.STATIC_DIR / "style.css").read_text(encoding="utf-8")
    js = (config.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    html = (
        f"<title>{'16大学 採用市場分析' if real else '採用市場インテリジェンス'}</title>\n"
        f"<style>\n{css}\n</style>\n{body}"
        f"<script>window.RMI_DATA={payload};</script>\n"
        f"<script>{RESOLVER}</script>\n<script>\n{js}\n</script>\n"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?")
    ap.add_argument("--real", action="store_true", help="data/real の公開データで作る（既定はデモ用サンプル）")
    args = ap.parse_args()
    build(Path(args.out) if args.out else ROOT / "dist" / ("real.html" if args.real else "demo.html"), real=args.real)
