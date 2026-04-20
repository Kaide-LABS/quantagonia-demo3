-- Tenants (must be created first — referenced by users and other tables)
CREATE TABLE tenants (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    stripe_subscription_id TEXT,
    plan_id TEXT DEFAULT 'starter',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users (synced from Clerk webhooks)
CREATE TABLE users (
    id TEXT PRIMARY KEY,            -- Clerk user ID
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    tenant_id TEXT REFERENCES tenants(id),
    role TEXT NOT NULL DEFAULT 'viewer',
    stripe_customer_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Requests
CREATE TABLE requests (
    id TEXT PRIMARY KEY,
    tenant_id TEXT REFERENCES tenants(id),
    user_id TEXT REFERENCES users(id),
    title TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    strategy TEXT DEFAULT 'auto',
    priority TEXT DEFAULT 'normal',
    celery_task_id TEXT,
    result_summary JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Uploaded files
CREATE TABLE uploaded_files (
    id TEXT PRIMARY KEY,
    request_id TEXT REFERENCES requests(id),
    filename TEXT NOT NULL,
    s3_key TEXT NOT NULL,
    size_bytes INTEGER,
    content_type TEXT,
    uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

-- Billing records (mirrors cost_tracker.db but in Postgres for queries)
CREATE TABLE billing_records (
    id TEXT PRIMARY KEY,
    tenant_id TEXT REFERENCES tenants(id),
    request_id TEXT REFERENCES requests(id),
    job_id TEXT,
    billed_minutes INTEGER NOT NULL,
    stripe_usage_record_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Quality feedback
CREATE TABLE quality_feedback (
    id TEXT PRIMARY KEY,
    request_id TEXT REFERENCES requests(id),
    tenant_id TEXT REFERENCES tenants(id),
    extraction_quality TEXT,
    solver_outcome TEXT,
    issues JSONB DEFAULT '[]',
    corrective_additions JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
