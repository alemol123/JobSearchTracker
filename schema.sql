-- Runs on every startup; IF NOT EXISTS makes it safe to run repeatedly.

-- ===== Domain 1: Application Pipeline =====

CREATE TABLE IF NOT EXISTS applications (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    company          TEXT    NOT NULL,
    role             TEXT    NOT NULL,
    source           TEXT    NOT NULL
                     CHECK (source IN ('referral', 'job_board', 'cold_apply', 'other')),
    date_applied     TEXT    NOT NULL,              -- ISO date, YYYY-MM-DD
    current_stage    TEXT    NOT NULL DEFAULT 'applied'
                     CHECK (current_stage IN ('applied', 'phone_screen', 'technical_assessment',
                                              'interview', 'final_round', 'offer',
                                              'rejected', 'withdrawn', 'accepted')),
    salary_range_min INTEGER,
    salary_range_max INTEGER,
    status           TEXT    NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'rejected', 'withdrawn', 'accepted')),
    CHECK (salary_range_min IS NULL OR salary_range_max IS NULL
           OR salary_range_min <= salary_range_max)
);

-- Append-only: one row per stage the application enters.
CREATE TABLE IF NOT EXISTS stage_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    stage          TEXT    NOT NULL
                   CHECK (stage IN ('applied', 'phone_screen', 'technical_assessment',
                                    'interview', 'final_round', 'offer',
                                    'rejected', 'withdrawn', 'accepted')),
    entered_at     TEXT    NOT NULL                 -- ISO datetime, YYYY-MM-DDTHH:MM:SS
);

CREATE INDEX IF NOT EXISTS idx_stage_history_application
    ON stage_history (application_id, entered_at);

-- ===== Domain 2: Skill Gap Tracker =====

CREATE TABLE IF NOT EXISTS skills (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    category TEXT,
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1))   -- soft delete
);

-- One row per skill I have; proficiency is self-reported.
CREATE TABLE IF NOT EXISTS my_skills (
    skill_id          INTEGER PRIMARY KEY REFERENCES skills(id),
    proficiency_level INTEGER NOT NULL CHECK (proficiency_level BETWEEN 1 AND 5)
);

-- Bridge table: the ONLY link between the two domains.
CREATE TABLE IF NOT EXISTS application_skills (
    application_id INTEGER NOT NULL REFERENCES applications(id),
    skill_id       INTEGER NOT NULL REFERENCES skills(id),
    PRIMARY KEY (application_id, skill_id)
);
