# ULTIMATE PRD: OpenClaw + Quantagonia HybridSolver — Slack/Folder Hybrid Sidecar

**Codename:** DecisionAI Intake Agent
**Architecture Class:** Pre-Core Stateless Sidecar (Upstream Formulation Pipeline)
**Orchestrator:** OpenClaw (Node.js Gateway + pi-mono runtime)
**Solver Boundary:** Strangeworks/Quantagonia HybridSolver (MILP/LP/QUBO only)
**LLM Stack:** Google Gemini 3 Flash (triage) + Gemini 3.1 Pro (extraction/formulation)
**Execution Target:** GitHub Codespaces (Node 22+ daemon, Python 3.9+ environment)

---

## 1. The FDE Thesis: Why This Specific Hybrid UX

### The Strategic Kill Shot

This architecture merges the Slack Bot intake (LATERAL_PRD_v1) with the Watch-Folder daemon (LATERAL_PRD_v2) into a single hybrid surface. The folder handles heavy quarterly data drops — spreadsheets, PDFs, vendor contracts — while Slack handles human-in-the-loop validation, approval gating, and live solver status. Neither surface alone is sufficient; together they cover the full enterprise adoption spectrum.

### Why This Is Lethal for Dirk and Philipp

**Dirk Zechiel** has stated publicly that his mission is to *"maximize the visibility and importance of Operations Research in public"* and to pursue the *"Democratization of Planning"* (CONTEXT.md, §Leadership Profiles). A watched folder alone is invisible. A Slack thread alone cannot handle 50 MB quarterly data packages. The hybrid gives Dirk exactly what he needs: the heavy data ingestion happens silently in the background, but the **magic moment** — a validated constraint summary, a compiled `.mps` artifact, and a live HybridSolver job ID — appears in a Slack thread where stakeholders can see it. Operations Research becomes socially legible without losing mathematical rigor.

**Philipp Hannemann** is embedded in the OpenClaw (MainClaw) community and explicitly asked *"Can ChatGPT solve optimization problems?"* at a local AI event (CONTEXT.md, §Hannemann Profile). This architecture answers his question with precision: the LLM (Gemini) does not solve the optimization. It extracts, validates, and compiles. The HybridSolver solves. The entire pipeline runs on OpenClaw primitives he actively champions — Lane Queues, JSONL transcripts, `MEMORY.md`, `exec` tool chains — making this a native-environment demonstration of his own ecosystem.

**Thomas Kleinert** (CTO, PhD Mathematical Optimization, FAU Erlangen-Nurnberg) requires that his Hybrid Q Platform remains the unquestioned mathematical authority (CONTEXT.md, §Kleinert Profile). This architecture enforces a hard anti-replication boundary: the sidecar emits `.mps`/`.lp`/`.qubo` artifacts and submits them via the documented SDK. It never executes Simplex, Branch-and-Bound, or Cutting Plane algorithms. The LLM's role is formulation translation — academically validated (see §4 below) — not computation.

**Matthias Wulff** (CSO, MSc Quantum Science & Technology, TUM/LMU) demands systemic reliability and *"low error rates"* (CONTEXT.md, §Wulff Profile). The hybrid architecture features three deterministic validation gates before any payload reaches the solver: Pydantic schema validation, unit normalization, and impossible-value rejection. Every extraction decision is auditable through OpenClaw's append-only JSONL transcripts and `MEMORY.md` entries.

### What We Killed and Why

The Terminal Wizard (LATERAL_PRD_v3) was killed because it requires the user to be present for every extraction step — this fails Dirk's accessibility mandate and cannot scale to recurring quarterly planning cycles. The Email Intake (LATERAL_PRD_v4) was killed because email parsing introduces unacceptable ambiguity in thread segmentation and attachment versioning, and enterprises with active Slack deployments will not route optimization work through email. Both are documented here per the Ego Check protocol (Kaide_Labs_Identity.md, §5).

---

## 2. The System Map: OpenClaw + Gemini Multi-Agent Routing

### Architecture Overview

