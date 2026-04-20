# PHASE 2 SPEC: Multi-Stage Orchestration & Solver Iteration

**Parent:** PRD.MD (§ "The demo: an autonomous production-planning agent for decomposed MILPs")
**Prerequisite:** Phase 1 complete (single-request pipeline: intake → validate → compile → submit)
**Scope:** Sequential multi-stage solves, parallel QUBO exploration, formulation repair on failure, institutional memory accumulation
**Boundary:** Blueprint only. No application code.
**Date:** 2026-04-20

---

## 0. Phase 2 Objectives (from Master PRD)

Phase 1 handles a **single optimization request** end-to-end. Phase 2 extends this to:

1. **Multi-stage sequential decomposition** — Annual production plans split into Q1→Q2→Q3→Q4, where each quarter's ending state becomes the next quarter's starting conditions
2. **Parallel QUBO reformulation** — Simultaneously submit binary MILPs with `--as-qubo` on a subagent lane to test if heuristic reformulation beats branch-and-bound
3. **Formulation iteration on solver failure** — When solver returns TIMEOUT/poor gap, the agent modifies formulation parameters and resubmits
4. **Institutional memory accumulation** — Cross-run learning stored in MEMORY.md, semantically retrievable for future requests

---

## 1. Dependency Additions

### `requirements.txt` (appended)

```
# Phase 2 additions
aiofiles>=24.1.0
asyncio-pool>=0.7.0
```

No new external services. All Phase 2 logic uses the same Quantagonia SDK, PuLP, and OpenClaw primitives from Phase 1.

---

## 2. New Pydantic Schemas (`scripts/schemas_v2.py`)

### 2.1 `StageDefinition` (BaseModel)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `stage_id` | `str` | `pattern=r'^[a-zA-Z0-9_-]+$'` | e.g., "q1_2026", "q2_2026" |
| `stage_order` | `int` | `ge=1` | Execution sequence (1 = first) |
| `depends_on` | `list[str]` | default `[]` | Stage IDs this stage depends on |
| `input_files` | `list[str]` | `min_length=1` | Source data files for this stage |
| `carry_forward_variables` | `list[str]` | default `[]` | Variable IDs whose solution values become fixed inputs for next stage |
| `time_limit_override` | `int | None` | optional | Per-stage time limit (seconds) |
| `qubo_eligible` | `bool` | default `False` | Whether to attempt parallel QUBO |

### 2.2 `DecompositionPlan` (BaseModel)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `plan_id` | `str` | required | Unique plan identifier |
| `account` | `str` | required | Client account |
| `description` | `str` | required | Human-readable plan description |
| `stages` | `list[StageDefinition]` | `min_length=2` | Ordered stages (must have ≥2 for decomposition) |
| `global_params` | `dict[str, Any]` | default `{}` | Parameters applied to all stages |
| `carry_forward_strategy` | `Literal["ending_inventory", "custom_variables", "full_solution"]` | required | How to propagate state |
| `created_at` | `datetime` | required | |

**Model Validators:**
1. `stages` must have unique `stage_id` values
2. All `depends_on` references must point to valid `stage_id` values
3. `stage_order` values must be sequential starting from 1
4. No circular dependencies
5. All `carry_forward_variables` must be valid variable IDs (checked at runtime against compiled bundle)

### 2.3 `StageResult` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `stage_id` | `str` | |
| `job_id` | `str` | HybridSolver job ID |
| `status` | `Literal["success", "timeout", "error", "reformulated"]` | Final status |
| `objective` | `float | None` | |
| `bound` | `float | None` | |
| `rel_gap` | `float | None` | |
| `wall_time` | `float | None` | |
| `billed_minutes` | `int` | |
| `solution` | `dict[str, float]` | Variable ID → value mapping (full solution) |
| `carry_forward_values` | `dict[str, float]` | Only the carry-forward variables |
| `qubo_attempted` | `bool` | |
| `qubo_result` | `QuboComparisonResult | None` | |
| `reformulation_attempts` | `int` | Number of iteration cycles |
| `memory_entries` | `list[str]` | Facts written to MEMORY.md |

