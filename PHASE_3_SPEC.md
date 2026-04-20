# PHASE 3 SPEC: Production Hardening, Multi-Tenant, & Observability

**Parent:** PRD.MD + ULTIMATE_PRD.md + PHASE_2_SPEC.md §13 (Phase 3 boundary)
**Prerequisite:** Phase 1 (single pipeline) + Phase 2 (multi-stage orchestration) complete
**Scope:** Multi-tenant workspace isolation, cost tracking & billing, observability dashboard, CI/CD for model validation, reliability hardening (retries, circuit breakers, rate limiting)
**Boundary:** Blueprint only. No application code.
**Date:** 2026-04-20

---

## 0. Phase 3 Objectives

Phase 2 proved the full optimization pipeline works for a single client in a single workspace. Phase 3 makes it **production-grade for multiple concurrent clients** with:

1. **Multi-tenant workspace isolation** — Each client gets a sandboxed workspace with independent MEMORY.md, no cross-client data leakage
2. **Cost tracking & attribution** — Every HybridSolver job's billed minutes attributed to a client, with configurable budget caps
3. **Observability dashboard** — Real-time Streamlit UI showing pipeline status, solver progress, cost burn, and memory growth
4. **CI/CD for model validation** — Automated testing of the extraction→compilation pipeline against known-good fixtures before production runs
5. **Reliability hardening** — Retry with exponential backoff, circuit breakers on Gemini/Quantagonia APIs, rate limiting for fair multi-tenant use

---

## 1. Dependency Additions

### `requirements.txt` (appended)

```
# Phase 3 additions
streamlit>=1.40.0
fastapi>=0.115.0
uvicorn>=0.32.0
httpx>=0.27.0
tenacity>=9.0.0
prometheus-client>=0.21.0
sqlite-utils>=3.37
```

### Justifications

| Package | Role |
|---------|------|
| `streamlit>=1.40.0` | Observability dashboard (client-facing status view) |
| `fastapi>=0.115.0` | Internal API for webhook triggers, health checks, cost queries |
| `uvicorn>=0.32.0` | ASGI server for FastAPI |
| `httpx>=0.27.0` | Async HTTP client for health probes |
| `tenacity>=9.0.0` | Retry decorator with exponential backoff + circuit breaker |
| `prometheus-client>=0.21.0` | Metrics export (solve time, cost, error rates) |
| `sqlite-utils>=3.37` | Lightweight cost/audit DB (no external dependencies) |

---

## 2. New Pydantic Schemas (`scripts/schemas_v3.py`)

### 2.1 `TenantConfig` (BaseModel)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `tenant_id` | `str` | `pattern=r'^[a-z0-9_-]+$'` | Unique tenant identifier |
| `display_name` | `str` | required | Human-readable name |
| `workspace_path` | `str` | required | Absolute path to tenant workspace |
| `budget_monthly_minutes` | `int \| None` | optional | Monthly HybridSolver budget cap (minutes) |
| `budget_alert_threshold` | `float` | default `0.8` | Alert at this fraction of budget |
| `allowed_planners` | `list[str]` | `min_length=1` | Slack user IDs authorized to APPROVE |
| `gemini_rate_limit_rpm` | `int` | default `30` | Gemini requests per minute for this tenant |
| `solver_concurrency` | `int` | default `2` | Max simultaneous HybridSolver jobs |
| `created_at` | `datetime` | required | |
| `active` | `bool` | default `True` | Whether tenant is active |

### 2.2 `CostRecord` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | UUID |
| `tenant_id` | `str` | |
| `request_id` | `str` | |
| `stage_id` | `str \| None` | For multi-stage plans |
| `job_id` | `str` | HybridSolver job ID |
| `billed_minutes` | `int` | |
| `submitted_at` | `datetime` | |
| `completed_at` | `datetime \| None` | |
| `status` | `str` | |
| `objective` | `float \| None` | |

### 2.3 `BudgetSummary` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `tenant_id` | `str` | |
| `period` | `str` | "YYYY-MM" |
| `total_minutes_used` | `int` | |
| `budget_limit` | `int \| None` | |
| `budget_remaining` | `int \| None` | |
| `jobs_submitted` | `int` | |
| `jobs_succeeded` | `int` | |
| `jobs_failed` | `int` | |
| `alert_triggered` | `bool` | |