```
                    INTAKE SURFACES
                    ══════════════
    ┌─────────────────┐     ┌──────────────────────┐
    │  Watch-Folder    │     │  Slack Channel        │
    │  Daemon          │     │  #decisionai-intake   │
    │                  │     │                       │
    │  clients/        │     │  Thread per request   │
    │   <acct>/        │     │  Attachments + NL     │
    │    inbox/        │     │  instructions         │
    └────────┬─────────┘     └───────────┬───────────┘
             │                           │
             └───────────┬───────────────┘
                         │
                    ┌────▼────┐
                    │ OpenClaw │
                    │ Gateway  │
                    │ :18789   │
                    └────┬────┘
                         │
              ┌──────────▼──────────┐
              │  Session Router      │
              │  Lane: session:<id>  │
              │  Queue: collect      │
              └──────────┬──────────┘
                         │
          ┌──────────────▼──────────────┐
          │     GEMINI 3 FLASH           │
          │     (Fast Triage Layer)      │
          │                              │
          │  - File classification       │
          │  - Attachment routing        │
          │  - Missing-info detection    │
          │  - Ambiguity flagging        │
          │  - Slack summary generation  │
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────┐
          │  SUBAGENT LANE (parallel)    │
          │  Concurrency: up to 4       │
          │                              │
          │  ┌────────┐ ┌────────┐       │
          │  │PDF/DOCX│ │XLSX/CSV│       │
          │  │Parser  │ │Parser  │       │
          │  └────────┘ └────────┘       │
          │  ┌────────┐ ┌────────┐       │
          │  │NL Text │ │Prior   │       │
          │  │Extract │ │Context │       │
          │  └────────┘ └────────┘       │
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────┐
          │     GEMINI 3.1 PRO           │
          │     (Deep Extraction Layer)  │
          │                              │
          │  - Cross-document reconcile  │
          │  - Variable identification   │
          │  - Constraint formulation    │
          │  - Objective mapping         │
          │  - Uncertainty annotation    │
          │  - Validator-driven repair   │
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────┐
          │  DETERMINISTIC GATE          │
          │  (exec tool — Python 3.9+)   │
          │                              │
          │  1. validate_bundle.py       │
          │     - Pydantic schema        │
          │     - Unit normalization     │
          │     - Impossible-value trap  │
          │     - Duplicate ID check     │
          │                              │
          │  2. emit_pulp_artifacts.py   │
          │     - PuLP model generation  │
          │     - .mps emission          │
          │     - .lp optional           │
          │     - .qubo conditional      │
          │                              │
          │  3. submit_hybridsolver.py   │
          │     - Async submit           │
          │     - Progress polling       │
          │     - Status + logs          │
          └──────────────┬──────────────┘
                         │
              ┌──────────▼──────────┐
              │  SLACK THREAD        │
              │  (Approval + Status) │
              │                      │
              │  - Extraction preview│
              │  - Validation report │
              │  - Artifact summary  │
              │  - APPROVE / REJECT  │
              │  - Solver job ID     │
              │  - Progress updates  │
              │  - Billed minutes    │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  HYBRIDSOLVER        │
              │  (Quantagonia Cloud) │
              │                      │
              │  MILP / LP / QUBO    │
              │  Global Optimality   │
              │  .mps.gz accepted    │
              └─────────────────────┘
```

### OpenClaw Primitives — Load-Bearing Assignment

| Primitive | Role in This Architecture |
|---|---|
| **Lane Queues** (session lane, concurrency 1) | Serializes per-request processing. Folder events and Slack follow-ups for the same request collapse into one coherent turn via `collect` mode. Prevents race conditions on workspace files. |
| **Lane Queues** (subagent lane, concurrency 4) | Parallelizes file parsing across PDF, XLSX, CSV, and NL-text subagents without interfering with the owning session. |
| **`exec` tool** (allowlist mode) | Runs all deterministic Python scripts: validators, PuLP emitter, HybridSolver submission. Pinned to exact binary paths (`/usr/bin/python3`, `/usr/local/bin/hybridsolver`). Approval-bound. |
| **`MEMORY.md`** | Stores durable client-specific knowledge: terminology mappings, unit conventions, recurring business-rule aliases, forbidden assumptions. Loaded only in private DM sessions per OpenClaw security boundary. Semantically retrievable via `memory_search`. |
| **Daily notes** (`memory/YYYY-MM-DD.md`) | Stores per-run anomalies: schema drift, validator rejections, ambiguous constraint patterns. Enables institutional learning across quarters. |
| **JSONL transcripts** | Append-only factual audit trail of every extraction decision, which attachment produced which constraint. Redaction-safe (API keys passed via env only). |
| **Slack bridge** | Native channel integration via OpenClaw gateway. Thread-keyed sessions. `allowFrom` restricted to authorized planner user IDs. |
| **Cron** | Morning heartbeat (`0 6 * * *`) checks `inbox/` for new data drops and triggers extraction if found. |
| **Model Resolver** | Primary: `google/gemini-3-flash`. Fallback chain: `google/gemini-3.1-pro` → `anthropic/claude-sonnet-4-6` → `openai/gpt-5.4`. Auth-profile rotation with exponential backoff. |