### 2.4 `QuboComparisonResult` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `qubo_job_id` | `str` | |
| `qubo_objective` | `float | None` | |
| `qubo_wall_time` | `float | None` | |
| `qubo_billed_minutes` | `int | None` | |
| `mip_wins` | `bool` | True if MIP found better/equal objective |
| `recommendation` | `Literal["prefer_mip", "prefer_qubo", "inconclusive"]` | |

### 2.5 `PlanExecutionReport` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `plan_id` | `str` | |
| `account` | `str` | |
| `started_at` | `datetime` | |
| `completed_at` | `datetime | None` | |
| `stages_completed` | `int` | |
| `stages_total` | `int` | |
| `total_billed_minutes` | `int` | |
| `total_wall_time` | `float` | |
| `stage_results` | `list[StageResult]` | |
| `overall_status` | `Literal["completed", "partial", "failed"]` | |
| `memory_entries_written` | `int` | |

### 2.6 `ReformulationAction` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `action_type` | `Literal["tighten_presolve", "relax_gap", "try_qubo", "increase_time", "decompose_further"]` | |
| `rationale` | `str` | Why the agent chose this action |
| `param_changes` | `dict[str, Any]` | What was modified |
| `attempt_number` | `int` | |

---

## 3. File: `scripts/orchestrate_plan.py`

**Purpose:** Sequential multi-stage orchestrator. Executes a `DecompositionPlan`, propagates state between stages, manages parallel QUBO attempts, handles failures.

### 3.1 CLI Interface

```
python3 scripts/orchestrate_plan.py <plan_dir> [--dry-run] [--resume-from STAGE_ID]
```

- **Input:** `<plan_dir>/decomposition_plan.json`
- **Output:** `<plan_dir>/execution_report.json` + per-stage artifacts in `<plan_dir>/stages/<stage_id>/`
- **Exit code:** 0 = all stages completed, 1 = partial failure (some stages succeeded), 2 = fatal failure
- **Stdout:** Newline-delimited JSON events (compatible with OpenClaw JSONL capture)

### 3.2 Execution Flow

```
1. Load decomposition_plan.json → DecompositionPlan
2. Resolve execution order via topological sort on depends_on graph
3. FOR each stage in execution order:
   a. Check dependencies: all depends_on stages must have status="success"
   b. IF dependencies failed: mark stage as "skipped", continue
   c. Inject carry_forward_values from prior stage solutions into this stage's constraint_bundle:
      - For each carry_forward variable: add a new EQUALITY constraint fixing it to prior solution value
      - Log: {"event": "carry_forward", "stage_id": ..., "variables": {...}}
   d. Run: validate_bundle.py <stage_run_dir>
   e. Run: emit_pulp_artifacts.py <stage_run_dir> --lp
   f. IF stage.qubo_eligible:
      - SPAWN parallel QUBO submission (see §3.3)
   g. Run: submit_hybridsolver.py <stage_run_dir> --time-limit <stage.time_limit_override or global>
   h. IF solver returns TIMEOUT or poor gap (rel_gap > 0.05):
      - Enter reformulation loop (see §4)
   i. Parse solution, extract carry_forward_values
   j. Write StageResult
   k. Post progress to Slack: "Stage {stage_id} complete: obj={objective}, gap={gap}%, {billed}min billed"
   l. Write memory entry
4. Compile PlanExecutionReport
5. Post final summary to Slack
```

### 3.3 Parallel QUBO Strategy

When `stage.qubo_eligible == True` AND all variables in the stage are binary:

```
1. Submit MPS normally on main path (standard MIP)
2. SIMULTANEOUSLY submit same .mps.gz with --as-qubo flag
3. Wait for BOTH to complete (or first to reach good gap)
4. Compare results:
   - If QUBO finds same/better objective faster: record recommendation="prefer_qubo"
   - If MIP wins: record recommendation="prefer_mip"
5. Use the BETTER result as the stage solution
6. Write comparison to QuboComparisonResult
7. Memory entry: "Stage {id}: QUBO {faster|slower} by {delta}s, objective {same|worse|better}"
```

**Implementation:** The parallel QUBO job runs as a separate invocation of `submit_hybridsolver.py` with `--as-qubo` flag. The orchestrator monitors both jobs in an async loop.

### 3.4 Directory Layout Per Plan

