import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "test.db"
    os.environ["RMI_DB_PATH"] = str(path)
    os.environ["RMI_AI_ENABLED"] = "0"
    subprocess.run([sys.executable, "scripts/generate_sample_data.py"], cwd=ROOT, check=True, capture_output=True)
    from app import ingest
    conn = ingest.reset_db(path)
    ingest.ingest_dir(conn, ROOT / "data" / "sample")
    conn.close()
    return path


@pytest.fixture(scope="session")
def client(db_path):
    from app import config
    config.DB_PATH = db_path
    config.AI_ENABLED = False
    from fastapi.testclient import TestClient
    from app import main
    main._conn = None
    return TestClient(main.app)