### 2.4 `PipelineEvent` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `datetime` | |
| `tenant_id` | `str` | |
| `request_id` | `str` | |
| `event_type` | `str` | e.g., "intake", "validation", "submission", "completion", "error" |
| `details` | `dict[str, Any]` | Event-specific payload |
| `duration_ms` | `int \| None` | Time since previous event in this request |

### 2.5 `HealthStatus` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `status` | `Literal["healthy", "degraded", "unhealthy"]` | |
| `gemini_flash` | `ServiceHealth` | |
| `gemini_pro` | `ServiceHealth` | |
| `hybridsolver` | `ServiceHealth` | |
| `slack` | `ServiceHealth` | |
| `disk_usage_percent` | `float` | |
| `active_jobs` | `int` | |
| `checked_at` | `datetime` | |

### 2.6 `ServiceHealth` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `available` | `bool` | |
| `latency_ms` | `int \| None` | Last probe latency |
| `error_rate_5m` | `float` | Error rate over 5 minutes |
| `circuit_open` | `bool` | Whether circuit breaker is tripped |

---

## 3. File: `scripts/tenant_manager.py`

**Purpose:** Multi-tenant workspace provisioning and isolation. Creates/manages tenant workspaces with independent MEMORY.md and folder structures.

### 3.1 CLI Interface

```
python3 scripts/tenant_manager.py <action> [args...]
```

**Actions:**

| Action | Command | Description |
|--------|---------|-------------|
| `create` | `tenant_manager.py create --id <id> --name <name> --planners U1,U2` | Provision new tenant workspace |
| `list` | `tenant_manager.py list` | List all tenants with status |
| `get` | `tenant_manager.py get <tenant_id>` | Get tenant config |
| `update` | `tenant_manager.py update <tenant_id> --budget 500` | Update tenant settings |
| `deactivate` | `tenant_manager.py deactivate <tenant_id>` | Soft-delete tenant |

### 3.2 Workspace Provisioning Logic

On `create`:
```
1. Validate tenant_id uniqueness against tenants.json registry
2. Create directory structure:
   ~/opt-workspace/tenants/<tenant_id>/
   ├── clients/<tenant_id>/
   │   ├── inbox/
   │   ├── staging/
   │   ├── approved/
   │   ├── runs/
   │   └── outbox/
   ├── MEMORY.md (initialized with tenant header)
   ├── memory/
   └── plans/
3. Write tenant config to ~/opt-workspace/tenants.json (append)
4. Initialize MEMORY.md with: "## Tenant: {display_name}\nCreated: {date}\n"
```

### 3.3 Isolation Guarantees

- Each tenant workspace path is the root for all `watch_inbox.py`, `orchestrate_plan.py`, etc. calls
- OpenClaw's workspace path-escape check prevents cross-tenant access
- MEMORY.md is tenant-scoped (loaded per-tenant, never merged)
- Slack `allowFrom` is tenant-scoped (only authorized planners can APPROVE)

### 3.4 Tenant Registry (`tenants.json`)

```json
{
  "tenants": [
    {
      "tenant_id": "acme",
      "display_name": "ACME Corp",
      "workspace_path": "~/opt-workspace/tenants/acme",
      "budget_monthly_minutes": 500,
      "allowed_planners": ["U0123ABC"],
      "active": true,
      "created_at": "2026-04-20T..."
    }
  ]
}
```

---

## 4. File: `scripts/cost_tracker.py`

**Purpose:** Records all HybridSolver job costs to a local SQLite database. Enforces budget caps. Provides query interface.

### 4.1 CLI Interface

```
python3 scripts/cost_tracker.py <action> [args...]
```

| Action | Command | Description |
|--------|---------|-------------|
| `record` | `cost_tracker.py record --tenant <id> --request <id> --job <id> --minutes <N>` | Record a completed job's cost |
| `check-budget` | `cost_tracker.py check-budget --tenant <id>` | Returns remaining budget (exit 0=ok, 1=exceeded) |
| `summary` | `cost_tracker.py summary --tenant <id> [--period YYYY-MM]` | Monthly cost summary |
| `export` | `cost_tracker.py export [--format json\|csv]` | Export all records |

