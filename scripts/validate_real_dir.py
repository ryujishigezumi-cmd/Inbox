"""1大学ぶんの data/real/<university_id>/ を単独で検証する。

- 一時 DB に取り込めるか（列名・出典・型）
- 学部ごとに 業種別人数の合計 == 就職者数 か（両方ある場合）

    python scripts/validate_real_dir.py <university_id>
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import db, ingest  # noqa: E402


def main(uid):
    d = ROOT / "data" / "real" / uid
    tmp = Path(tempfile.mkdtemp()) / "v.db"
    conn = ingest.reset_db(tmp)
    try:
        print(ingest.ingest_dir(conn, d))
    except ingest.IngestError as e:
        print("取り込みエラー:", e)
        return 1
    problems = 0
    for r in db.rows(conn, """
        SELECT o.faculty_id, o.year, o.employed, SUM(i.count) AS ind_sum
        FROM career_outcome o JOIN employment_industry i ON i.faculty_id=o.faculty_id AND i.year=o.year
        GROUP BY o.faculty_id, o.year"""):
        if r["employed"] is not None and r["ind_sum"] is not None and r["employed"] != r["ind_sum"]:
            problems += 1
            print(f"不一致: {r['faculty_id']} {r['year']} 就職者 {r['employed']} / 業種計 {r['ind_sum']}")
    facs = {r["faculty_id"] for r in db.rows(conn, "SELECT faculty_id FROM faculty_master")}
    for table in ("career_outcome", "employment_industry", "employment_company"):
        bad = {r["faculty_id"] for r in db.rows(conn, f"SELECT DISTINCT faculty_id FROM {table}")} - facs
        if bad:
            problems += 1
            print(f"{table}: faculties.csv に無い faculty_id {sorted(bad)}")
    for t in ("faculty_master", "career_outcome", "employment_industry", "employment_company"):
        print(t, db.one(conn, f"SELECT COUNT(*) n FROM {t}")["n"])
    print("OK" if not problems else f"要確認 {problems} 件")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
