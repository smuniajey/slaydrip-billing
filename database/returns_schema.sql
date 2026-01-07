-- Return & Exchange tables (run once on your DB)

-- Main returns log (one row per returned item)
CREATE TABLE IF NOT EXISTS returns (
    id BIGSERIAL PRIMARY KEY,
    return_ref VARCHAR(50) NOT NULL,
    invoice_no VARCHAR(50) NOT NULL,
    design_id INTEGER NOT NULL,
    size VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    refund_amount NUMERIC(12,2) NOT NULL,
    return_type VARCHAR(10) NOT NULL CHECK (return_type IN ('RETURN','EXCHANGE')),
    payment_mode VARCHAR(10) NOT NULL CHECK (payment_mode IN ('Cash','UPI','Card')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_returns_invoice ON returns (invoice_no);
CREATE INDEX IF NOT EXISTS idx_returns_design_size ON returns (design_id, size);
CREATE INDEX IF NOT EXISTS idx_returns_ref ON returns (return_ref);

-- New items issued during an exchange (optional but recommended)
CREATE TABLE IF NOT EXISTS exchange_details (
    id BIGSERIAL PRIMARY KEY,
    exchange_ref VARCHAR(50) NOT NULL,
    invoice_no VARCHAR(50) NOT NULL,
    design_id INTEGER NOT NULL,
    size VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12,2) NOT NULL,
    line_total NUMERIC(12,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exchange_ref ON exchange_details (exchange_ref);
CREATE INDEX IF NOT EXISTS idx_exchange_invoice ON exchange_details (invoice_no);
