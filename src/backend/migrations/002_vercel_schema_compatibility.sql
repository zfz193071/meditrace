-- Reconcile the initial Neon tables with the conversation API without dropping data.
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS patient_id VARCHAR(42) NOT NULL DEFAULT '';
ALTER TABLE conversations ALTER COLUMN patient_id DROP DEFAULT;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS metadata JSONB;

ALTER TABLE messages ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS context_refs JSONB;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'messages' AND column_name = 'created_at'
    ) THEN
        UPDATE messages SET timestamp = created_at WHERE timestamp IS NULL;
    END IF;
END $$;

ALTER TABLE messages ALTER COLUMN timestamp SET DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_patient_id ON conversations(patient_id);
CREATE INDEX IF NOT EXISTS idx_updated_at ON conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation ON messages(conversation_id, timestamp);
