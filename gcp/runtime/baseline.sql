-- Additive baseline equivalent to Alembic revision 0005. Only for an empty DB.
-- Historical upgrades 0002/0003 change/remove older structures and rows; those
-- upgrades must never be replayed by the GCP initializer.
CREATE TABLE users (
    id UUID DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    cognito_sub VARCHAR(64) NOT NULL,
    email VARCHAR(320) NOT NULL,
    name VARCHAR(120) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_users_cognito_sub UNIQUE (cognito_sub)
);
CREATE TABLE items (
    id UUID DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'todo' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    owner_id UUID NOT NULL,
    completed_at TIMESTAMPTZ,
    agenda JSONB,
    ai_suggestion JSONB,
    CONSTRAINT ck_items_status CHECK (status IN ('todo', 'in_progress', 'done')),
    CONSTRAINT items_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX ix_items_created_at ON items (created_at);
CREATE INDEX ix_items_owner_id ON items (owner_id);
CREATE INDEX ix_items_completed_at ON items (completed_at);
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO alembic_version (version_num) VALUES ('0005');