```
<plan_dir>/
├── decomposition_plan.json
├── execution_report.json
├── stages/
│   ├── q1_2026/
│   │   ├── source/                    # Stage-specific input files
│   │   ├── carry_forward_input.json   # Injected from prior stage
│   │   ├── constraint_bundle.json
│   │   ├── validation_report.json
│   │   ├── model.py
│   │   ├── artifacts/
│   │   │   ├── problem.mps
│   │   │   ├── problem.mps.gz
│   │   │   └── problem.lp
│   │   ├── submission.json
│   │   ├── qubo_submission.json       # If QUBO attempted
│   │   ├── stage_result.json
│   │   └── reformulation_log.json     # If iteration occurred
│   ├── q2_2026/
│   │   ├── carry_forward_input.json   # Contains Q1 ending inventory
│   │   └── ...
│   ├── q3_2026/
│   └── q4_2026/
└── slack_thread.json
```

---

## 4. File: `scripts/reformulate.py`

**Purpose:** Solver failure handler. When a stage returns TIMEOUT or poor optimality gap, this script decides what to change and resubmits.

### 4.1 CLI Interface

```
python3 scripts/reformulate.py <stage_run_dir> --attempt <N> --failure-reason <timeout|poor_gap|error>
```

- **Input:** Stage run directory with `submission.json` (failed result) + solver logs
- **Output:** Updated `constraint_bundle.json` or `params.json`, then re-invokes the pipeline
- **Exit code:** 0 = reformulation succeeded (new submission ready), 1 = gave up after max attempts
- **Max attempts:** 3 (configurable)

### 4.2 Decision Tree

```
IF failure_reason == "timeout":
    IF attempt == 1:
        ACTION: increase time_limit by 2x
        RATIONALE: "Initial time limit may be insufficient for problem size"
    IF attempt == 2:
        ACTION: enable presolve aggressive + set heuristics_only for initial bound
        RATIONALE: "Tighten preprocessing to reduce search space"
    IF attempt == 3:
        ACTION: relax relative_gap to 0.05 (5%)
        RATIONALE: "Accept sub-optimal solution rather than no solution"

IF failure_reason == "poor_gap" (gap > 5%):
    IF attempt == 1:
        ACTION: try --as-qubo (if all binary)
        RATIONALE: "QUBO reformulation may find better heuristic bounds"
    IF attempt == 2:
        ACTION: increase time_limit by 3x
        RATIONALE: "Allow more time for branch-and-bound to close gap"
    IF attempt == 3:
        ACTION: accept current solution with warning
        RATIONALE: "Best-effort after exhausting reformulation options"

IF failure_reason == "error":
    IF error contains "infeasible":
        ACTION: invoke Gemini 3.1 Pro to identify conflicting constraints
        Use gemini_client.py repair with error context
    IF error contains "numerical":
        ACTION: scale all coefficients by normalizing to [0, 1000] range
    ELSE:
        ACTION: log and escalate to human (post to Slack)
```

### 4.3 Reformulation Log

Each attempt writes to `<stage_run_dir>/reformulation_log.json`:

```json
{
  "attempts": [
    {
      "attempt": 1,
      "action_type": "increase_time",
      "param_changes": {"time_limit": 7200},
      "rationale": "Initial time limit insufficient",
      "result": "timeout",
      "timestamp": "..."
    },
    {
      "attempt": 2,
      "action_type": "tighten_presolve",
      "param_changes": {"presolve": true, "heuristics_only": true},
      "rationale": "Reduce search space",
      "result": "success",
      "timestamp": "..."
    }
  ]
}
```

---

## 5. File: `scripts/carry_forward.py`

**Purpose:** State propagation between stages. Extracts solution values from a completed stage and injects them as fixed constraints into the next stage's bundle.

### 5.1 CLI Interface

```
python3 scripts/carry_forward.py <completed_stage_dir> <next_stage_dir> --variables <var_id_csv>
```

- **Input:** `<completed_stage_dir>/submission.json` (with solution), carry-forward variable list
- **Output:** `<next_stage_dir>/carry_forward_input.json` + modified `constraint_bundle.json`
- **Exit code:** 0 = success, 1 = missing solution values

