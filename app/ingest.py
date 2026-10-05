"""CSV 取り込み。サンプルデータも実データも同じ経路で投入する。

使い方:
    python -m app.ingest <csv_dir> [--reset]

ディレクトリ内のファイル（存在するものだけ取り込む）:
    sources.csv, universities.csv, faculties.csv, career_outcomes.csv,
    companies.csv, company_aliases.csv, company_attributes.csv,
    employment_companies.csv, employment_industries.csv,
    student_signals.csv, review_signals.csv

データ品質ルール（16章）:
    - 人数が空欄 → count = NULL（0 にしない）
    - 企業名は原文保持し、正規化辞書で company_id に統合（未解決は NULL）
    - 全行 source_id 必須（Source_Log に存在すること）
"""
import argparse
import csv
import sys
from pathlib import Path

from . import config, db
from .normalize import build_alias_index, normalize_company_name, resolve_company_id

LOAD_ORDER = [
    "sources", "universities", "faculties", "career_outcomes", "companies",
    "company_aliases", "company_attributes", "employment_companies",
    "employment_industries", "student_signals", "review_signals",
]


class IngestError(ValueError):
    pass


def _int(v):
    v = (v or "").strip()
    return int(float(v)) if v else None


def _float(v):
    v = (v or "").strip()
    return float(v) if v else None


def _str(v):
    v = (v or "").strip()
    return v or None


