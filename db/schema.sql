-- =============================================================================
-- KDAC-2 Resume Screening & Talent Analytics Platform
-- Star Schema DDL
-- =============================================================================
-- Auto-executed on first Postgres container start via /docker-entrypoint-initdb.d/

-- Dimension: Candidates
CREATE TABLE IF NOT EXISTS dim_candidate (
    candidate_id SERIAL PRIMARY KEY,
    name TEXT,
    email TEXT,
    education TEXT,
    university TEXT,
    experience_years NUMERIC,
    location TEXT,
    most_recent_title TEXT,
    job_family TEXT,
    resume_filename TEXT
);

-- Dimension: Jobs
CREATE TABLE IF NOT EXISTS dim_job (
    job_id SERIAL PRIMARY KEY,
    title TEXT,
    department TEXT,
    company TEXT,
    location TEXT,
    job_family TEXT,
    required_skills TEXT[],
    required_experience NUMERIC,
    description TEXT
);

-- Dimension: Skills
CREATE TABLE IF NOT EXISTS dim_skill (
    skill_id SERIAL PRIMARY KEY,
    skill_name TEXT UNIQUE,
    category TEXT
);

-- Dimension: Companies
CREATE TABLE IF NOT EXISTS dim_company (
    company_id SERIAL PRIMARY KEY,
    name TEXT,
    industry TEXT
);

-- Dimension: Time
CREATE TABLE IF NOT EXISTS dim_time (
    date_id SERIAL PRIMARY KEY,
    full_date DATE UNIQUE,
    day INT,
    month INT,
    quarter INT,
    year INT
);

-- Bridge: Candidate ↔ Skill (many-to-many)
CREATE TABLE IF NOT EXISTS bridge_candidate_skill (
    candidate_id INT REFERENCES dim_candidate(candidate_id),
    skill_id INT REFERENCES dim_skill(skill_id),
    PRIMARY KEY (candidate_id, skill_id)
);

-- Fact: Applications (candidate-job match scores)
CREATE TABLE IF NOT EXISTS fact_applications (
    application_id SERIAL PRIMARY KEY,
    candidate_id INT REFERENCES dim_candidate(candidate_id),
    job_id INT REFERENCES dim_job(job_id),
    date_id INT REFERENCES dim_time(date_id),
    semantic_score NUMERIC,
    skill_overlap_score NUMERIC,
    experience_score NUMERIC,
    final_score NUMERIC,
    applied_date DATE,
    insight_text TEXT
);

-- Populate initial time dimension for current year ± 1
INSERT INTO dim_time (full_date, day, month, quarter, year)
SELECT
    d::date,
    EXTRACT(DAY FROM d)::int,
    EXTRACT(MONTH FROM d)::int,
    EXTRACT(QUARTER FROM d)::int,
    EXTRACT(YEAR FROM d)::int
FROM generate_series(
    (CURRENT_DATE - INTERVAL '1 year')::date,
    (CURRENT_DATE + INTERVAL '1 year')::date,
    '1 day'::interval
) AS d
ON CONFLICT (full_date) DO NOTHING;
