# PHASE 4 SPEC: SaaS Productization & Commercial Launch

**Parent:** PRD.MD + PHASE_3_SPEC.md §17 (Phase 4 boundary)
**Prerequisite:** Phases 1-3 complete (pipeline, orchestration, multi-tenant, observability)
**Scope:** Public-facing web app with authentication, Stripe billing integration, horizontal scaling, custom domain/SSL, automated formulation quality feedback loop
**Boundary:** Blueprint only. No application code.
**Date:** 2026-04-20

---

## 0. Phase 4 Objectives

Phase 3 delivered a production-grade multi-tenant system accessible via Slack and folder drops. Phase 4 transforms it into a **commercially viable SaaS product** with:

1. **Authentication & user management** — Clerk-based auth with SSO, team invites, role-based access
2. **Self-service web portal** — Next.js frontend for request submission, job monitoring, and result download (replacing Slack-only UX for enterprises without Slack)
3. **Stripe billing integration** — Usage-based pricing (per solver minute), plan tiers, invoicing
4. **Horizontal scaling** — Queue-based job distribution across multiple OpenClaw gateway instances
5. **Custom domain & SSL** — Production deployment with proper certificates
6. **Formulation quality feedback loop** — Track solver outcomes, identify extraction patterns that lead to infeasibility or poor gaps, feed back into Gemini prompts

---

## 1. Dependency Additions

### `requirements.txt` (appended)

```
# Phase 4 additions
stripe>=10.0.0
clerk-backend-api>=1.0.0
redis>=5.0.0
celery>=5.4.0
boto3>=1.34.0
```

### `package.json` (new — Next.js frontend)

```json
{
  "name": "decisionai-portal",
  "dependencies": {
    "next": "^14.2.0",
    "@clerk/nextjs": "^5.0.0",
    "@stripe/stripe-js": "^4.0.0",
    "tailwindcss": "^3.4.0",
    "swr": "^2.2.0"
  }
}
```

---

## 2. Architecture Overview

```
                    PUBLIC INTERNET
                    ═══════════════
    ┌─────────────────────────────────────────────┐
    │  Next.js Portal (Vercel / Cloudflare Pages)  │
    │  decisionai.kaide.dev                         │
    │  Auth: Clerk | Billing: Stripe               │
    └─────────────────────┬───────────────────────┘
                          │ HTTPS
                          ▼
    ┌─────────────────────────────────────────────┐
    │  FastAPI Gateway (api.decisionai.kaide.dev)   │
    │  - Auth middleware (Clerk JWT verification)   │
    │  - File upload endpoint                       │
    │  - Job status endpoint                        │
    │  - Billing webhook receiver                   │
    │  - WebSocket for live progress                │
    └─────────────────────┬───────────────────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
    ┌──────────────┐ ┌──────────┐ ┌──────────────┐
    │ Redis Queue   │ │ Postgres │ │ S3 / R2      │
    │ (Celery)     │ │ (users,  │ │ (artifacts,  │
    │ Job dispatch │ │  billing)│ │  uploads)    │
    └──────┬───────┘ └──────────┘ └──────────────┘
           │
    ┌──────▼───────────────────────────────────────┐
    │  Worker Pool (1-N OpenClaw Instances)          │
    │  Each worker:                                  │
    │  - Pulls job from Redis queue                  │
    │  - Runs Phase 1-3 pipeline in isolated tenant  │
    │  - Reports progress via Redis pub/sub          │
    │  - Uploads artifacts to S3/R2                  │
    └──────────────────────────────────────────────┘
```

---

## 3. New Pydantic Schemas (`scripts/schemas_v4.py`)

### 3.1 `User` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Clerk user ID |
| `email` | `str` | |
| `name` | `str` | |
| `tenant_id` | `str` | Associated tenant |
| `role` | `Literal["admin", "planner", "viewer"]` | Access level |
| `created_at` | `datetime` | |
| `stripe_customer_id` | `str \| None` | Stripe customer |

### 3.2 `BillingPlan` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `plan_id` | `str` | e.g., "starter", "professional", "enterprise" |
| `name` | `str` | |
| `included_minutes` | `int` | Monthly included solver minutes |
| `overage_rate_per_minute` | `float` | Cost per minute over included |
| `max_concurrent_jobs` | `int` | |
| `max_file_upload_mb` | `int` | |
| `features` | `list[str]` | e.g., ["multi_stage", "qubo", "memory"] |

