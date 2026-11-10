-- 001: the Assignment 1 skills schema, ported from SQLite to SQL Server.
-- Never edit this file once applied; schema changes go in a new numbered migration.

CREATE TABLE skills (
    id       INT IDENTITY(1,1) PRIMARY KEY,
    name     NVARCHAR(50) NOT NULL UNIQUE,   -- default collation is case-insensitive (was COLLATE NOCASE)
    category NVARCHAR(50) NULL,
    archived BIT NOT NULL DEFAULT 0          -- soft delete
);
GO

-- One row per skill I have; proficiency is self-reported.
CREATE TABLE my_skills (
    skill_id          INT PRIMARY KEY REFERENCES skills(id),
    proficiency_level INT NOT NULL CHECK (proficiency_level BETWEEN 1 AND 5)
);
GO

-- application_id is a plain ID now: the applications table lives in the pipeline database,
-- so there is no foreign key. Existence is checked over HTTP when tagging.
CREATE TABLE application_skills (
    application_id INT NOT NULL,
    skill_id       INT NOT NULL REFERENCES skills(id),
    PRIMARY KEY (application_id, skill_id)
);
GO

-- Used only by GET /health to prove the service can write (the insert is rolled back).
CREATE TABLE health_check (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    checked_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