### 4.2 Database Schema (`cost_tracker.db`)

```sql
CREATE TABLE cost_records (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    stage_id TEXT,
    job_id TEXT NOT NULL,
    billed_minutes INTEGER NOT NULL,
    submitted_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    objective REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tenant_period ON cost_records(tenant_id, submitted_at);
```

### 4.3 Budget Enforcement

Before every `submit_hybridsolver.py` call, the orchestrator must:
```
1. Run: cost_tracker.py check-budget --tenant <id>
2. IF exit code 1 (budget exceeded):
   - Post to Slack: "Budget exceeded for {tenant}. {used}/{limit} minutes used this month."
   - HALT (do not submit)
3. IF budget > alert_threshold:
   - Post warning to Slack but continue
```

### 4.4 Integration Point

`submit_hybridsolver.py` must be modified to call `cost_tracker.py record` after each job completes:
```
python3 scripts/cost_tracker.py record \
  --tenant $TENANT_ID \
  --request $REQUEST_ID \
  --job $JOB_ID \
  --minutes $BILLED_MINUTES
```

---

## 5. File: `scripts/reliability.py`

**Purpose:** Shared retry/circuit-breaker utilities. Wraps Gemini and Quantagonia API calls with resilience patterns.

### 5.1 Public Interface

```python
from reliability import with_retry, CircuitBreaker, RateLimiter

@with_retry(max_attempts=3, backoff_base=2.0, backoff_max=30.0)
def call_gemini(...):
    ...

gemini_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    name="gemini_pro"
)

tenant_limiter = RateLimiter(
    requests_per_minute=30,
    name="tenant_acme_gemini"
)
```

### 5.2 Retry Configuration

| Service | Max Attempts | Backoff | Retry On |
|---------|-------------|---------|----------|
| Gemini Flash | 3 | 2s, 4s, 8s | 429, 500, 503, network error |
| Gemini Pro | 3 | 2s, 4s, 8s | 429, 500, 503, network error |
| HybridSolver submit | 3 | 2s, 4s, 8s | network error only (not job failures) |
| HybridSolver progress | 5 | 1s, 2s, 4s, 8s, 16s | network error, 503 |
| Slack | 3 | 1s, 2s, 4s | 429, network error |

### 5.3 Circuit Breaker

```
States: CLOSED → OPEN → HALF_OPEN → CLOSED

CLOSED: normal operation, count failures
  → OPEN when failure_count >= threshold within window

OPEN: reject all calls immediately, return last error
  → HALF_OPEN after recovery_timeout seconds

HALF_OPEN: allow one probe call
  → CLOSED if probe succeeds
  → OPEN if probe fails (reset timeout)
```

State persisted to `~/opt-workspace/.circuit_breakers.json` so it survives restarts.

### 5.4 Rate Limiter

Token bucket algorithm per tenant per service:
- Configurable `requests_per_minute` from TenantConfig
- Blocks (with backpressure) rather than rejecting
- Ensures fair sharing when multiple tenants are active

---

## 6. File: `dashboard/app.py` (Streamlit)

**Purpose:** Real-time observability dashboard. Shows pipeline status, active jobs, cost burn, and system health.

### 6.1 Launch

```
streamlit run dashboard/app.py --server.port 8501
```

### 6.2 Pages

| Page | Content |
|------|---------|
| **Overview** | Active tenants, total jobs running, system health indicators, cost burn chart |
| **Tenant Detail** | Per-tenant: active requests, stage progress, budget usage, recent memory entries |
| **Job Monitor** | Live job status table: job_id, tenant, stage, objective, gap, wall_time, status |
| **Cost Analysis** | Monthly cost by tenant (bar chart), daily burn rate, budget alerts |
| **System Health** | Service availability, circuit breaker states, error rates, disk usage |

### 6.3 Data Sources