### 3.3 `Invoice` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | |
| `tenant_id` | `str` | |
| `period` | `str` | "YYYY-MM" |
| `included_minutes` | `int` | |
| `used_minutes` | `int` | |
| `overage_minutes` | `int` | |
| `overage_cost` | `float` | |
| `total_cost` | `float` | |
| `stripe_invoice_id` | `str \| None` | |
| `status` | `Literal["draft", "open", "paid", "void"]` | |

### 3.4 `JobRequest` (BaseModel — API submission)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | UUID |
| `tenant_id` | `str` | |
| `user_id` | `str` | Submitting user |
| `title` | `str` | Human description |
| `files` | `list[UploadedFile]` | S3 keys for uploaded files |
| `instructions` | `str \| None` | Natural language constraints |
| `strategy` | `Literal["auto", "single", "quarterly"]` | |
| `priority` | `Literal["normal", "high"]` | |
| `status` | `Literal["queued", "processing", "awaiting_approval", "submitted", "completed", "failed"]` | |
| `created_at` | `datetime` | |

### 3.5 `UploadedFile` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `filename` | `str` | Original filename |
| `s3_key` | `str` | Storage key |
| `size_bytes` | `int` | |
| `content_type` | `str` | MIME type |
| `uploaded_at` | `datetime` | |

### 3.6 `QualityFeedback` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | `str` | |
| `tenant_id` | `str` | |
| `extraction_quality` | `Literal["good", "acceptable", "poor"]` | User or auto rating |
| `solver_outcome` | `Literal["optimal", "feasible", "infeasible", "timeout"]` | |
| `issues` | `list[str]` | Specific problems identified |
| `corrective_prompt_additions` | `list[str]` | Prompt improvements derived |
| `timestamp` | `datetime` | |

---

## 4. File: `portal/` (Next.js Application)

### 4.1 Page Structure

```
portal/
├── app/
│   ├── layout.tsx              # ClerkProvider + global layout
│   ├── page.tsx                # Landing / marketing page
│   ├── sign-in/[[...sign-in]]/page.tsx
│   ├── sign-up/[[...sign-up]]/page.tsx
│   ├── dashboard/
│   │   ├── layout.tsx          # Authenticated layout
│   │   ├── page.tsx            # Overview: recent jobs, budget gauge
│   │   ├── submit/
│   │   │   └── page.tsx        # File upload + instructions form
│   │   ├── jobs/
│   │   │   ├── page.tsx        # Job list table
│   │   │   └── [id]/page.tsx   # Single job detail + live progress
│   │   ├── billing/
│   │   │   └── page.tsx        # Usage, invoices, plan upgrade
│   │   └── settings/
│   │       └── page.tsx        # Team management, API keys
│   └── api/
│       └── webhooks/
│           ├── clerk/route.ts  # User sync webhook
│           └── stripe/route.ts # Payment webhook
├── components/
│   ├── FileUpload.tsx
│   ├── JobProgressCard.tsx
│   ├── BudgetGauge.tsx
│   └── ApprovalButton.tsx
└── lib/
    ├── api.ts                  # API client (SWR fetcher)
    └── stripe.ts               # Stripe checkout helper
```

### 4.2 Key User Flows

**Submit Request:**
1. User uploads files via drag-and-drop (`FileUpload.tsx`)
2. Files uploaded directly to S3/R2 via pre-signed URL
3. User adds optional NL instructions
4. Clicks "Submit" → POST `/api/v1/requests` → job queued
5. Redirected to job detail page

**Monitor Progress:**
1. Job detail page (`/dashboard/jobs/[id]`)
2. WebSocket connection to `/ws/jobs/{id}`
3. Real-time updates: extraction → validation → compilation → solver progress
4. Shows objective, bound, gap, wall_time in live chart

**Approve Submission:**
1. After extraction preview, portal shows approval card
2. User clicks "APPROVE" → PATCH `/api/v1/requests/{id}/approve`
3. Equivalent to Slack APPROVE (same backend path)

### 4.3 Authentication (Clerk)

| Feature | Implementation |
|---------|---------------|
| Sign up/in | Clerk hosted UI components |
| SSO | Google, Microsoft via Clerk |
| JWT verification | Clerk middleware in FastAPI (`clerk-backend-api`) |
| Team invites | Clerk organizations → mapped to tenants |
| Role enforcement | `role` claim in JWT → checked per endpoint |