### 5.2 Logic

```
1. Load solution from completed stage's submission.json → solution dict
2. For each variable_id in --variables:
   a. Look up value in solution dict
   b. IF not found: error (variable wasn't in the solved model)
   c. Create carry_forward_input.json entry: {variable_id: solved_value}
3. Load next stage's constraint_bundle.json
4. For each carry-forward variable:
   a. Add new constraint: "{variable_id}_carry_fwd": lhs=[{variable_id: 1.0}], op="==", rhs=solved_value
   b. Mark constraint as: is_inferred=True, confidence=1.0, source_file="carry_forward"
5. Write updated constraint_bundle.json
6. Log: {"event": "carry_forward_applied", "variables": {...}, "from_stage": ..., "to_stage": ...}
```

### 5.3 Carry-Forward Strategies

| Strategy | Behavior |
|----------|----------|
| `ending_inventory` | Only carry variables whose name matches `*_ending_inventory` or `*_end_inv` |
| `custom_variables` | Carry exactly the variables listed in `carry_forward_variables` |
| `full_solution` | Fix ALL variables from prior stage (makes next stage a warm-start) |

---

## 6. File: `scripts/memory_writer.py`

**Purpose:** Structured memory accumulation. After each stage or plan completion, writes durable facts to `MEMORY.md` and dated daily notes.

### 6.1 CLI Interface

```
python3 scripts/memory_writer.py <action> <run_dir> [--workspace <path>]
```

**Actions:**

| Action | What it writes |
|--------|---------------|
| `stage_complete` | Reads stage_result.json, writes performance facts to MEMORY.md |
| `plan_complete` | Reads execution_report.json, writes plan-level insights |
| `qubo_comparison` | Writes QUBO vs MIP recommendation for this problem class |
| `reformulation_learned` | Writes what reformulation strategy worked |
| `client_terminology` | Writes discovered terminology mappings from extraction |

### 6.2 MEMORY.md Entry Format

```markdown
## Client: {account} | {date}

### Problem Characteristics
- {num_variables} variables ({binary}B, {integer}I, {continuous}C)
- {num_constraints} constraints
- Density: {density}
- Solve time: {wall_time}s to {gap}% gap
- Billed: {minutes} minutes

### Learned Facts
- {fact_1}
- {fact_2}

### Recommendations for Next Run
- {recommendation_1}
- {recommendation_2}
```

### 6.3 Daily Notes Format

Written to `memory/YYYY-MM-DD.md`:

```markdown
### {timestamp} — {plan_id} / {stage_id}

- Status: {success|timeout|reformulated}
- Anomalies: {any schema drift, validator rejections, unexpected patterns}
- Reformulation: {if any, what worked}
```

### 6.4 Memory Retrieval Interface

```python
def load_client_memory(workspace: str, account: str) -> str:
    """Load relevant MEMORY.md entries for a specific client account."""
```