### Gemini Model Routing Logic

**Gemini 3 Flash** handles all latency-sensitive, low-complexity tasks:
- Incoming Slack message classification (is this a new request, a follow-up, or noise?)
- File-type detection and parser routing
- Missing-information detection and question generation
- Compact Slack summaries at extraction boundaries

**Gemini 3.1 Pro** handles all high-complexity, accuracy-critical tasks:
- Full constraint extraction from long-form contracts and policy documents
- Cross-document reconciliation (resolving conflicts between a PDF and a spreadsheet)
- Decision variable identification and typing (continuous, integer, binary)
- Constraint formulation drafting with explicit uncertainty markers
- Post-validation repair loops (when the deterministic validator rejects output, Pro must fix the structure without fabricating coefficients)

This split is architecturally consistent with Google's own tiered model guidance and with OpenClaw's Model Resolver, which supports per-agent model assignment with cross-provider failover.

---

## 3. The Hybrid UX: Folder + Slack Integration Spec

### Folder Contract (Heavy Data Ingestion)

```
~/opt-workspace/clients/<account>/
├── inbox/              # User drops raw files here
│   └── <request_id>/   # One folder per optimization request
│       ├── demand_forecast_q2.xlsx
│       ├── vendor_contract_2026.pdf
│       ├── capacity_limits.csv
│       └── README.txt   # Optional: natural language brief
├── staging/            # Agent mirrors here during extraction
├── approved/           # Human moves here to approve submission
├── runs/               # Agent writes all intermediate + final artifacts
│   └── <request_id>/
│       ├── source/
│       ├── constraint_bundle.json
│       ├── validation_report.json
│       ├── model.py
│       ├── artifacts/
│       │   ├── problem.mps
│       │   ├── problem.lp
│       │   └── problem.qubo  (conditional)
│       └── submission.json
└── outbox/             # Final reports for downstream consumption
```

### Slack Contract (Validation + Approval + Status)

**Channel:** `#decisionai-intake`
**Threading:** One thread per `<request_id>`. All interaction is thread-local.

**Thread lifecycle:**

1. **Trigger** — Cron detects new folder in `inbox/` OR user posts directly in Slack with attachments
2. **Intake receipt** — Agent posts: `"Processing request <id> — 3 files detected (1 PDF, 1 XLSX, 1 CSV)"`
3. **Extraction preview** — Agent posts structured summary:
   - Detected entities and indices
   - Candidate decision variables (with types)
   - Hard constraints extracted
   - Unresolved ambiguities requiring human input
4. **Human review** — Planner confirms, edits, or rejects in-thread
5. **Validation report** — Agent posts pass/fail with human-readable explanations (never raw tracebacks)
6. **Artifact compilation** — Agent posts: `"Compiled problem.mps (847 variables, 2,341 constraints). Ready for submission?"`
7. **Approval gate** — Planner replies `APPROVE` or moves folder to `approved/`
8. **Submission** — Agent posts HybridSolver job ID
9. **Progress updates** — Agent posts incumbent objective, bound, gap, and billed minutes at configurable intervals
10. **Completion** — Agent posts final result summary with solution quality metrics

### Approval Semantics (Dual-Path)

Approval can be triggered by either:
- **Slack:** Planner replies `APPROVE` in the request thread
- **Folder:** Planner moves the request folder from `staging/` to `approved/`

Both signals are equivalent. The agent must not submit to HybridSolver without one of them. This dual-path design respects both chat-native and file-native operator habits.

---

## 4. State-of-the-Art Justification: Academic & Engineering Validation

### Academic Validation: LLM-Driven MILP Formulation

The core architectural claim — that an LLM can reliably extract constraints from natural language and formulate MILP models while a deterministic solver handles computation — is validated by a rapidly maturing body of peer-reviewed research:

