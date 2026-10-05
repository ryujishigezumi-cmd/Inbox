-- 仕様書 15章 データモデル準拠。すべての事実データは source_id で Source_Log に紐づく。

CREATE TABLE IF NOT EXISTS source_log (
    source_id     TEXT PRIMARY KEY,
    url           TEXT NOT NULL,
    source_name   TEXT NOT NULL,            -- 情報源（大学公式 / 大学ポートレート / ONE CAREER 等）
    source_type   TEXT NOT NULL,            -- university / survey / review / company / government
    retrieved_at  TEXT,                     -- 取得日
    published_at  TEXT,                     -- 公開日
    target_year   INTEGER,                  -- データ対象年度
    scope         TEXT,                     -- 公開範囲（public / sample 等）
    reliability   TEXT,                     -- 信頼度（A/B/C/DEMO）
    note          TEXT
);

CREATE TABLE IF NOT EXISTS university_master (
    university_id    TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    region           TEXT,                  -- 関東 / 関西 / 中国 / 九州 ...
    prefecture       TEXT,
    establishment    TEXT,                  -- 国立 / 公立 / 私立
    student_count    INTEGER,
    disclosure_level TEXT CHECK (disclosure_level IN ('A','B','C')),  -- 17章 情報取得レベル
    source_id        TEXT REFERENCES source_log(source_id)
);

CREATE TABLE IF NOT EXISTS faculty_master (
    faculty_id     TEXT PRIMARY KEY,
    university_id  TEXT NOT NULL REFERENCES university_master(university_id),
    faculty        TEXT NOT NULL,           -- 学部
    department     TEXT,                    -- 学科（NULL=学部単位でのみ公開）
    field          TEXT,                    -- 文系 / 理系 / 文理融合
    student_count  INTEGER,
    source_id      TEXT REFERENCES source_log(source_id)
);

CREATE TABLE IF NOT EXISTS career_outcome (
    university_id    TEXT NOT NULL,
    faculty_id       TEXT NOT NULL,
    year             INTEGER NOT NULL,
    graduates        INTEGER,
    employed         INTEGER,
    further_study    INTEGER,
    employment_rate  REAL,
    source_id        TEXT REFERENCES source_log(source_id),
    PRIMARY KEY (faculty_id, year)
);

CREATE TABLE IF NOT EXISTS company_master (
    company_id       TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    industry         TEXT,
    hiring_count     INTEGER,
    starting_salary  INTEGER,               -- 円（大卒初任給・公開値）
    locations        TEXT,
    transfer_policy  TEXT,
    career_system    TEXT,
    recruit_url      TEXT,
    source_id        TEXT REFERENCES source_log(source_id)
);

-- 企業名の正規化辞書（原文 → 分析用企業ID）
CREATE TABLE IF NOT EXISTS company_alias (
    alias_normalized TEXT PRIMARY KEY,
    company_id       TEXT NOT NULL REFERENCES company_master(company_id)
);

CREATE TABLE IF NOT EXISTS employment_company (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id     TEXT NOT NULL,
    faculty_id        TEXT NOT NULL,
    year              INTEGER NOT NULL,
    company_id        TEXT,                 -- 正規化できなかった場合 NULL
    company_name_raw  TEXT NOT NULL,        -- 原文保持
    count             INTEGER,              -- 人数非公開は NULL（0 と区別する）
    listed            INTEGER NOT NULL DEFAULT 1,  -- 掲載有無
    source_id         TEXT REFERENCES source_log(source_id)
);
CREATE INDEX IF NOT EXISTS idx_emp_company_fac ON employment_company(faculty_id, year);
CREATE INDEX IF NOT EXISTS idx_emp_company_cid ON employment_company(company_id);

CREATE TABLE IF NOT EXISTS employment_industry (
    university_id  TEXT NOT NULL,
    faculty_id     TEXT NOT NULL,
    year           INTEGER NOT NULL,
    industry       TEXT NOT NULL,
    count          INTEGER,
    ratio          REAL,
    source_id      TEXT REFERENCES source_log(source_id),
    PRIMARY KEY (faculty_id, year, industry)
);

-- 企業比較用の属性（給与・勤務地・転勤・キャリア 等）。すべて出典付き。
CREATE TABLE IF NOT EXISTS company_attribute (
    company_id  TEXT NOT NULL,
    attribute   TEXT NOT NULL,
    value       TEXT,
    source_id   TEXT REFERENCES source_log(source_id),
    PRIMARY KEY (company_id, attribute)
);

-- 学生意識調査等の集計シグナル
CREATE TABLE IF NOT EXISTS student_signal (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    year       INTEGER NOT NULL,
    segment    TEXT NOT NULL DEFAULT '全体',   -- 全体 / 文系 / 理系
    theme      TEXT NOT NULL,
    metric     TEXT NOT NULL,
    value      REAL,
    unit       TEXT,
    source_id  TEXT REFERENCES source_log(source_id)
);

-- ONE CAREER 等のメタデータ・件数・テーマ分類シグナル（本文は保存しない）
CREATE TABLE IF NOT EXISTS review_signal (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id   TEXT NOT NULL,
    year         INTEGER NOT NULL,
    segment      TEXT NOT NULL DEFAULT '全体',  -- 文理
    theme        TEXT,                          -- テーマ件数系の場合のみ
    signal_type  TEXT NOT NULL,                 -- favorites / rating / selection_reviews / intern_reviews / popularity_rank / theme_mentions
    value        REAL,
    source_id    TEXT REFERENCES source_log(source_id)
);

-- AI 出力キャッシュ（入力データのハッシュで無効化）
CREATE TABLE IF NOT EXISTS ai_cache (
    cache_key   TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
