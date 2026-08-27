-- Migration 001: Create conversations and messages tables
-- Purpose: Support multi-turn conversation system (SPEC-0005)
-- Created: 2026-08-27
-- Note: SQLite-compatible syntax

-- Drop tables if they exist (for clean development)
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS conversations;

-- Conversation main table
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT
);

-- Create indexes
CREATE INDEX idx_patient_id ON conversations(patient_id);
CREATE INDEX idx_updated_at ON conversations(updated_at DESC);

-- Messages table
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    context_refs TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX idx_conversation ON messages(conversation_id, timestamp);

-- Insert sample data for testing (optional, can be removed in production)
-- INSERT INTO conversations (id, patient_id, title, metadata) VALUES
--     ('550e8400-e29b-41d4-a716-446655440001', '0x262Ee58D3e7A782ceC68094A6DACb53D02Fa9d0B', '头痛诊断', '{"diagnosisId": "20260825181145_0b8c6d162a6e7b45"}');
-- 
-- INSERT INTO messages (id, conversation_id, role, content) VALUES
--     ('660e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440001', 'user', '我头痛已经 3 天了'),
--     ('660e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440001', 'assistant', '根据您的描述，头痛可能由多种原因引起...');
