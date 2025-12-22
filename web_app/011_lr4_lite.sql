-- LR4-Lite: только таблица contracts. Совместимо с существующими clients.

CREATE TABLE IF NOT EXISTS contracts (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    number      VARCHAR(40) UNIQUE NOT NULL,
    client_id   BIGINT NOT NULL REFERENCES clients(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    principal   NUMERIC(12,2) NOT NULL CHECK (principal > 0),
    status      VARCHAR(16) NOT NULL CHECK (status IN ('Draft','Active','Closed')),
    start_date  DATE NOT NULL,
    end_date    DATE NOT NULL CHECK (end_date >= start_date),
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contracts_client    ON contracts(client_id);
CREATE INDEX IF NOT EXISTS idx_contracts_status    ON contracts(status);
CREATE INDEX IF NOT EXISTS idx_contracts_end_date  ON contracts(end_date);