---

## 5. File: `api/v1/` (Extended FastAPI)

### 5.1 New Route Module Structure

```
api/
├── server.py                   # (Phase 3 — internal metrics, kept)
├── v1/
│   ├── __init__.py
│   ├── app.py                  # Main FastAPI app with Clerk middleware
│   ├── auth.py                 # Clerk JWT verification
│   ├── routes/
│   │   ├── requests.py         # POST/GET/PATCH job requests
│   │   ├── files.py            # Pre-signed upload URLs
│   │   ├── billing.py          # Usage, invoices, plan management
│   │   ├── tenants.py          # Tenant CRUD (admin only)
│   │   └── webhooks.py         # Stripe + Clerk webhooks
│   ├── workers.py              # Celery task definitions
│   └── ws.py                   # WebSocket live progress
```

### 5.2 API Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/v1/requests` | planner+ | Create new optimization request |
| `GET` | `/v1/requests` | viewer+ | List requests for tenant |
| `GET` | `/v1/requests/{id}` | viewer+ | Get request detail + progress |
| `PATCH` | `/v1/requests/{id}/approve` | planner+ | Approve for solver submission |
| `DELETE` | `/v1/requests/{id}` | admin | Cancel/delete request |
| `POST` | `/v1/files/upload-url` | planner+ | Get pre-signed S3 upload URL |
| `GET` | `/v1/files/{key}` | viewer+ | Get pre-signed download URL |
| `GET` | `/v1/billing/usage` | viewer+ | Current period usage |
| `GET` | `/v1/billing/invoices` | admin | Invoice history |
| `POST` | `/v1/billing/checkout` | admin | Create Stripe checkout session |
| `POST` | `/v1/webhooks/stripe` | none (sig verified) | Stripe event handler |
| `POST` | `/v1/webhooks/clerk` | none (sig verified) | Clerk user sync |
| `WS` | `/v1/ws/jobs/{id}` | viewer+ | Live job progress stream |

### 5.3 Auth Middleware

```python
from clerk_backend_api import Clerk

clerk = Clerk(api_key=os.environ["CLERK_SECRET_KEY"])

async def verify_token(authorization: str) -> User:
    """Extract and verify Clerk JWT. Returns User with tenant_id and role."""
    token = authorization.replace("Bearer ", "")
    session = clerk.sessions.verify_token(token)
    # Map Clerk org membership → tenant_id + role
    return User(...)
```

### 5.4 Role-Based Access Control

| Role | Can Submit | Can Approve | Can View | Can Manage Billing | Can Admin |
|------|-----------|-------------|----------|-------------------|-----------|
| viewer | No | No | Yes | No | No |
| planner | Yes | Yes | Yes | No | No |
| admin | Yes | Yes | Yes | Yes | Yes |

---

## 6. File: `api/v1/workers.py` (Celery Tasks)

### 6.1 Task: `process_request`

```python
@celery_app.task(bind=True, max_retries=2)
def process_request(self, request_id: str, tenant_id: str):
    """
    Main worker task. Runs the full Phase 1-3 pipeline for a request.
    Pulled from Redis queue by available worker.
    """
```

**Flow:**
```
1. Download files from S3 → tenant staging directory
2. Run Phase 1: classify → extract → validate → compile
3. Publish progress events to Redis pub/sub channel: f"job:{request_id}"
4. IF multi-stage detected: run Phase 2 orchestration
5. After APPROVE received (via API): run solver submission
6. Record cost (Phase 3 cost_tracker)
7. Upload artifacts (.mps, .lp, solution) to S3
8. Update request status in Postgres
9. Notify via WebSocket (Redis pub/sub → WS bridge)
```

### 6.2 Task: `check_approval`

```python
@celery_app.task
def check_approval(request_id: str):
    """Poll for approval status. Called periodically until approved or timeout."""
```

### 6.3 Celery Configuration

```python
celery_app = Celery('decisionai')
celery_app.config_from_object({
    'broker_url': os.environ['REDIS_URL'],
    'result_backend': os.environ['REDIS_URL'],
    'task_serializer': 'json',
    'task_time_limit': 14400,  # 4 hours (matches HybridSolver max)
    'task_soft_time_limit': 14100,
    'worker_concurrency': 2,  # Per worker instance
    'task_routes': {
        'process_request': {'queue': 'optimization'},
        'check_approval': {'queue': 'default'},
    }
})
```

