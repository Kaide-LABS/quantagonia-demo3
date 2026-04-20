# PHASE 5 SPEC: Demo Orchestration, Test Fixtures & Live Pitch Tooling

**Parent:** PRD.MD (§ "Why this specific demo justifies the framework"), ULTIMATE_PRD.md (§6 MVP Acceptance Test), Kaide_Labs_Identity.md (§5-Pillar Demo Standard)
**Prerequisite:** Phases 1-4 complete (full SaaS pipeline operational)
**Scope:** End-to-end demo fixtures, scripted presentation flow, live demo controller, audience-facing documentation, video recording harness
**Boundary:** Blueprint only. No application code.
**Date:** 2026-04-20

---

## 0. Phase 5 Objectives

Phases 1-4 built the engine. Phase 5 builds the **stage** — everything needed to deliver a flawless, reproducible live demonstration to Strangeworks/Quantagonia leadership:

1. **Synthetic test fixtures** — Realistic enterprise data packages that exercise every pipeline capability (PDF contracts, XLSX forecasts, CSV with unit mismatches, NL instructions)
2. **Demo controller script** — One-click orchestrator that resets state, seeds data, and runs the full pipeline in a deterministic, timed sequence
3. **Audience-facing documentation** — Technical one-pager and architecture diagram designed for Thomas Kleinert (CTO) and Matthias Wulff (CSO)
4. **Narration script** — Beat-by-beat presenter notes synced to pipeline events
5. **Recording harness** — Terminal + Slack + portal screenshots captured automatically at key moments
6. **Failure injection** — Deliberate unit mismatch and ambiguity injection to demonstrate validation gates and repair loops live

---

## 1. File: `demo/fixtures/acme_q2_2026/`

**Purpose:** The primary demo data package. Exercises the full Phase 1-2 pipeline including multi-stage detection, unit normalization, and QUBO comparison.

### 1.1 Fixture Files

| File | Type | Content | What It Exercises |
|------|------|---------|-------------------|
| `union_contract_munich.pdf` | PDF | 3-page mock labor contract with shift rules, overtime limits, weekend prohibitions | PDF parser, constraint extraction, NL → hard constraints |
| `demand_forecast_q2.xlsx` | XLSX | 4 tabs (ProductA-D), 12 weeks, demand quantities | Tabular parser, multi-tab handling, quarterly detection |
| `warehouse_capacity.csv` | CSV | 5 warehouses, mixed units (kg AND tons deliberately) | Unit normalization, impossible-value detection |
| `routing_matrix.csv` | CSV | SKU → warehouse assignment with binary eligibility | Binary variable detection, QUBO eligibility |
| `instructions.txt` | TXT | "Q2 workforce allocation for Munich. Max 8h shifts, no weekend OT. Prioritize warehouse-3." | NL text parser, objective framing |

### 1.2 Expected Extraction Targets

The demo fixture is designed so that a correct extraction produces:

| Category | Count | Key Items |
|----------|-------|-----------|
| Decision Variables | 24 | 4 products × 5 warehouses × binary assignment + 4 continuous production levels |
| Constraints | 38 | Shift limits, overtime ban, capacity bounds, demand satisfaction, routing eligibility |
| Objective | Minimize total overtime cost | With secondary: maximize warehouse-3 utilization |
| Unit Mismatch | 1 | warehouse_capacity.csv has warehouse-3 in kg, others in tons |
| Ambiguity | 1 | "Prioritize warehouse-3" is vague — should surface as ambiguity |

### 1.3 Expected Validation Behavior

- `validate_bundle.py` catches kg/tons mismatch on warehouse-3
- Normalizes to metric tons (×0.001 factor)
- Flags "prioritize" as ambiguity requiring human clarification
- Passes on second run after Gemini repair resolves the ambiguity structurally

---

## 2. File: `demo/fixtures/acme_annual_plan/`

**Purpose:** Multi-stage demo fixture for Phase 2 orchestration. 4 quarterly stages with carry-forward.

### 2.1 Fixture Files

```
demo/fixtures/acme_annual_plan/
├── demand_q1.csv       # 12 SKUs, 13 weeks
├── demand_q2.csv
├── demand_q3.csv
├── demand_q4.csv
├── capacity.csv        # 5 warehouses (clean units)
├── sku_routing.csv     # Binary eligibility matrix
└── instructions.txt    # "Annual workforce plan. Q1 inventory carries to Q2."
```

### 2.2 Expected Behavior

- `plan_generator.py` detects quarterly structure → generates 4-stage plan
- Q1 solves in ~30s (small problem)
- Q2 deliberately sized to timeout at 60s → triggers reformulation (time increase)
- Q3/Q4 solve normally with carry-forward from prior quarters
- QUBO attempted on Q1 (all binary routing subset)
- MEMORY.md entry: "ACME annual: QUBO 12% faster on routing subproblem"

