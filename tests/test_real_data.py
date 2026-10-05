"""data/real（公開データ）を全部取り込み、全学部・主要競合で各画面の API が動くことを確かめる。"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def real_client(tmp_path_factory, monkeypatch_module):
    from app import config, main
    from scripts.load_real_data import main as load_real
    db = tmp_path_factory.mktemp("real") / "real.db"
    load_real(["--db", str(db)])
    monkeypatch_module.setattr(config, "DB_PATH", db)
    monkeypatch_module.setattr(config, "AI_ENABLED", False)
    main._conn = None
    yield TestClient(main.app)
    main._conn = None


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def test_every_faculty_renders(real_client):
    rows = real_client.get("/api/ranking").json()["rows"]
    assert len(rows) > 100
    for r in rows:
        fid = r["faculty_id"]
        assert real_client.get(f"/api/faculties/{fid}").status_code == 200
        s = real_client.get(f"/api/strategy/{fid}").json()
        assert s["engine"] == "rule" and s["result"]["market_summary"]


def test_competitors_and_target(real_client):
    comps = real_client.get("/api/competitors", params={"limit": 10}).json()
    assert comps and all(c["company_id"] != "nitori" for c in comps)
    for c in comps:
        assert real_client.get(f"/api/companies/{c['company_id']}").status_code == 200
    meta = real_client.get("/api/meta").json()
    assert meta["demo_data"] is False and meta["target"]["industry"] == "卸売業・小売業"