| Data | Source |
|------|--------|
| Active jobs | Scan `tenants/*/runs/*/submission.json` where status=RUNNING |
| Cost data | `cost_tracker.db` via sqlite-utils |
| Health status | `scripts/health_check.py` output |
| Memory growth | Line count of `tenants/*/MEMORY.md` over time |
| Pipeline events | Append-only `pipeline_events.jsonl` |

### 6.4 Auto-Refresh

- Overview page: 10-second refresh interval
- Job Monitor: 5-second refresh
- Cost Analysis: 60-second refresh
- Health: 30-second refresh

---

## 7. File: `scripts/health_check.py`

**Purpose:** Probes all external services and reports health status. Used by dashboard and by OpenClaw cron for alerting.

### 7.1 CLI Interface

```
python3 scripts/health_check.py [--json] [--alert-slack]
```

- **Output (default):** Human-readable status
- **Output (--json):** `HealthStatus` as JSON
- **--alert-slack:** Post to Slack if any service is unhealthy

### 7.2 Probes

| Service | Probe Method | Healthy Criteria |
|---------|-------------|-----------------|
| Gemini Flash | `generate_content("ping")` with 5s timeout | Response in <3s, no error |
| Gemini Pro | `generate_content("ping")` with 10s timeout | Response in <5s, no error |
| HybridSolver | `hybridsolver version` CLI call | Exit code 0 |
| Slack | `client.auth_test()` | Valid response |
| Disk | `shutil.disk_usage()` | <90% used |

### 7.3 Cron Integration

```json5
// Added to ~/.openclaw/openclaw.json
{
  cron: {
    health_check: {
      every: "*/5 * * * *",  // Every 5 minutes
      session: "main",
      payload: {
        kind: "agentTurn",
        message: "Run health check and alert if degraded"
      }
    }
  }
}
```

---

## 8. File: `scripts/pipeline_logger.py`

**Purpose:** Structured event logging for observability. All scripts call this to emit pipeline events to a central JSONL file.

### 8.1 Interface

```python
from pipeline_logger import log_event

log_event(
    tenant_id="acme",
    request_id="req-001",
    event_type="validation_passed",
    details={"errors": 0, "warnings": 2}
)
```

### 8.2 Storage

Events written to `~/opt-workspace/pipeline_events.jsonl` (append-only):
```json
{"timestamp": "2026-04-20T14:30:00Z", "tenant_id": "acme", "request_id": "req-001", "event_type": "validation_passed", "details": {"errors": 0, "warnings": 2}, "duration_ms": 1234}
```

### 8.3 Rotation

- Daily rotation: `pipeline_events.YYYY-MM-DD.jsonl`
- Retention: 30 days (configurable)
- Dashboard reads current + last 7 days

---

## 9. File: `api/server.py` (FastAPI)

**Purpose:** Internal API for webhooks, health checks, and cost queries. Not client-facing — used by dashboard and monitoring.

### 9.1 Launch

```
uvicorn api.server:app --host 0.0.0.0 --port 8080
```

### 9.2 Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Returns HealthStatus JSON |
| `GET` | `/tenants` | List all tenants |
| `GET` | `/tenants/{id}/budget` | Get budget summary |
| `GET` | `/tenants/{id}/jobs` | List recent jobs |
| `GET` | `/metrics` | Prometheus metrics endpoint |
| `POST` | `/webhooks/solver-complete` | Webhook for solver completion (future) |

### 9.3 Prometheus Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `hybridsolver_jobs_total` | Counter | tenant, status | Total jobs submitted |
| `hybridsolver_minutes_total` | Counter | tenant | Total billed minutes |
| `hybridsolver_solve_seconds` | Histogram | tenant | Solve wall time distribution |
| `pipeline_events_total` | Counter | tenant, event_type | Pipeline event counts |
| `gemini_requests_total` | Counter | model, status | Gemini API call counts |
| `circuit_breaker_state` | Gauge | service | 0=closed, 1=open, 2=half_open |

---

## 10. File: `tests/ci_validation.py`

**Purpose:** CI/CD test suite that validates the extraction→compilation pipeline against known-good fixtures. Runs on every commit.

### 10.1 CLI Interface

```
python3 tests/ci_validation.py [--verbose] [--fixture <name>]
```

