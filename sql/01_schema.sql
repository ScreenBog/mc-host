CREATE TYPE server_status AS ENUM ('PROVISIONING', 'RUNNING', 'STOPPED', 'SUSPENDED', 'TERMINATED');
CREATE TYPE server_type AS ENUM ('VANILLA', 'PAPER', 'PURPUR', 'FABRIC', 'FORGE', 'NEOFORGE');
CREATE TYPE invoice_status AS ENUM ('PENDING', 'SUCCEEDED', 'CANCELED');
CREATE TYPE mod_source AS ENUM ('MODRINTH', 'CURSEFORGE', 'CUSTOM');

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE plans (
    id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    cpu_cores NUMERIC(3, 1) NOT NULL,
    ram_mb INTEGER NOT NULL,
    disk_mb INTEGER NOT NULL,
    price_monthly NUMERIC(10, 2) NOT NULL
);

CREATE TABLE servers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    plan_id VARCHAR(32) REFERENCES plans(id) NOT NULL,
    name VARCHAR(64) NOT NULL,
    subdomain VARCHAR(64) UNIQUE NOT NULL,
    container_id VARCHAR(128),
    server_type server_type DEFAULT 'PAPER' NOT NULL,
    game_version VARCHAR(32) DEFAULT '1.20.4' NOT NULL,
    status server_status DEFAULT 'PROVISIONING' NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    server_id UUID REFERENCES servers(id) ON DELETE SET NULL,
    yookassa_payment_id VARCHAR(64) UNIQUE,
    amount NUMERIC(10, 2) NOT NULL,
    status invoice_status DEFAULT 'PENDING' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE installed_mods (
    id BIGSERIAL PRIMARY KEY,
    server_id UUID REFERENCES servers(id) ON DELETE CASCADE NOT NULL,
    source mod_source NOT NULL,
    external_id VARCHAR(64) NOT NULL,
    file_id VARCHAR(64) NOT NULL,
    name VARCHAR(256) NOT NULL,
    file_name VARCHAR(256) NOT NULL,
    installed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_server_mod UNIQUE (server_id, source, external_id)
);

-- Operational extras used by billing, DNS and lease lifecycle.
ALTER TABLE invoices
    ADD COLUMN metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN purpose VARCHAR(32) NOT NULL DEFAULT 'CREATE';

ALTER TABLE servers
    ADD COLUMN dns_record_id VARCHAR(64),
    ADD COLUMN renewal_notified_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN suspended_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX idx_servers_user_id ON servers(user_id);
CREATE INDEX idx_servers_status ON servers(status);
CREATE INDEX idx_servers_expires_at ON servers(expires_at);
CREATE INDEX idx_invoices_user_id ON invoices(user_id);
CREATE INDEX idx_invoices_status ON invoices(status);
