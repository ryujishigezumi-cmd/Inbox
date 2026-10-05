"""data/real/ の公開データを取り込む。

1. 各大学フォルダの employment_companies.csv から企業マスタを生成（data/real/_generated/）
2. DB を作り直し、大学フォルダ → 共通 → 生成物 の順に取り込む

    python scripts/load_real_data.py [--db PATH]
"""
import argparse
import csv
import hashlib
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config, ingest  # noqa: E402
from app.industries import standardize_industry  # noqa: E402
from app.normalize import normalize_company_name  # noqa: E402

REAL = ROOT / "data" / "real"
GENERATED = REAL / "_generated"
COMMON = REAL / "_common"
TARGET = {"key": normalize_company_name("ニトリ"), "id": "nitori", "name": "株式会社ニトリ",
          "industry": "卸売業・小売業", "source_id": "nitori-corp"}


def university_dirs():
    return sorted(p for p in REAL.iterdir() if p.is_dir() and not p.name.startswith("_"))


def _display_name(raw):
    name = raw.strip()
    for suffix in ("　など", " など", "など"):
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return name


def build_company_master():
    aliases = {}
    alias_path = COMMON / "alias_merge.csv"
    if alias_path.exists():
        with alias_path.open(encoding="utf-8") as f:
            aliases = {normalize_company_name(r["alias"]): normalize_company_name(r["canonical"]) for r in csv.DictReader(f)}

    names, industries, sources, raw_keys = defaultdict(Counter), defaultdict(Counter), {}, defaultdict(set)
    for d in university_dirs():
        path = d / "employment_companies.csv"
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                raw_key = normalize_company_name(r["company_name_raw"])
                if not raw_key:
                    continue
                key = aliases.get(raw_key, raw_key)
                raw_keys[key].add(raw_key)
                names[key][_display_name(r["company_name_raw"])] += 1
                if (r.get("industry_raw") or "").strip():
                    industries[key][standardize_industry(r["industry_raw"])] += 1
                sources.setdefault(key, r["source_id"])

    companies, alias_rows = [], []
    for key in sorted(names):
        if key == TARGET["key"]:
            continue
        cid = "co-" + hashlib.sha1(key.encode()).hexdigest()[:10]
        ind = industries[key].most_common(1)[0][0] if industries[key] else ""
        companies.append((cid, names[key].most_common(1)[0][0], ind, sources[key]))
        alias_rows += [(n, cid) for n in names[key]] + [(k, cid) for k in raw_keys[key]]
    companies.append((TARGET["id"], TARGET["name"], TARGET["industry"], TARGET["source_id"]))
    alias_rows += [(n, TARGET["id"]) for n in names.get(TARGET["key"], {})] + [("ニトリ", TARGET["id"])]

    GENERATED.mkdir(exist_ok=True)
    with (GENERATED / "companies.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company_id", "name", "industry", "source_id"])
        w.writerows(companies)
    with (GENERATED / "company_aliases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["alias", "company_id"])
        w.writerows(sorted(set(alias_rows)))
    return len(companies)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(config.DB_PATH))
    a = p.parse_args(argv)
    n = build_company_master()
    conn = ingest.reset_db(a.db)
    dirs = university_dirs() + [COMMON, GENERATED]
    for d in dirs:
        counts = ingest.ingest_dir(conn, d)
        print(f"{d.name:14s} " + " ".join(f"{k}={v}" for k, v in counts.items()))
    unresolved = conn.execute("SELECT COUNT(*) FROM employment_company WHERE company_id IS NULL").fetchone()[0]
    print(f"企業マスタ {n} 社 / 未正規化の就職先 {unresolved} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