---

## 7. Stripe Billing Integration

### 7.1 Plan Tiers

| Plan | Included Minutes | Overage | Max Concurrent | Price |
|------|-----------------|---------|----------------|-------|
| Starter | 50 | $2.00/min | 1 | $99/mo |
| Professional | 200 | $1.50/min | 3 | $349/mo |
| Enterprise | 1000 | $1.00/min | 10 | Custom |

### 7.2 Stripe Objects

| Object | Purpose |
|--------|---------|
| `Product` | One per plan tier |
| `Price` | Monthly subscription price |
| `Customer` | One per tenant |
| `Subscription` | Active plan for tenant |
| `UsageRecord` | Reported solver minutes (metered billing) |
| `Invoice` | Monthly invoice with included + overage |

### 7.3 Billing Flow

```
1. Tenant admin clicks "Upgrade" in portal
2. Portal creates Stripe Checkout Session via /v1/billing/checkout
3. User completes payment on Stripe hosted page
4. Stripe webhook → /v1/webhooks/stripe (event: checkout.session.completed)
5. Backend activates subscription, updates tenant config
6. On each solver job completion:
   - Report usage: stripe.SubscriptionItem.create_usage_record(minutes)
   - Update cost_tracker.db
7. Monthly: Stripe auto-generates invoice with base + overage
8. Webhook: invoice.paid → mark tenant as current
```

### 7.4 Budget Enforcement (Enhanced)

Pre-submission check now includes Stripe plan limits:
```
1. Load tenant's active Stripe subscription
2. Get plan's included_minutes
3. Get current period usage from cost_tracker.db
4. IF usage >= included_minutes AND no overage allowed (starter): HALT
5. IF usage >= included_minutes AND overage allowed: proceed with warning
6. Check max_concurrent_jobs: count active jobs for tenant
```

---

## 8. File: `scripts/quality_feedback.py`

**Purpose:** Automated formulation quality assessment. After solver completes, analyze outcome and improve extraction prompts.

### 8.1 CLI Interface

```
python3 scripts/quality_feedback.py <run_dir> --tenant <id>
```

### 8.2 Logic

```
1. Load submission.json → check solver outcome
2. Classify quality:
   - "optimal" (gap < 1%): quality = "good"
   - "feasible" (gap 1-10%): quality = "acceptable"
   - "infeasible" or "timeout" (gap > 10%): quality = "poor"
3. IF quality == "poor":
   a. Load constraint_bundle.json
   b. Analyze patterns:
      - Too many constraints relative to variables? → over-extraction
      - Conflicting constraints? → ambiguity not resolved
      - Very large/small coefficients? → unit normalization failure
   c. Generate corrective_prompt_additions via Gemini Flash:
      "Given this solver failure, what extraction guidance should be added?"
   d. Append to tenant-specific prompt additions file
4. Write QualityFeedback record
5. If feedback accumulates (>5 poor results for same tenant):
   - Post alert to Slack: "Extraction quality degrading for {tenant}. Review recommended."
```

### 8.3 Prompt Improvement File

```
~/opt-workspace/tenants/<tenant_id>/prompt_additions.md

## Learned Extraction Guidance

- For ACME data: capacity columns are always in metric tons, not kg
- For ACME data: "overtime" refers to hours beyond 8h shift, not weekend work
- When demand forecast has >12 SKUs, split into product families first
```

This file is loaded by `gemini_client.py extract` as additional system prompt context (appended to prior_context from MEMORY.md).

---

## 9. Infrastructure & Deployment

### 9.1 Services Map

| Service | Platform | Purpose |
|---------|----------|---------|
| Next.js Portal | Vercel / Cloudflare Pages | Frontend |
| FastAPI v1 | Cloud Run / Railway | API gateway |
| Celery Workers | Cloud Run Jobs / EC2 | Pipeline execution |
| Redis | Upstash / ElastiCache | Queue + pub/sub |
| PostgreSQL | Neon / Supabase | Users, billing, request state |
| S3/R2 | Cloudflare R2 / AWS S3 | File storage |
| Clerk | Clerk.com | Auth provider |
| Stripe | Stripe.com | Billing |

### 9.2 Environment Variables (Production)