---

## 3. File: `demo/controller.py`

**Purpose:** One-click demo orchestrator. Resets all state, seeds fixtures, runs the pipeline in a timed sequence with narration cues.

### 3.1 CLI Interface

```
python3 demo/controller.py [--mode live|recording|dry-run] [--fixture acme_q2|acme_annual] [--speed 1.0]
```

### 3.2 Execution Flow

```
Phase 0: RESET (5s)
├── Clear tenant workspace (rm -rf tenants/demo-acme/clients/demo-acme/runs/*)
├── Reset MEMORY.md to initial state
├── Clear cost_tracker.db entries for demo-acme
├── Print: "🔄 Environment reset. Ready for demo."

Phase 1: SEED (3s)
├── Copy fixture files to tenants/demo-acme/clients/demo-acme/inbox/demo-request/
├── Print: "📁 Data package dropped into watched folder."

Phase 2: INTAKE (10s)
├── Run: watch_inbox.py → detect new request
├── Run: gemini_client.py classify → file classification
├── Run: slack_notify.py intake → Slack post
├── Print: "🔍 Files detected and classified."
├── NARRATION CUE: "The agent has detected new files. Gemini Flash classified them in <X>ms."

Phase 3: EXTRACTION (20s)
├── Run: pdf_parser.py, tabular_parser.py, text_parser.py (parallel)
├── Run: gemini_client.py extract → constraint_bundle.json
├── Run: slack_notify.py preview → extraction preview to Slack
├── Print: "📊 Extracted {N} variables, {M} constraints."
├── NARRATION CUE: "Gemini Pro extracted constraints. Note the ambiguity flagged."

Phase 4: VALIDATION (5s)
├── Run: validate_bundle.py → catches unit mismatch
├── Print: "⚠️ Unit mismatch detected (kg vs tons). Auto-normalizing..."
├── Run: validate_bundle.py (second pass after normalization)
├── Print: "✅ Validation passed. {N} warnings."
├── NARRATION CUE: "The deterministic gate caught a unit mismatch. No LLM involved here."

Phase 5: COMPILATION (5s)
├── Run: emit_pulp_artifacts.py --lp
├── Print: "🔨 Compiled problem.mps ({N} vars, {M} constraints, {size} bytes)"
├── NARRATION CUE: "PuLP compiled the model. The .mps artifact is solver-ready."

Phase 6: APPROVAL (manual or auto)
├── IF mode=live: WAIT for Slack APPROVE or keyboard input
├── IF mode=recording|dry-run: auto-approve after 3s
├── Print: "✅ APPROVED. Submitting to HybridSolver..."

Phase 7: SUBMISSION (30-120s)
├── Run: submit_hybridsolver.py --time-limit 300
├── Stream progress to stdout + Slack
├── Print: "🚀 Job submitted. Tracking: obj={X}, gap={Y}%, time={Z}s"
├── NARRATION CUE: "The solver is running. We see live progress. Note: the LLM never touches this."

Phase 8: COMPLETION (5s)
├── Print final results
├── Run: memory_writer.py stage_complete
├── Run: quality_feedback.py (if applicable)
├── Print: "🏁 Complete. Objective: {X}, Gap: {Y}%, Billed: {Z} minutes"
├── NARRATION CUE: "Done. The agent learned one new fact for next time."

TOTAL ESTIMATED TIME: 80-170 seconds (depending on solver)
```

### 3.3 Speed Control

- `--speed 0.5`: Double all artificial pauses (slower, more dramatic)
- `--speed 1.0`: Normal (real execution speed)
- `--speed 2.0`: Skip artificial pauses (for testing)

### 3.4 Narration Cues

Output format for presenter:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎤 NARRATION: "The agent has detected new files. Gemini Flash classified them in 234ms."
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 4. File: `demo/narration_script.md`

**Purpose:** Full presenter notes for the live demo. Beat-by-beat script synced to pipeline events.

### 4.1 Structure