def _read(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _require_source(conn, sid, ctx):
    if not sid:
        raise IngestError(f"{ctx}: source_id は必須です（出典を必ず保持）")
    if not conn.execute("SELECT 1 FROM source_log WHERE source_id=?", (sid,)).fetchone():
        raise IngestError(f"{ctx}: 未登録の source_id '{sid}'")


def load_sources(conn, rows):
    for r in rows:
        conn.execute(
            "INSERT OR REPLACE INTO source_log VALUES (?,?,?,?,?,?,?,?,?,?)",
            (r["source_id"], r["url"], r["source_name"], r.get("source_type") or "university",
             _str(r.get("retrieved_at")), _str(r.get("published_at")), _int(r.get("target_year")),
             _str(r.get("scope")), _str(r.get("reliability")), _str(r.get("note"))),
        )


def load_universities(conn, rows):
    for i, r in enumerate(rows):
        _require_source(conn, r.get("source_id"), f"universities.csv 行{i+2}")
        conn.execute(
            "INSERT OR REPLACE INTO university_master VALUES (?,?,?,?,?,?,?,?)",
            (r["university_id"], r["name"], _str(r.get("region")), _str(r.get("prefecture")),
             _str(r.get("establishment")), _int(r.get("student_count")),
             _str(r.get("disclosure_level")), r["source_id"]),
        )


def load_faculties(conn, rows):
    for i, r in enumerate(rows):
        _require_source(conn, r.get("source_id"), f"faculties.csv 行{i+2}")
        conn.execute(
            "INSERT OR REPLACE INTO faculty_master VALUES (?,?,?,?,?,?,?)",
            (r["faculty_id"], r["university_id"], r["faculty"], _str(r.get("department")),
             _str(r.get("field")), _int(r.get("student_count")), r["source_id"]),
        )


def load_career_outcomes(conn, rows):
    for i, r in enumerate(rows):
        _require_source(conn, r.get("source_id"), f"career_outcomes.csv 行{i+2}")
        grads, emp = _int(r.get("graduates")), _int(r.get("employed"))
        rate = _float(r.get("employment_rate"))
        conn.execute(
            "INSERT OR REPLACE INTO career_outcome VALUES (?,?,?,?,?,?,?,?)",
            (r["university_id"], r["faculty_id"], _int(r["year"]), grads, emp,
             _int(r.get("further_study")), rate, r["source_id"]),
        )


def load_companies(conn, rows):
    for i, r in enumerate(rows):
        _require_source(conn, r.get("source_id"), f"companies.csv 行{i+2}")
        conn.execute(
            "INSERT OR REPLACE INTO company_master VALUES (?,?,?,?,?,?,?,?,?,?)",
            (r["company_id"], r["name"], _str(r.get("industry")), _int(r.get("hiring_count")),
             _int(r.get("starting_salary")), _str(r.get("locations")), _str(r.get("transfer_policy")),
             _str(r.get("career_system")), _str(r.get("recruit_url")), r["source_id"]),
        )
        conn.execute("INSERT OR REPLACE INTO company_alias VALUES (?,?)",
                     (normalize_company_name(r["name"]), r["company_id"]))


def load_company_aliases(conn, rows):
    for r in rows:
        conn.execute("INSERT OR REPLACE INTO company_alias VALUES (?,?)",
                     (normalize_company_name(r["alias"]), r["company_id"]))


def load_company_attributes(conn, rows):
    for i, r in enumerate(rows):
        _require_source(conn, r.get("source_id"), f"company_attributes.csv 行{i+2}")
        conn.execute("INSERT OR REPLACE INTO company_attribute VALUES (?,?,?,?)",
                     (r["company_id"], r["attribute"], _str(r.get("value")), r["source_id"]))


def load_employment_companies(conn, rows):
    idx = build_alias_index(conn)
    for i, r in enumerate(rows):
        _require_source(conn, r.get("source_id"), f"employment_companies.csv 行{i+2}")
        raw = r["company_name_raw"].strip()
        listed = r.get("listed", "1").strip()
        conn.execute(
            "INSERT INTO employment_company (university_id, faculty_id, year, company_id,"
            " company_name_raw, count, listed, source_id) VALUES (?,?,?,?,?,?,?,?)",
            (r["university_id"], r["faculty_id"], _int(r["year"]), resolve_company_id(raw, idx),
             raw, _int(r.get("count")), 0 if listed == "0" else 1, r["source_id"]),
        )


def load_employment_industries(conn, rows):
    for i, r in enumerate(rows):
        _require_source(conn, r.get("source_id"), f"employment_industries.csv 行{i+2}")
        conn.execute(
            "INSERT OR REPLACE INTO employment_industry VALUES (?,?,?,?,?,?,?)",
            (r["university_id"], r["faculty_id"], _int(r["year"]), r["industry"],
             _int(r.get("count")), _float(r.get("ratio")), r["source_id"]),
        )


def load_student_signals(conn, rows):
    for i, r in enumerate(rows):
        _require_source(conn, r.get("source_id"), f"student_signals.csv 行{i+2}")
        conn.execute(
            "INSERT INTO student_signal (year, segment, theme, metric, value, unit, source_id)"
            " VALUES (?,?,?,?,?,?,?)",
            (_int(r["year"]), r.get("segment") or "全体", r["theme"], r["metric"],
             _float(r.get("value")), _str(r.get("unit")), r["source_id"]),
        )


def load_review_signals(conn, rows):
    for i, r in enumerate(rows):
        _require_source(conn, r.get("source_id"), f"review_signals.csv 行{i+2}")
        conn.execute(
            "INSERT INTO review_signal (company_id, year, segment, theme, signal_type, value, source_id)"
            " VALUES (?,?,?,?,?,?,?)",
            (r["company_id"], _int(r["year"]), r.get("segment") or "全体", _str(r.get("theme")),
             r["signal_type"], _float(r.get("value")), r["source_id"]),
        )


LOADERS = {name: globals()[f"load_{name}"] for name in LOAD_ORDER}

# 再投入時に追記型テーブルを重複させないため、取り込み前にクリアする対象
_APPEND_TABLES = {
    "employment_companies": "employment_company",
    "student_signals": "student_signal",
    "review_signals": "review_signal",
}


def ingest_dir(conn, csv_dir: Path) -> dict:
    counts = {}
    with db.transaction(conn):
        for name in LOAD_ORDER:
            path = Path(csv_dir) / f"{name}.csv"
            if not path.exists():
                continue
            data = _read(path)
            if name in _APPEND_TABLES:
                conn.execute(f"DELETE FROM {_APPEND_TABLES[name]}")
            LOADERS[name](conn, data)
            counts[name] = len(data)
        # 企業辞書が後から増えた場合に備え、未解決の就職先を再解決
        idx = build_alias_index(conn)
        for r in conn.execute("SELECT id, company_name_raw FROM employment_company WHERE company_id IS NULL").fetchall():
            cid = resolve_company_id(r["company_name_raw"], idx)
            if cid:
                conn.execute("UPDATE employment_company SET company_id=? WHERE id=?", (cid, r["id"]))
        conn.execute("DELETE FROM ai_cache")
    return counts


def reset_db(path=None):
    path = Path(path or config.DB_PATH)
    if path.exists():
        path.unlink()
    conn = db.connect(path)
    db.init_schema(conn)
    return conn


def main(argv=None):
    p = argparse.ArgumentParser(description="CSV を取り込む")
    p.add_argument("csv_dir", nargs="?", default=str(config.SAMPLE_DIR))
    p.add_argument("--reset", action="store_true", help="DB を作り直してから取り込む")
    a = p.parse_args(argv)
    conn = reset_db() if a.reset else db.connect()
    db.init_schema(conn)
    try:
        counts = ingest_dir(conn, Path(a.csv_dir))
    except IngestError as e:
        print(f"取り込みエラー: {e}", file=sys.stderr)
        return 1
    for k, v in counts.items():
        print(f"{k:24s} {v:6d} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