```
# Auth
CLERK_SECRET_KEY=sk_live_...
CLERK_PUBLISHABLE_KEY=pk_live_...
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...

# Billing
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_STARTER=price_...
STRIPE_PRICE_PROFESSIONAL=price_...

# Infrastructure
REDIS_URL=redis://...
DATABASE_URL=postgresql://...
S3_BUCKET=decisionai-artifacts
S3_REGION=auto
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...

# Existing (from Phase 1-3)
QUANTAGONIA_API_KEY=...
GEMINI_API_KEY=...
SLACK_BOT_TOKEN=...
```

### 9.3 Custom Domain & SSL

| Domain | Service | SSL |
|--------|---------|-----|
| `decisionai.kaide.dev` | Portal (Vercel) | Auto (Let's Encrypt) |
| `api.decisionai.kaide.dev` | FastAPI (Cloud Run) | Managed |
| `ws.decisionai.kaide.dev` | WebSocket (Cloud Run) | Managed |

---

## 10. Database Schema (PostgreSQL)

### 10.1 Tables

```sql
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

-- Tenants
CREATE TABLE tenants (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    stripe_subscription_id TEXT,
    plan_id TEXT DEFAULT 'starter',
    active BOOLEAN DEFAULT TRUE,
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
```

---

## 11. WebSocket Progress Protocol

### 11.1 Connection

```
ws://api.decisionai.kaide.dev/v1/ws/jobs/{request_id}
Authorization: Bearer <clerk_jwt>
```

### 11.2 Message Types (server → client)

```json
{"type": "status_change", "status": "processing", "timestamp": "..."}
{"type": "extraction_preview", "variables": 12, "constraints": 34, "ambiguities": 2}
{"type": "validation", "passed": true, "errors": 0, "warnings": 3}
{"type": "compilation", "variables": 12, "constraints": 34, "mps_size_bytes": 4567}
{"type": "awaiting_approval", "preview": "..."}
{"type": "solver_progress", "objective": 145.2, "bound": 140.0, "gap": 0.035, "wall_time": 120}
{"type": "completed", "objective": 145.2, "gap": 0.001, "billed_minutes": 3}
{"type": "error", "message": "Budget exceeded", "code": "BUDGET_EXCEEDED"}
```

### 11.3 Implementation

Redis pub/sub bridge:
- Workers publish progress to channel `job:{request_id}`
- WebSocket handler subscribes to channel, forwards to connected clients
- On disconnect: unsubscribe

---

## 12. Testing Strategy (Phase 4)

### 12.1 Unit Tests

| File | Coverage |
|------|----------|
| `tests/test_auth.py` | Clerk JWT verification, role enforcement |
| `tests/test_billing.py` | Stripe webhook handling, usage recording, invoice generation |
| `tests/test_workers.py` | Celery task execution, retry behavior, progress publishing |
| `tests/test_quality_feedback.py` | Quality classification, prompt improvement generation |
| `tests/test_api_routes.py` | All v1 endpoints with mocked auth |

### 12.2 Integration Test

**Scenario:** Full user journey:
1. Sign up → Clerk org created → tenant provisioned
2. Select Starter plan → Stripe checkout → subscription active
3. Upload files → job queued → worker picks up
4. Extraction → validation → approval (via portal) → submission
5. Solver completes → cost recorded → Stripe usage reported
6. Quality feedback generated → prompt additions written

### 12.3 Load Test

- 10 concurrent tenants, 3 jobs each
- Verify: no cross-tenant leakage, budget enforcement holds, WebSocket doesn't drop

---

## 13. Anti-Replication Verification (Phase 4)

- [ ] Portal only displays solver results, never executes solver logic
- [ ] API server routes requests to workers, never solves math
- [ ] Celery workers delegate to `submit_hybridsolver.py` subprocess, never solve inline
- [ ] Quality feedback analyzes outcomes but never modifies solver behavior
- [ ] Stripe billing reports minutes FROM Quantagonia, never estimates or inflates

---

## 14. Migration from Phase 3

| Phase 3 Component | Phase 4 Replacement |
|-------------------|---------------------|
| Local SQLite `cost_tracker.db` | PostgreSQL `billing_records` + Stripe metered billing |
| Local `tenants.json` | PostgreSQL `tenants` table + Clerk organizations |
| Streamlit dashboard | Next.js portal (internal Streamlit retained for ops) |
| Slack-only approval | Portal approval button + Slack (both paths remain) |
| Direct file drops | S3 upload via pre-signed URL + folder drops (both) |
| Single gateway | Worker pool behind Redis queue |

---

*End of Phase 4 Spec.*