```markdown
# DecisionAI Demo — Presenter Script

## Opening (30s)
"What you're about to see is a fully autonomous optimization intake agent.
It watches a folder, extracts constraints from messy enterprise data,
validates deterministically, compiles solver-ready artifacts, and submits
to Quantagonia's HybridSolver — all without a human writing a single
line of math."

## Beat 1: The Data Drop (10s)
[Files appear in watched folder]
"A planner just dropped their quarterly data package. Three files:
a union labor contract PDF, a demand forecast Excel, and a capacity CSV
with mixed units."

## Beat 2: Classification (10s)
[Slack message appears]
"Gemini Flash classified the files in under 300ms. It knows the PDF is
a contract, the Excel is data, and the CSV needs unit attention."

## Beat 3: Extraction (20s)
[Extraction preview in Slack]
"Gemini Pro now extracts the actual mathematical constraints. Note:
it explicitly flags what it's certain about, what it inferred, and
what's ambiguous. The LLM is honest about uncertainty."

## Beat 4: The Validation Gate (10s)
[Unit mismatch caught]
"Here's the key differentiator. A DETERMINISTIC Python gate — not an LLM —
caught that warehouse-3's capacity was in kilograms while others are in tons.
It normalized automatically. This is why Thomas Kleinert's team can trust
the pipeline: every artifact that reaches their solver has been verified
by hard logic, not probabilistic guessing."

## Beat 5: Compilation (5s)
[MPS file generated]
"PuLP compiled the validated bundle into a standard .mps file.
847 variables, 2,341 constraints. This is the lingua franca of OR solvers."

## Beat 6: Approval (5s)
[APPROVE in Slack]
"The planner reviews and approves. No submission without human sign-off."

## Beat 7: Solver Execution (30-60s)
[Live progress in Slack thread]
"Now HybridSolver takes over. We see live progress: incumbent objective,
bound, gap, wall time. The LLM's job is done. The math is Quantagonia's."

## Beat 8: Memory (5s)
[MEMORY.md updated]
"The agent learned that Munich warehouse uses metric tons. Next quarter,
it won't need the validation gate to catch this — it'll extract correctly
the first time. Institutional knowledge, compounding over time."

## Closing (20s)
"What we didn't build: a solver. What we built: the impedance matcher
between messy enterprise reality and perfectly formatted solver input.
Your engine solves. Our agent prepares."
```

---

## 5. File: `demo/audience_onepager.md`

**Purpose:** Leave-behind technical one-pager for Kleinert (CTO) and Wulff (CSO). Designed to answer their specific concerns.

### 5.1 Content Structure

```markdown
# DecisionAI Intake Agent — Technical Overview

## What It Does
Autonomous pre-processing pipeline: enterprise data → validated .mps artifacts → HybridSolver

## What It Doesn't Do
- Never executes Simplex, Branch-and-Bound, or Cutting Plane
- Never fabricates constraints not present in source data
- Never submits without human approval

## Architecture
[Simplified diagram from ULTIMATE_PRD.md §2]

## Validation Stack (For Thomas)
1. Pydantic schema validation (type safety)
2. Unit normalization (deterministic conversion)
3. Impossible-value rejection (bounds checking)
4. Referential integrity (no dangling variable refs)

## Reliability (For Matthias)
- Error rate: 0% on deterministic gates (by definition)
- LLM extraction: confidence-scored, auditable, repairable
- Every decision in append-only JSONL transcript

## Academic Grounding
- OptiMUS (Stanford, 2024): LLM formulation, solver computation — same pattern
- OptiTrust (IBM, 2025): Verifiable LLM optimization modeling
- MIPLIB-NL (2026): Validates need for deterministic post-extraction gates
```

---

## 6. File: `demo/screenshot_harness.py`

**Purpose:** Automatically captures terminal output and Slack screenshots at key demo moments for use in pitch decks and recordings.

### 6.1 CLI Interface

```
python3 demo/screenshot_harness.py --output-dir demo/captures/ --mode terminal
```

### 6.2 Capture Points

| Moment | What to Capture |
|--------|----------------|
| File detection | Terminal showing watch_inbox.py output |
| Classification | Gemini Flash response JSON |
| Extraction preview | Slack thread with facts/inferences/ambiguities |
| Unit mismatch | validate_bundle.py stderr + correction log |
| MPS compilation | Terminal showing variable/constraint counts |
| Solver progress | Slack thread with live objective/gap updates |
| Completion | Final summary in Slack + MEMORY.md diff |

### 6.3 Implementation

- Terminal captures: redirect stdout to tee + timestamp-named file
- Slack captures: use `slack-sdk` `conversations_history` to fetch thread messages after each beat
- Save as Markdown + raw JSON for reuse in pitch deck

---

## 7. File: `demo/failure_injection.py`

**Purpose:** Deliberately injects errors into demo fixtures to demonstrate the pipeline's self-healing capabilities.

### 7.1 CLI Interface

```
python3 demo/failure_injection.py --type <unit_mismatch|ambiguity|infeasibility|timeout> --fixture <path>
```

### 7.2 Injection Types

