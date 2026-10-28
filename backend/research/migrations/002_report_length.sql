-- Existing queued and delivered investigations retain the Standard default.
ALTER TABLE sherlock_requests ADD COLUMN IF NOT EXISTS report_length TEXT NOT NULL
    DEFAULT 'standard' CHECK (report_length IN ('brief','standard','detailed'));
