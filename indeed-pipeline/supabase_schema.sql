-- Run this once in your Supabase SQL editor

CREATE TABLE IF NOT EXISTS search_combinations (
  id SERIAL PRIMARY KEY,
  state TEXT NOT NULL,
  search_term TEXT NOT NULL,
  last_used TIMESTAMPTZ,
  results_found INTEGER DEFAULT 0,
  active BOOLEAN DEFAULT TRUE,
  UNIQUE(state, search_term)
);

CREATE TABLE IF NOT EXISTS applied_jobs (
  job_id TEXT PRIMARY KEY,
  company TEXT,
  title TEXT,
  state TEXT,
  search_term TEXT,
  status TEXT,   -- 'success' | 'failed' | 'skipped'
  reason TEXT,
  account_id TEXT,
  applied_date TIMESTAMPTZ DEFAULT NOW()
);

-- Batch / dev test run logs (separate from production applied_jobs)
CREATE TABLE IF NOT EXISTS test_run_logs (
  id         SERIAL PRIMARY KEY,
  run_id     TEXT NOT NULL,        -- shared across one batch run
  job_num    INTEGER,
  url        TEXT,
  url_type   TEXT,                 -- viewjob | smartapply | external
  status     TEXT,                 -- success | failed | skipped | error
  reason     TEXT,
  elapsed_s  FLOAT,
  profile_id TEXT,
  ts         TIMESTAMPTZ DEFAULT NOW()
);

-- Full pipeline execution runs (one row per apply_to_job call in production)
CREATE TABLE IF NOT EXISTS executions (
  id           SERIAL PRIMARY KEY,
  run_id       TEXT,                  -- batch run identifier
  profile_id   TEXT,                  -- AdsPower profile used (e.g. k19td50a)
  job_id       TEXT,                  -- Indeed job key (jk param)
  job_url      TEXT,
  url_type     TEXT,                  -- viewjob | smartapply | external
  status       TEXT,                  -- success | failed | skipped | error
  reason       TEXT,
  steps        INTEGER,               -- number of Gemini loop steps taken
  elapsed_s    FLOAT,
  screenshot_dir TEXT,               -- path to /tmp/playwright_debug/<dir>
  ts           TIMESTAMPTZ DEFAULT NOW()
);

-- Seed initial search combinations
INSERT INTO search_combinations (state, search_term) VALUES
  ('California', 'medical receptionist'),
  ('California', 'front desk medical'),
  ('California', 'medical office receptionist'),
  ('California', 'clinic receptionist'),
  ('Texas', 'medical receptionist'),
  ('Texas', 'front desk medical'),
  ('Florida', 'medical receptionist'),
  ('New York', 'medical receptionist'),
  ('California', 'healthcare receptionist'),
  ('California', 'doctor office receptionist')
ON CONFLICT DO NOTHING;
