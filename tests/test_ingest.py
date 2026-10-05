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
