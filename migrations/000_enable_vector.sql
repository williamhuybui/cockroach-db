-- Enable CockroachDB vector-index support.
--
-- This is required because the transcripts table contains an embedding
-- column and a vector index for semantic transcript search.
SET CLUSTER SETTING feature.vector_index.enabled = true;