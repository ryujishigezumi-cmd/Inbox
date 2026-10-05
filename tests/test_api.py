"""仕様書 19章「MVP の完成条件」をそのままテストにしたもの。"""


def test_1_search_university(client):
    r = client.get("/api/search", params={"q": "関西大学"}).json()
    assert [u["name"] for u in r] == ["関西大学"]


def test_2_select_faculty(client):
    facs = client.get("/api/search", params={"q": "関西大学"}).json()[0]["faculties"]
    assert any(f["faculty"] == "商学部" for f in facs)


def _fid(client, uni="関西大学", fac="商学部"):
    return next(f["faculty_id"] for f in client.get("/api/search", params={"q": uni}).json()[0]["faculties"] if f["faculty"] == fac)


def test_3_main_employers(client):
    d = client.get(f"/api/faculties/{_fid(client)}").json()
    assert d["companies"] and all("count" in c for c in d["companies"])


def test_4_target_listed_flag(client):
    d = client.get(f"/api/faculties/{_fid(client)}").json()
    assert d["target"]["listed"] in (True, False)
    # レベル C（学部×企業が非公開）は「不明」= None であり False ではない
    c = client.get(f"/api/faculties/{_fid(client, '一橋大学')}").json()
    assert c["target"]["listed"] is None


def test_5_competitor_top10(client):
    d = client.get(f"/api/faculties/{_fid(client)}").json()
    comps = d["competitors"]
    assert 0 < len(comps) <= 10
    assert all(c["company_id"] != "nitori" for c in comps)
    assert [c["score"] for c in comps] == sorted((c["score"] for c in comps), reverse=True)


def test_6_competitor_detail(client):
    fid = _fid(client)
    cid = client.get(f"/api/faculties/{fid}").json()["competitors"][0]["company_id"]
    d = client.get(f"/api/companies/{cid}", params={"faculty_id": fid}).json()
    assert d["comparison"] and d["signal_comparison"]
    assert d["competition"]["score"] == next(c["score"] for c in client.get(f"/api/faculties/{fid}").json()["competitors"] if c["company_id"] == cid)
    assert abs(sum(b["weight"] for b in d["competition"]["breakdown"]) - 1) < 1e-6


def test_7_student_signals(client):
    d = client.get("/api/insights", params={"segment": "文系"}).json()
    assert d["metrics"] and d["review"]


def test_8_sources_link(client):
    d = client.get(f"/api/faculties/{_fid(client)}").json()
    assert d["sources"] and all(s["url"].startswith("http") for s in d["sources"])


def test_9_10_ai_strategy_fallback(client):
    d = client.get(f"/api/strategy/{_fid(client)}").json()
    assert d["engine"] == "rule"
    r = d["result"]
    assert r["market_summary"] and r["appeal_hypotheses"] and r["actions"]
    known = {s["source_id"] for s in d["context"]["sources"]}
    assert all(sid in known for e in r["evidence"] for sid in e["source_ids"])  # 出典のない主張をしない


def test_ranking_filters(client):
    rows = client.get("/api/ranking", params={"region": "関西", "target_listed": "no"}).json()["rows"]
    assert rows and all(r["region"] == "関西" and r["target_listed"] is False for r in rows)
    allrows = client.get("/api/ranking").json()["rows"]
    assert {r["grade"] for r in allrows} == {"A", "B", "C", "D"}
    assert all(0 <= r["score"] <= 100 for r in allrows)


def test_classify_keyword(client):
    r = client.post("/api/classify", json={"texts": ["全国転勤が気になる", "将来どういうキャリアになるかわからない"]}).json()
    assert r["results"][0]["themes"] == ["勤務地・転勤"]
    assert "キャリア可視性" in r["results"][1]["themes"]


def test_index(client):
    assert client.get("/").status_code == 200