| Type | What It Does | What Demo Shows |
|------|-------------|-----------------|
| `unit_mismatch` | Changes one warehouse's units from tons to kg in CSV | validate_bundle.py catches and normalizes |
| `ambiguity` | Adds vague constraint ("optimize efficiency") to instructions.txt | Gemini flags as ambiguity, asks human |
| `infeasibility` | Adds conflicting constraints (demand > capacity) | Solver returns infeasible, repair loop triggered |
| `timeout` | Doubles problem size (more variables) | Reformulation loop increases time limit |

---

## 8. File: `demo/docker-compose.yml`

**Purpose:** One-command demo environment setup. Brings up all services locally for a self-contained demo.

### 8.1 Services

```yaml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  api:
    build: .
    command: uvicorn api.v1.app:app --host 0.0.0.0 --port 8000
    environment:
      - REDIS_URL=redis://redis:6379/0
      - WORKSPACE_ROOT=/opt-workspace
      - QUANTAGONIA_API_KEY=${QUANTAGONIA_API_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}
    volumes:
      - workspace:/opt-workspace
    ports: ["8000:8000"]

  worker:
    build: .
    command: celery -A api.v1.workers worker -Q optimization --loglevel=info
    environment:
      - REDIS_URL=redis://redis:6379/0
      - WORKSPACE_ROOT=/opt-workspace
      - QUANTAGONIA_API_KEY=${QUANTAGONIA_API_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    volumes:
      - workspace:/opt-workspace

  dashboard:
    build: .
    command: streamlit run dashboard/app.py --server.port 8501
    environment:
      - WORKSPACE_ROOT=/opt-workspace
    volumes:
      - workspace:/opt-workspace
    ports: ["8501:8501"]

volumes:
  workspace:
```

### 8.2 Quick Start

```bash
# Set secrets
export QUANTAGONIA_API_KEY=...
export GEMINI_API_KEY=...
export SLACK_BOT_TOKEN=...

# Launch
docker-compose up -d

# Run demo
python3 demo/controller.py --mode live --fixture acme_q2
```

---

## 9. Directory Layout (Phase 5)

```
demo/
├── controller.py               # One-click demo orchestrator
├── narration_script.md         # Presenter beat notes
├── audience_onepager.md        # CTO/CSO leave-behind
├── screenshot_harness.py       # Auto-capture at key moments
├── failure_injection.py        # Deliberate error injection
├── docker-compose.yml          # One-command environment
├── fixtures/
│   ├── acme_q2_2026/
│   │   ├── union_contract_munich.pdf
│   │   ├── demand_forecast_q2.xlsx
│   │   ├── warehouse_capacity.csv
│   │   ├── routing_matrix.csv
│   │   └── instructions.txt
│   └── acme_annual_plan/
│       ├── demand_q1.csv
│       ├── demand_q2.csv
│       ├── demand_q3.csv
│       ├── demand_q4.csv
│       ├── capacity.csv
│       ├── sku_routing.csv
│       └── instructions.txt
└── captures/                   # Auto-generated screenshots
```

---

## 10. Demo Tenant Setup

### 10.1 Pre-Demo Provisioning

```bash
python3 scripts/tenant_manager.py create \
  --id demo-acme \
  --name "ACME Corp (Demo)" \
  --planners U_DEMO_PLANNER \
  --budget 100 \
  --workspace-root ~/opt-workspace
```

### 10.2 OpenClaw Cron (Demo Mode)

Override cron to check every 10 seconds instead of daily:
```json5
{
  cron: {
    inbox_check: {
      every: "*/10 * * * * *",  // Every 10 seconds for demo
      session: "main",
      payload: {
        kind: "agentTurn",
        message: "Check ~/opt-workspace/tenants/demo-acme/clients/demo-acme/inbox/"
      }
    }
  }
}
```

---

## 11. Success Criteria

The demo is ready to present when:

- [ ] `controller.py --mode dry-run` completes without errors
- [ ] `controller.py --mode recording` produces all expected Slack messages
- [ ] Unit mismatch is caught and normalized visibly
- [ ] Ambiguity surfaces in Slack preview
- [ ] HybridSolver job completes with gap < 1%
- [ ] MEMORY.md entry appears after completion
- [ ] Total demo time < 3 minutes
- [ ] No API keys visible in any output
- [ ] `audience_onepager.md` reviewed and finalized
- [ ] Docker-compose brings up clean environment in < 60s

---

## 12. Anti-Replication Final Check

Before presenting:
- [ ] `grep -r "solve(" scripts/ api/` returns ZERO results (excluding comments)
- [ ] `grep -r "scipy\|ortools\|gurobipy" scripts/ api/` returns ZERO results
- [ ] All solver progress shows Quantagonia branding/job IDs
- [ ] Narration script explicitly states "Your engine solves. Our agent prepares."

---

*End of Phase 5 Spec. This is the final phase — demo delivery.*
