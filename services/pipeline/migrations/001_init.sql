-- 001: the Assignment 1 pipeline schema, ported from SQLite to SQL Server.
-- Never edit this file once applied; schema changes go in a new numbered migration.

CREATE TABLE applications (
    id               INT IDENTITY(1,1) PRIMARY KEY,
    company          NVARCHAR(200) NOT NULL,
    role             NVARCHAR(200) NOT NULL,
    source           NVARCHAR(20)  NOT NULL
        CHECK (source IN ('referral','job_board','cold_apply','other')),
    date_applied     DATE NOT NULL,
    current_stage    NVARCHAR(30) NOT NULL DEFAULT 'applied'
        CHECK (current_stage IN ('applied','phone_screen','technical_assessment','interview',
                                 'final_round','offer','rejected','withdrawn','accepted')),
    salary_range_min INT NULL,
    salary_range_max INT NULL,
    status           NVARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','rejected','withdrawn','accepted')),
    CONSTRAINT ck_salary CHECK (salary_range_min IS NULL OR salary_range_max IS NULL
                                OR salary_range_min <= salary_range_max)
);
GO

-- Append-only: one row per stage the application enters.
CREATE TABLE stage_history (
    id             INT IDENTITY(1,1) PRIMARY KEY,
    application_id INT NOT NULL REFERENCES applications(id),
    stage          NVARCHAR(30) NOT NULL
        CHECK (stage IN ('applied','phone_screen','technical_assessment','interview',
                         'final_round','offer','rejected','withdrawn','accepted')),
    entered_at     DATETIME2(0) NOT NULL
);
GO

CREATE INDEX idx_stage_history_application ON stage_history (application_id, entered_at);
GO

-- Used only by GET /health to prove the service can write (the insert is rolled back).
CREATE TABLE health_check (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    checked_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