- **Exit code:** 0 = all pass, 1 = failures found
- **Default:** Runs all fixtures in `tests/fixtures/`

### 10.2 Test Cases

| Test | What it validates |
|------|-------------------|
| `test_schema_roundtrip` | A valid bundle serializes → deserializes without loss |
| `test_validation_catches_errors` | Known-bad bundles produce expected error codes |
| `test_unit_normalization` | kg/tons fixture normalizes correctly |
| `test_mps_generation` | Compiled MPS can be read back by PuLP's `readMPS` |
| `test_mps_variable_count` | Generated MPS has correct variable/constraint counts |
| `test_carry_forward_injection` | Carry-forward adds equality constraints correctly |
| `test_plan_validation` | Valid/invalid decomposition plans pass/fail correctly |
| `test_budget_enforcement` | Budget exceeded → exit code 1 |
| `test_reformulation_decision_tree` | Each failure/attempt combo produces correct action |

### 10.3 GitHub Actions Workflow (`.github/workflows/ci.yml`)

```yaml
name: Pipeline CI
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python tests/ci_validation.py --verbose
```

---

## 11. OpenClaw Configuration Updates

### 11.1 Multi-Tenant Agent Config

```json5
// ~/.openclaw/openclaw.json — Phase 3 additions
{
  agents: {
    list: [
      {
        agentId: "intake-agent",
        workspace: "~/opt-workspace",
        // Now routes to tenant-specific subdirectory based on Slack user → tenant mapping
        skills: { load: { extraDirs: ["~/opt-workspace/skills"] } },
        model: { primary: "google/gemini-3-flash" }
      }
    ]
  },
  cron: {
    inbox_check: {
      every: "0 6 * * *",
      session: "main",
      payload: {
        kind: "agentTurn",
        message: "Check ALL tenant inboxes: ~/opt-workspace/tenants/*/clients/*/inbox/"
      }
    },
    health_check: {
      every: "*/5 * * * *",
      session: "main",
      payload: {
        kind: "agentTurn",
        message: "Run python3 scripts/health_check.py --alert-slack"
      }
    },
    cost_alert: {
      every: "0 9 * * *",
      session: "main",
      payload: {
        kind: "agentTurn",
        message: "Run python3 scripts/cost_tracker.py summary for all active tenants, alert if near budget"
      }
    }
  }
}
```

### 11.2 Slack Tenant Routing

The intake agent must map incoming Slack user ID → tenant:
```
1. Load tenants.json
2. For each tenant, check if sender's user ID is in allowed_planners
3. Route request to that tenant's workspace path
4. If user not found in any tenant: reject with "Unauthorized user"
```

---

## 12. Directory Layout (Phase 3 Complete)

```
~/opt-workspace/
├── tenants.json                           # Tenant registry
├── pipeline_events.jsonl                  # Observability log
├── cost_tracker.db                        # SQLite cost database
├── .circuit_breakers.json                 # Circuit breaker state
├── skills/
│   └── constraint-intake-hybrid/
│       └── SKILL.md
├── scripts/
│   ├── schemas.py
│   ├── schemas_v2.py
│   ├── schemas_v3.py                      # NEW
│   ├── validate_bundle.py
│   ├── emit_pulp_artifacts.py
│   ├── submit_hybridsolver.py
│   ├── watch_inbox.py
│   ├── slack_notify.py
│   ├── gemini_client.py
│   ├── orchestrate_plan.py
│   ├── carry_forward.py
│   ├── reformulate.py
│   ├── memory_writer.py
│   ├── plan_generator.py
│   ├── tenant_manager.py                  # NEW
│   ├── cost_tracker.py                    # NEW
│   ├── reliability.py                     # NEW
│   ├── health_check.py                    # NEW
│   ├── pipeline_logger.py                 # NEW
│   └── parsers/
│       ├── pdf_parser.py
│       ├── tabular_parser.py
│       └── text_parser.py
├── api/
│   └── server.py                          # NEW (FastAPI)
├── dashboard/
│   └── app.py                             # NEW (Streamlit)
├── tests/
│   ├── ci_validation.py                   # NEW
│   └── fixtures/
│       ├── mvp_request/
│       └── multi_stage_plan/
├── .github/
│   └── workflows/
│       └── ci.yml                         # NEW
├── tenants/
│   └── <tenant_id>/
│       ├── clients/<tenant_id>/
│       │   ├── inbox/
│       │   ├── staging/
│       │   ├── approved/
│       │   ├── runs/
│       │   └── outbox/
│       ├── plans/
│       ├── MEMORY.md
│       └── memory/
└── MEMORY.md                              # Global (non-tenant) memory
```