**Primary Citation:**

> **OptiMUS: Scalable Optimization Modeling with (MI)LP Solvers and Large Language Models**
> Ali AhmadiTeshnizi, Wenzhi Gao, Madeleine Udell (Stanford / Cornell)
> arXiv:2402.10172 (Feb 2024), extended as OptiMUS-0.3 in arXiv:2407.19633 (Jul 2024)
> GitHub: https://github.com/teshnizi/OptiMUS
>
> OptiMUS demonstrates a modular LLM-based agent that formulates and solves MILP problems from natural language descriptions. The system develops mathematical models, writes solver code, evaluates solutions, and self-corrects. On the NLP4LP benchmark (long, complex problems), OptiMUS outperforms baseline prompting by >30%. **The architecture explicitly validates the "LLM for formulation, solver for computation" split** — the LLM never attempts to solve the optimization; it only produces the mathematical model for a deterministic solver.

**Supporting Citation:**

> **OptiTrust: Toward a Trustworthy Optimization Modeling Agent via Verifiable Synthetic Data Generation**
> Vinicius Lima, Dzung T. Phan, Jayant Kalagnanam, Dhaval Patel, Nianjun Zhou (IBM Research)
> arXiv:2508.03117 (Aug 2025)
>
> OptiTrust introduces a verifiable pipeline for training LLM agents on LP/MILP formulation tasks. It performs multi-stage translation from natural language to solver-ready code with cross-validation. Achieves state-of-the-art on 6 of 7 optimization benchmarks. **Validates that LLM formulation agents can achieve production-grade reliability when paired with deterministic verification** — directly analogous to our Pydantic validation gate.

**Industrial-Scale Frontier:**

> **MIPLIB-NL: Constructing Industrial-Scale Optimization Modeling Benchmark**
> Zhong Li et al.
> arXiv:2602.10450 (Feb 2026)
>
> Introduces a benchmark of 223 real industrial MILP problems with natural language specifications, built from MIPLIB 2017. Shows that current LLM systems that perform well on toy benchmarks **degrade substantially at industrial scale** (10^3–10^6 variables). This validates our architectural choice to use Gemini 3.1 Pro for formulation drafting but enforce deterministic compilation and validation before submission — the LLM's formulation is a draft, not gospel.

**Pitch framing for Kleinert:** *"The architecture we propose — LLM-driven formulation feeding a deterministic solver engine — is consistent with the emerging consensus in the OR+AI literature (OptiMUS, NeurIPS-track 2024; OptiTrust, IBM Research 2025; MIPLIB-NL, 2026). We are not asking the LLM to solve. We are asking it to model. Your engine solves."*

### Engineering Validation: Gemini + Agentic Frameworks

