"""企業名の正規化（16章）。原文は保持し、分析用キーに変換して企業IDへ統合する。"""
import re
import unicodedata

# 法人格・付帯語。順序は長いものから。
_LEGAL_FORMS = [
    "株式会社", "(株)", "㈱", "有限会社", "(有)", "合同会社", "一般社団法人",
    "国立大学法人", "独立行政法人",
]
_SUFFIXES = ["ホールディングス", "グループ", "hd", "holdings", "group", "corporation", "inc.", "inc", "co.,ltd.", "ltd."]


def normalize_company_name(raw: str) -> str:
    """表記ゆれを吸収した照合用キーを返す。

    例: 「株式会社ニトリ」「ニトリ」「ニトリグループ」「ﾆﾄﾘ ホールディングス」→ "ニトリ"
    """
    if not raw:
        return ""
    s = unicodedata.normalize("NFKC", raw).strip().lower()
    for lf in _LEGAL_FORMS:
        s = s.replace(unicodedata.normalize("NFKC", lf).lower(), "")
    s = re.sub(r"[\s・\-‐－―]", "", s)
    s = re.sub(r"[()（）「」『』]", "", s)
    changed = True
    while changed:
        changed = False
        for suf in _SUFFIXES:
            if s.endswith(suf) and len(s) > len(suf):
                s = s[: -len(suf)]
                changed = True
    return s


def build_alias_index(conn) -> dict:
    return {r["alias_normalized"]: r["company_id"] for r in conn.execute("SELECT * FROM company_alias")}


def resolve_company_id(raw: str, alias_index: dict):
    return alias_index.get(normalize_company_name(raw))
