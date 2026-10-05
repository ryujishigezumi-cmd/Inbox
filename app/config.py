"""アプリ設定。環境変数で上書き可能。"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("RMI_DB_PATH", ROOT / "rmi.db"))
SAMPLE_DIR = ROOT / "data" / "sample"
STATIC_DIR = ROOT / "static"

# 自社（分析の基準となる企業）。company_id で指定する。
TARGET_COMPANY_ID = os.environ.get("RMI_TARGET_COMPANY_ID", "nitori")

# AI（Claude）設定。APIキー等が無い場合はルールベース生成にフォールバックする。
AI_ENABLED = os.environ.get("RMI_AI_ENABLED", "1") == "1"
AI_MODEL = os.environ.get("RMI_AI_MODEL", "claude-opus-5-5")
AI_EFFORT = os.environ.get("RMI_AI_EFFORT", "medium")
