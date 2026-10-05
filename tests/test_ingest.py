import csv

import pytest

from app import db, ingest


def _write(dirpath, name, header, rows):
    with (dirpath / f"{name}.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _minimal(tmp_path):
    _write(tmp_path, "sources", ["source_id", "url", "source_name", "source_type"], [("s1", "https://example.ac.jp", "x", "university")])
    _write(tmp_path, "universities", ["university_id", "name", "disclosure_level", "source_id"], [("u1", "テスト大学", "A", "s1")])
    _write(tmp_path, "faculties", ["faculty_id", "university_id", "faculty", "field", "source_id"], [("f1", "u1", "商学部", "文系", "s1")])
    _write(tmp_path, "companies", ["company_id", "name", "industry", "source_id"], [("nitori", "株式会社ニトリ", "小売", "s1")])


def test_null_count_is_not_zero(tmp_path):
    _minimal(tmp_path)
    _write(tmp_path, "employment_companies", ["university_id", "faculty_id", "year", "company_name_raw", "count", "listed", "source_id"],
           [("u1", "f1", 2024, "ニトリグループ", "", 1, "s1"), ("u1", "f1", 2024, "謎の会社", "3", 1, "s1")])
    conn = ingest.reset_db(tmp_path / "t.db")
    ingest.ingest_dir(conn, tmp_path)
    rows = {r["company_name_raw"]: r for r in db.rows(conn, "SELECT * FROM employment_company")}
    assert rows["ニトリグループ"]["count"] is None          # 人数なし ≠ 0人
    assert rows["ニトリグループ"]["company_id"] == "nitori"  # 正規化で統合
    assert rows["謎の会社"]["company_id"] is None            # 未解決は NULL
    assert rows["謎の会社"]["count"] == 3


def test_source_required(tmp_path):
    _minimal(tmp_path)
    _write(tmp_path, "employment_companies", ["university_id", "faculty_id", "year", "company_name_raw", "count", "listed", "source_id"],
           [("u1", "f1", 2024, "ニトリ", "", 1, "")])
    conn = ingest.reset_db(tmp_path / "t.db")
    with pytest.raises(ingest.IngestError):
        ingest.ingest_dir(conn, tmp_path)


def test_unknown_source_rejected(tmp_path):
    _minimal(tmp_path)
    _write(tmp_path, "employment_companies", ["university_id", "faculty_id", "year", "company_name_raw", "count", "listed", "source_id"],
           [("u1", "f1", 2024, "ニトリ", "", 1, "nope")])
    conn = ingest.reset_db(tmp_path / "t.db")
    with pytest.raises(ingest.IngestError):
        ingest.ingest_dir(conn, tmp_path)


def test_incremental_ingest_keeps_other_rows(tmp_path):
    _minimal(tmp_path)
    hdr = ["university_id", "faculty_id", "year", "company_name_raw", "count", "listed", "source_id"]
    _write(tmp_path, "employment_companies", hdr, [("u1", "f1", 2024, "ニトリ", "5", 1, "s1")])
    conn = ingest.reset_db(tmp_path / "t.db")
    ingest.ingest_dir(conn, tmp_path)

    # 別の学部だけを追加投入
    add = tmp_path / "add"
    add.mkdir()
    _write(add, "faculties", ["faculty_id", "university_id", "faculty", "field", "source_id"], [("f2", "u1", "経済学部", "文系", "s1")])
    _write(add, "employment_companies", hdr, [("u1", "f2", 2024, "ニトリ", "2", 1, "s1")])
    ingest.ingest_dir(conn, add)
    assert db.one(conn, "SELECT COUNT(*) n FROM employment_company")["n"] == 2

    # 同じ学部・年度を再投入すると置き換わる（重複しない）
    _write(add, "employment_companies", hdr, [("u1", "f2", 2024, "ニトリ", "7", 1, "s1")])
    ingest.ingest_dir(conn, add)
    rows = db.rows(conn, "SELECT faculty_id, count FROM employment_company ORDER BY faculty_id")
    assert rows == [{"faculty_id": "f1", "count": 5}, {"faculty_id": "f2", "count": 7}]
