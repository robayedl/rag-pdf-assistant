-- Migration 005: DOCX support
-- Adds source_type to documents.
-- Run manually or applied automatically via _init_db() on startup.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS source_type  VARCHAR NOT NULL DEFAULT 'pdf';
