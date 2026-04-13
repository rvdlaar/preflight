-- Preflight database initialization
-- Runs automatically when the PostgreSQL container starts for the first time.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE preflight TO preflight;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO preflight;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO preflight;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO preflight;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO preflight;