CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS sync;
CREATE SCHEMA IF NOT EXISTS metrics;
CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS core.sources (
  id UUID PRIMARY KEY,
  youtube_url TEXT NOT NULL,
  title TEXT,
  channel TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.episodes (
  id UUID PRIMARY KEY,
  source_id UUID REFERENCES core.sources(id),
  status TEXT NOT NULL DEFAULT 'PENDING',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.episode_steps (
  id UUID PRIMARY KEY,
  episode_id UUID REFERENCES core.episodes(id),
  step_name TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  error TEXT
);

CREATE TABLE IF NOT EXISTS core.artifacts (
  id UUID PRIMARY KEY,
  episode_id UUID REFERENCES core.episodes(id),
  kind TEXT NOT NULL,
  uri TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.evidence_units (
  id UUID PRIMARY KEY,
  episode_id UUID REFERENCES core.episodes(id),
  source_url TEXT NOT NULL,
  start_ms INTEGER NOT NULL,
  end_ms INTEGER NOT NULL,
  text TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.context_cards (
  id UUID PRIMARY KEY,
  episode_id UUID REFERENCES core.episodes(id),
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  key_points JSONB NOT NULL,
  citations JSONB NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.embeddings (
  id UUID PRIMARY KEY,
  episode_id UUID REFERENCES core.episodes(id),
  object_type TEXT NOT NULL,
  object_id UUID NOT NULL,
  embedding vector(768) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evidence_units_episode ON core.evidence_units (episode_id);
CREATE INDEX IF NOT EXISTS idx_context_cards_episode_status ON core.context_cards (episode_id, status);
CREATE INDEX IF NOT EXISTS idx_embeddings_object ON core.embeddings (object_type, object_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON core.embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