---

## 13. Integration Flow (Phase 3 Complete Pipeline)

```
Slack message or folder drop
    │
    ▼
Tenant Routing (user ID → tenant from tenants.json)
    │
    ▼
Rate Limiter check (tenant's gemini_rate_limit_rpm)
    │
    ▼
Phase 1 Pipeline (tenant-scoped workspace)
    │
    ▼
Budget Check (cost_tracker.py check-budget)
    │  └─ HALT if exceeded
    ▼
Phase 2 Orchestration (if multi-stage detected)
    │
    ▼
Cost Recording (cost_tracker.py record per job)
    │
    ▼
Pipeline Logger (every event → pipeline_events.jsonl)
    │
    ▼
Memory Writer (tenant-scoped MEMORY.md)
    │
    ▼
Dashboard (real-time Streamlit, reads events + cost DB)
```

---

## 14. Security Considerations (Phase 3)

| Concern | Mitigation |
|---------|-----------|
| Cross-tenant data access | OpenClaw workspace path-escape checks; tenant workspace is the root |
| API key per tenant | Single shared keys (QUANTAGONIA, GEMINI, SLACK) — cost attributed by tag |
| Budget bypass | Budget check is mandatory before submit; enforced in orchestrate_plan.py |
| Dashboard auth | Streamlit runs on localhost only; access via SSH tunnel or Codespaces port forwarding |
| Cost DB tampering | SQLite file permissions 600; write-only from cost_tracker.py |
| Rate limit bypass | Rate limiter is in-process; per-tenant tokens enforced before Gemini calls |

---

## 15. Testing Strategy (Phase 3)

### 15.1 Unit Tests

| File | Coverage |
|------|----------|
| `tests/test_schemas_v3.py` | TenantConfig validation, BudgetSummary calculations |
| `tests/test_tenant_manager.py` | Create/list/update/deactivate tenants, workspace provisioning |
| `tests/test_cost_tracker.py` | Record, budget check, monthly summary, export |
| `tests/test_reliability.py` | Retry behavior, circuit breaker state transitions, rate limiter fairness |
| `tests/test_health_check.py` | Mock service probes, degraded detection |

### 15.2 Integration Test

**Scenario:** Two tenants submit jobs concurrently:
- Tenant A: single-stage MILP, within budget
- Tenant B: quarterly decomposition, hits budget cap at stage 3

**Pass criteria:**
- [ ] Both tenants' requests route to correct workspaces
- [ ] No cross-tenant data leakage (Tenant A can't read B's MEMORY.md)
- [ ] Tenant B's stage 3 blocked with budget exceeded message
- [ ] Cost records correctly attributed per tenant
- [ ] Dashboard shows both tenants' activity
- [ ] Health check reports all services healthy
- [ ] Circuit breaker test: simulate Gemini 503 → breaker opens → auto-recovers

---

## 16. Anti-Replication Verification (Phase 3)

- [ ] Dashboard shows solver results but never executes solver logic
- [ ] FastAPI server exposes read-only endpoints; no solve/submit capabilities
- [ ] Cost tracker only records minutes reported by HybridSolver SDK, never estimates
- [ ] Reliability wrappers retry API calls, never contain solver algorithms
- [ ] Health check probes services but never runs optimization

---

## 17. Phase 3 → Phase 4 Boundary (Future)

Phase 3 does NOT include:
- Public-facing SaaS web app with authentication (Auth0/Clerk)
- Stripe/billing integration for paid tenants
- Horizontal scaling (multiple gateway instances)
- Custom domain and SSL for dashboard
- Automated model retraining from solver results
- Multi-region deployment

---

*End of Phase 3 Spec.*