Searches MEMORY.md for entries matching the account name. Returns concatenated text for injection into Gemini extraction prompts (Phase 1's `prior_context` parameter).

---

## 7. File: `scripts/plan_generator.py`

**Purpose:** Given a set of input files and metadata, generate a `DecompositionPlan` using Gemini 3.1 Pro to identify natural decomposition boundaries.

### 7.1 CLI Interface

```
python3 scripts/plan_generator.py <input_dir> --account <account> --strategy <quarterly|custom>
```

- **Input:** Directory of raw data files + metadata
- **Output:** `decomposition_plan.json`
- **Exit code:** 0 = plan generated, 1 = cannot decompose (treat as single-stage)

### 7.2 Logic

```
1. Scan input_dir for files, classify via gemini_client.py classify
2. IF strategy == "quarterly":
   a. Detect time-series columns in tabular data (look for date/quarter/period columns)
   b. Split data by quarter boundaries
   c. Generate 4 stages with sequential dependencies
   d. Identify inventory/state variables that carry forward
3. IF strategy == "custom":
   a. Send all file summaries to Gemini 3.1 Pro with prompt:
      "Identify natural decomposition boundaries in this optimization problem.
       What stages can be solved sequentially? What state propagates between them?"
   b. Parse structured response into StageDefinition list
4. Validate plan (no cycles, valid dependencies)
5. Write decomposition_plan.json
```

### 7.3 Quarterly Decomposition Heuristics

| Signal | Interpretation |
|--------|---------------|
| Column headers containing "Q1", "Q2", "Q3", "Q4" | Quarterly time periods |
| Column "period" with values 1-4 or 1-12 | Monthly/quarterly decomposition |
| Separate tabs per quarter in XLSX | Natural stage boundary |
| Variables named `*_ending_*` or `*_carry_*` | Carry-forward candidates |
| Constraints referencing "previous period" | Temporal dependency |

---

## 8. OpenClaw Skill Update

**File:** `~/opt-workspace/skills/constraint-intake-hybrid/SKILL.md`

### 8.1 Additional Workflow Sections (append to existing)

```markdown
### Phase F: Multi-Stage Plan Detection
20. After single-request extraction, check if data contains temporal decomposition signals
21. IF quarterly/temporal data detected:
    - Run: `exec python3 scripts/plan_generator.py <staging_dir> --account <acct> --strategy quarterly`
    - Post to Slack: "Detected multi-stage optimization (4 quarters). Generating decomposition plan."
    - Await APPROVE for plan execution

### Phase G: Sequential Execution
22. Run: `exec python3 scripts/orchestrate_plan.py <plan_dir>`
23. Monitor stdout for stage completion events
24. Post per-stage progress to Slack thread
25. IF any stage fails and reformulation exhausted:
    - Post failure details to Slack
    - HALT (await human guidance)
26. On plan completion: post final summary with total cost/time

### Phase H: Institutional Memory
27. Run: `exec python3 scripts/memory_writer.py plan_complete <plan_dir>`
28. IF QUBO comparison available: `exec python3 scripts/memory_writer.py qubo_comparison <stage_dir>`
29. Post memory update confirmation to Slack: "Learned {N} new facts about {account}'s problem structure."
```

### 8.2 OpenClaw Subagent Configuration (for parallel QUBO)

```json5
// Addition to ~/.openclaw/openclaw.json
{
  agents: {
    list: [
      // ... existing intake-agent ...
      {
        agentId: "qubo-explorer",
        workspace: "~/opt-workspace",
        model: { primary: "google/gemini-3-flash" },
        // Lightweight agent that just submits and monitors QUBO jobs
        skills: ["constraint_intake_hybrid"]
      }
    ]
  }
}
```

The `qubo-explorer` subagent is spawned via `sessions_spawn` on the subagent lane (concurrency 4). It receives the `.mps.gz` path and submits with `--as-qubo`. Its result is announced back to the main session.

---

## 9. Integration Contracts (Phase 2 Additions)

### 9.1 New Script → Script Data Flow

```
plan_generator.py
    → input: raw data directory
    → output: decomposition_plan.json

orchestrate_plan.py
    → input: decomposition_plan.json
    → orchestrates: validate_bundle.py → emit_pulp_artifacts.py → submit_hybridsolver.py (per stage)
    → calls: carry_forward.py between stages
    → calls: reformulate.py on failure
    → output: execution_report.json

carry_forward.py
    → input: completed stage submission.json + next stage constraint_bundle.json
    → output: modified constraint_bundle.json with fixed carry-forward constraints

reformulate.py
    → input: failed stage directory + failure reason
    → output: modified params or bundle, re-invokes submit pipeline
    → may call: gemini_client.py repair (for infeasibility)

memory_writer.py
    → input: stage/plan results
    → output: MEMORY.md entries, memory/YYYY-MM-DD.md entries
```

### 9.2 OpenClaw exec Calls (Phase 2)

| Step | Command | Notes |
|------|---------|-------|
| Plan generation | `python3 scripts/plan_generator.py <dir> --account <acct> --strategy quarterly` | After Phase 1 extraction |
| Orchestration | `python3 scripts/orchestrate_plan.py <plan_dir>` | Long-running; streams progress |
| Carry-forward | `python3 scripts/carry_forward.py <prev_dir> <next_dir> --variables x1,x2,x3` | Between stages |
| Reformulation | `python3 scripts/reformulate.py <stage_dir> --attempt 1 --failure-reason timeout` | On solver failure |
| Memory write | `python3 scripts/memory_writer.py stage_complete <stage_dir>` | After each stage |
| QUBO submit | `python3 scripts/submit_hybridsolver.py <stage_dir> --as-qubo` | Parallel on subagent |

---

## 10. Slack Thread Extensions (Phase 2)

### 10.1 New Message Types for `slack_notify.py`

| Action | Message Content |
|--------|----------------|
| `plan_detected` | "Detected multi-stage optimization ({N} stages). Plan: {description}. Reply APPROVE to execute." |
| `stage_started` | "Starting stage {stage_id} ({order}/{total})..." |
| `stage_complete` | "Stage {stage_id}: obj={objective}, gap={gap}%, time={wall_time}s, billed={minutes}min" |
| `qubo_result` | "QUBO comparison: MIP={mip_obj} in {mip_time}s vs QUBO={qubo_obj} in {qubo_time}s → Recommend: {recommendation}" |
| `reformulating` | "Stage {stage_id} failed ({reason}). Attempting reformulation {attempt}/3: {action_type}" |
| `plan_complete` | "Plan complete. {stages_completed}/{total} stages. Total: obj={sum_obj}, billed={total_minutes}min, learned {N} facts." |
| `memory_learned` | "Learned: {fact}" |

---

## 11. Testing Strategy (Phase 2)

### 11.1 Unit Tests

| File | Coverage |
|------|----------|
| `tests/test_schemas_v2.py` | DecompositionPlan validation: cycle detection, dependency ordering, carry-forward refs |
| `tests/test_carry_forward.py` | Solution extraction, constraint injection, strategy variants |
| `tests/test_reformulate.py` | Decision tree logic, param changes per attempt/failure |
| `tests/test_orchestrate.py` | Sequential execution with mocked solver, dependency skipping |

### 11.2 Integration Test

**Fixture:** 4-quarter production planning scenario:
- Q1 input: demand + capacity CSVs, 20 binary + 10 continuous variables
- Q2-Q4: same structure, with Q(n-1) ending inventory as Q(n) starting constraint
- Q2 deliberately sized to TIMEOUT at 60s limit → triggers reformulation

**Pass criteria:**
- [ ] Plan generator detects quarterly structure and produces valid DecompositionPlan
- [ ] Q1 solves successfully, carry-forward extracts ending_inventory variables
- [ ] Q2 receives carry-forward constraints as equality constraints
- [ ] Q2 timeout triggers reformulation → increased time limit → success
- [ ] Q3 and Q4 complete normally
- [ ] MEMORY.md entry written with solve characteristics
- [ ] Slack thread shows per-stage progress
- [ ] Execution report contains all 4 stage results
- [ ] Total billed minutes reported accurately

### 11.3 Test Fixtures

```
~/opt-workspace/tests/fixtures/
├── multi_stage_plan/
│   ├── inputs/
│   │   ├── demand_q1.csv
│   │   ├── demand_q2.csv
│   │   ├── demand_q3.csv
│   │   ├── demand_q4.csv
│   │   ├── capacity.csv
│   │   └── sku_routing.csv
│   └── expected_outputs/
│       ├── decomposition_plan.json
│       └── execution_report.json (template)
```

---

## 12. Anti-Replication Verification (Phase 2 Additions)

- [ ] `orchestrate_plan.py` never calls `prob.solve()` — it invokes `submit_hybridsolver.py` via subprocess/exec
- [ ] `reformulate.py` only changes parameters/constraints, never implements solving logic
- [ ] `carry_forward.py` only reads solution dicts, never generates solutions
- [ ] QUBO reformulation delegated entirely to HybridSolver's `--as-qubo` flag (no custom QUBO conversion code)
- [ ] Memory entries never claim "we optimized" — only "HybridSolver solved"

---

## 13. Phase 2 → Phase 3 Boundary

Phase 2 does NOT include:
- Multi-tenant isolation (all runs share one workspace)
- Production hardening (retry with circuit breaker, rate limiting)
- Web dashboard or API server
- Cost tracking/billing integration
- Automated CI/CD for model validation
- Multi-model consensus (running same extraction on multiple LLMs)

These belong to Phase 3 (production readiness).

---

*End of Phase 2 Spec.*
