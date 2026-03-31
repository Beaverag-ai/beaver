-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Vector chunks table (replaces external Qdrant storage)
CREATE TABLE IF NOT EXISTS vector_chunks (
    id VARCHAR(255) PRIMARY KEY,
    collection VARCHAR(255) NOT NULL DEFAULT 'beaver_knowledge',
    embedding vector,
    document_id VARCHAR(255),
    user_id VARCHAR(255),
    chunk_index INTEGER,
    text TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for filtering
CREATE INDEX IF NOT EXISTS idx_vector_chunks_user_id ON vector_chunks (user_id);
CREATE INDEX IF NOT EXISTS idx_vector_chunks_document_id ON vector_chunks (document_id);
CREATE INDEX IF NOT EXISTS idx_vector_chunks_collection ON vector_chunks (collection);
