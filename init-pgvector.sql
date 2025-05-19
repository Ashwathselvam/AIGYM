-- Enable pgvector extension for the database
CREATE EXTENSION IF NOT EXISTS vector;
 
-- Ensure the extension is accessible
ALTER DATABASE current_database() SET search_path TO "$user", public; 