**Google Gemini 3 / 3.1 Pro (Confirmed Current — April 2026):**
- Gemini 3 Flash is now the default model in the Gemini app, representing a major capability upgrade over 2.5 Flash ([Google Blog: Introducing Gemini 3 Flash](https://blog.google/products/gemini/gemini-3-flash/))
- Gemini 3.1 Pro is rolling out to developers and enterprises via AI Studio, Vertex AI, and the Gemini API as of April 2026 ([Google Blog: Gemini 3.1 Pro](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-pro/))
- Google ADK (Agent Development Kit) at `github.com/google/adk-python` supports per-agent model assignment, enabling the Flash-for-triage / Pro-for-extraction pattern natively

**OpenClaw Orchestration Layer (Confirmed Current):**
- Architecture documentation covering Lane Queues, Semantic Snapshots, JSONL memory: [Vertu Architecture Guide](https://vertu.com/ai-tools/openclaw-clawdbot-architecture-engineering-reliable-and-controllable-ai-agents/)
- Platform overview with webhook, file-system, and exec capabilities: [MindStudio](https://www.mindstudio.ai/blog/what-is-openclaw-ai-agent), [DigitalOcean](https://www.digitalocean.com/resources/articles/what-is-openclaw)
- Community events organized by Philipp Hannemann: [MainClaw Meetups (Luma)](https://luma.com/claw)
- OpenClaw's Model Resolver is provider-agnostic — Gemini models are supported via auth-profile configuration with the same failover semantics as any other provider

**Quantagonia HybridSolver (SDK Audit — April 2026):**
- `quantagonia>=0.15.0` (March 2026): async `submit→progress→status→logs` pattern confirmed current
- CLI: `hybridsolver` with `--as-qubo` / `--as-qubo-only` flags confirmed current
- PuLP adapter: `quantagonia.mip.pulp_adapter.HybridSolver_CMD` confirmed current
- Full audit in PRD.MD Appendix A

---

## 5. Anti-Replication Guardrail Verification

This section explicitly satisfies the Kaide Labs Anti-Replication Principle (Kaide_Labs_Identity.md, §5) and the OpenClaw/FDE firewalls.

### What the Sidecar Does

| Action | Tool | Deterministic? |
|---|---|---|
| Classifies incoming files | Gemini 3 Flash | No (LLM) — but output is only routing metadata, not solver input |
| Extracts constraints from natural language | Gemini 3.1 Pro | No (LLM) — but output is a **draft** that must pass validation |
| Validates constraint bundle | `validate_bundle.py` via `exec` | **Yes** — Pydantic schema, unit checks, value bounds |
| Compiles PuLP model and emits `.mps` | `emit_pulp_artifacts.py` via `exec` | **Yes** — deterministic code generation |
| Submits to HybridSolver | `submit_hybridsolver.py` via `exec` | **Yes** — SDK call only |
| Solves the MILP/LP/QUBO | **HybridSolver (Quantagonia Cloud)** | **Yes** — global optimality guarantee |

### What the Sidecar Never Does

- Never executes Simplex, Branch-and-Bound, or Cutting Plane algorithms
- Never claims to have "optimized" or "solved" a model
- Never fabricates coefficients, bounds, or constraints not present in source data
- Never submits to HybridSolver without explicit human approval
- Never supports QP, MIQP, or NLP (HybridSolver boundary does not support these)
- Never echoes `QUANTAGONIA_API_KEY` to stdout (OpenClaw JSONL redaction caveat)

### The Ego Check

Thomas Kleinert's engineering team builds the solver engine. This sidecar builds nothing that competes with that engine. It is an impedance matcher between messy enterprise data and perfectly formatted `.mps` payloads. If Kleinert's team were to look at this architecture, they would feel **relieved** — it creates clean input for their system without touching their math.

---

## 6. Phase 1 Execution Spec: GitHub Codespaces Blueprint

### Environment Setup

```bash
# Codespace: Ubuntu 22.04, Node 22+, Python 3.11
# Step 1: Install OpenClaw
npm install -g openclaw@latest
openclaw onboard --install-daemon

# Step 2: Python dependencies
pip install quantagonia>=0.15.0 pulp>=3.3.0 pandas>=2.2.0 pydantic>=2.0

# Step 3: Secrets (Codespaces Secrets, never in code)
# QUANTAGONIA_API_KEY → platform.quantagonia.com
# SLACK_BOT_TOKEN → Slack app with channels:history, chat:write, files:read
# GEMINI_API_KEY → Google AI Studio
```

### OpenClaw Configuration

```json5
// ~/.openclaw/openclaw.json
{
  gateway: { port: 18789 },
  agents: {
    defaults: {
      workspace: "~/opt-workspace",
      model: {
        primary: "google/gemini-3-flash",
        fallbacks: ["google/gemini-3.1-pro", "anthropic/claude-sonnet-4-6", "openai/gpt-5.4"]
      },
      maxConcurrent: 4,
      sandbox: { mode: "non-main", workspaceAccess: "rw" }
    },
    list: [{
      agentId: "intake-agent",
      workspace: "~/opt-workspace",
      skills: { load: { extraDirs: ["~/opt-workspace/skills"] } },
      model: {
        primary: "google/gemini-3-flash"  // triage
      }
    }, {
      agentId: "formulation-agent",
      workspace: "~/opt-workspace",
      model: {
        primary: "google/gemini-3.1-pro"  // deep extraction
      }
    }]
  },
  channels: {
    slack: {
      allowFrom: ["U_PLANNER_ID"],
      channel: "decisionai-intake"
    }
  },
  tools: {
    exec: {
      security: "allowlist",
      safeBins: [
        "/usr/bin/python3",
        "/usr/local/bin/hybridsolver",
        "/usr/bin/git",
        "/bin/ls"
      ],
      approvalRunningNoticeMs: 10000
    }
  },
  messages: { queue: { mode: "collect", debounceMs: 2000 } },
  cron: {
    inbox_check: {
      every: "0 6 * * *",
      session: "main",
      payload: {
        kind: "agentTurn",
        message: "Check ~/opt-workspace/clients/*/inbox/ for new data drops"
      }
    }
  }
}
```

### Skill Definition

```yaml
# ~/opt-workspace/skills/constraint-intake-hybrid/SKILL.md
---
name: constraint-intake-hybrid
description: >
  Watch folders and Slack threads for enterprise data packages.
  Extract constraints via Gemini, validate deterministically,
  compile PuLP artifacts, submit to Quantagonia HybridSolver.
version: 0.1.0
metadata:
  openclaw:
    requires:
      env: [QUANTAGONIA_API_KEY, GEMINI_API_KEY, SLACK_BOT_TOKEN]
      bins: [python3, hybridsolver]
---
# Behavior
1. On folder event or Slack thread: create session, classify files (Flash)
2. Fan out subagents for parallel parsing
3. Merge evidence and draft formulation (Pro)
4. Run validate_bundle.py via exec
5. If fail: repair loop (Pro), max 2 retries, then ask human
6. Run emit_pulp_artifacts.py via exec
7. Post preview to Slack thread, await APPROVE
8. Run submit_hybridsolver.py via exec
9. Stream progress to Slack thread
10. Write durable learnings to MEMORY.md
```

### Deterministic Scripts

**`scripts/validate_bundle.py`**
- Input: `constraint_bundle.json`
- Pydantic model with strict typing for variables (continuous/integer/binary), constraints (LHS coefficients, operator, RHS), bounds, and objective
- Unit normalization (detect and convert mismatched units)
- Impossible-value rejection (negative capacities, percentages > 100, etc.)
- Duplicate identifier detection
- Output: `validation_report.json` with pass/fail and human-readable error descriptions

**`scripts/emit_pulp_artifacts.py`**
- Input: validated `constraint_bundle.json`
- Generates `model.py` using PuLP API + `quantagonia.mip.pulp_adapter.HybridSolver_CMD`
- Executes model to emit `problem.mps` (primary), `problem.lp` (optional)
- Emits `problem.qubo` only when all variables are binary AND `--qubo` flag is explicitly set
- Output: artifact files + compilation manifest

**`scripts/submit_hybridsolver.py`**
- Input: `problem.mps.gz` + `params.json`
- Implements async `submit → progress → status → logs` loop
- Streams machine-readable progress JSON to stdout (captured by OpenClaw JSONL)
- Returns: job ID, status, objective, bound, gap, billed minutes
- API key passed exclusively via `QUANTAGONIA_API_KEY` env var (never in argv, never echoed)

**`scripts/watch_inbox.py`**
- Polls `clients/*/inbox/` for new `<request_id>/` folders
- Emits stable request IDs based on folder name + timestamp
- Triggers OpenClaw agent turn via gateway API

### Run-State Layout

```
runs/<request_id>/
├── source/                    # Mirrored source files (immutable after staging)
├── constraint_bundle.json     # Extracted constraints (Gemini 3.1 Pro output)
├── validation_report.json     # Deterministic validation result
├── questions.md               # Unresolved ambiguities for human review
├── model.py                   # Generated PuLP model code
├── artifacts/
│   ├── problem.mps            # Primary solver artifact
│   ├── problem.mps.gz         # Compressed for submission
│   ├── problem.lp             # Optional human-readable format
│   └── problem.qubo           # Conditional (binary-only problems)
├── submission.json            # HybridSolver job metadata
└── slack_thread.json          # Thread ID + message history reference
```

### MVP Acceptance Test

**Test fixture:** One synthetic client data package containing:
1. One messy PDF: a union labor contract with embedded overtime rules and shift constraints
2. One XLSX: quarterly demand forecast with 4 tabs (one per product line)
3. One CSV: warehouse capacity limits with mixed units (kg vs. tons)
4. One Slack message: *"Need the Q2 workforce allocation model for the Munich warehouse. Max 8-hour shifts, no overtime on weekends."*

**Pass criteria:**
- [ ] Folder watcher detects the new request within one cron cycle
- [ ] Gemini 3 Flash correctly classifies all 3 file types
- [ ] Gemini 3.1 Pro extracts at least: shift-length constraint (8h), weekend-overtime prohibition, capacity bounds from CSV, demand parameters from XLSX
- [ ] `validate_bundle.py` catches the kg/tons unit mismatch and normalizes
- [ ] `emit_pulp_artifacts.py` produces a valid `.mps` file
- [ ] Slack thread shows extraction preview with separated facts / inferences / ambiguities
- [ ] Submission occurs only after explicit `APPROVE` in thread
- [ ] HybridSolver job ID and progress updates appear in thread
- [ ] `QUANTAGONIA_API_KEY` never appears in JSONL transcripts or Slack messages
- [ ] `MEMORY.md` entry created: *"Munich warehouse uses metric tons for capacity, not kg"*

---

## 7. Dependency Versions (Locked)

| Package | Version | Python | Status |
|---|---|---|---|
| `quantagonia` | ≥0.15.0 | ≥3.8 | Current (March 2026). Async pattern, CLI flags, PuLP adapter verified. |
| `PuLP` | ≥3.3.0 | ≥3.9 | Current. `LpSolver_CMD` interface stable. |
| `pandas` | ≥2.2.0 | ≥3.9 | Current. `read_csv` stable. Use `pd.concat()` not `DataFrame.append()`. |
| `pydantic` | ≥2.0 | ≥3.8 | Current. V2 API for strict schema validation. |
| `strangeworks-optimization` | 0.2.28 | 3.10–3.11 | **Stale** (Aug 2024, pre-acquisition). Not recommended for Phase 1. Monitor for v0.3.x. |

**Effective Python floor: ≥3.9** (driven by PuLP 3.3.0).

---

## 8. References

### Academic Papers
1. AhmadiTeshnizi, A., Gao, W., & Udell, M. (2024). "OptiMUS: Scalable Optimization Modeling with (MI)LP Solvers and Large Language Models." arXiv:2402.10172. https://arxiv.org/abs/2402.10172
2. AhmadiTeshnizi, A., Gao, W., Brunborg, H., Talaei, S., Lawless, C., & Udell, M. (2024). "OptiMUS-0.3: Using Large Language Models to Model and Solve Optimization Problems at Scale." arXiv:2407.19633. https://arxiv.org/abs/2407.19633
3. Lima, V., Phan, D.T., Kalagnanam, J., Patel, D., & Zhou, N. (2025). "OptiTrust: Toward a Trustworthy Optimization Modeling Agent via Verifiable Synthetic Data Generation." arXiv:2508.03117. https://arxiv.org/abs/2508.03117
4. Li, Z. et al. (2026). "MIPLIB-NL: Constructing Industrial-Scale Optimization Modeling Benchmark." arXiv:2602.10450. https://arxiv.org/abs/2602.10450

### Engineering Sources
5. Google. "Introducing Gemini 3 Flash." https://blog.google/products/gemini/gemini-3-flash/
6. Google. "Gemini 3.1 Pro: A smarter model for your most complex tasks." https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-pro/
7. Google ADK (Agent Development Kit). https://github.com/google/adk-python
8. Quantagonia HybridSolver Documentation. https://docs.quantagonia.com/
9. Quantagonia HybridSolver API Reference. https://docs.quantagonia.com/api-ref.html
10. Quantagonia CLI Reference. https://docs.quantagonia.com/cli-ref.html

### Strategic Context
11. Strangeworks acquires Quantagonia (Aug 2025). https://strangeworks.com/press/strangeworks-acquires-quantagonia-to-create-global-leader-in-applied-ai-optimization-and-quantum-computing
12. Quantagonia DecisionAI. https://www.quantagonia.com/post/not-a-solver-but-decision-ai-for-business-intelligence
13. LHIND integrates DecisionAI into gate assignment. https://www.lufthansa-industry-solutions.com/de-en/newsroom-downloads/news/lufthansa-industry-solutions-integrates-decisionai-into-its-gate-assignment-solution
14. OpenClaw Architecture Guide (Vertu). https://vertu.com/ai-tools/openclaw-clawdbot-architecture-engineering-reliable-and-controllable-ai-agents/
15. OpenClaw Overview (DigitalOcean). https://www.digitalocean.com/resources/articles/what-is-openclaw
16. MainClaw Community Events (Luma). https://luma.com/claw
