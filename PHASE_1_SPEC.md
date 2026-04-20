# PHASE 1 SPEC: File-by-File Technical Blueprint

**Parent:** ULTIMATE_PRD.md (Phase 1 Execution Spec)
**Scope:** Deterministic Python gate scripts + OpenClaw skill wiring
**Boundary:** Blueprint only. No application code. Execution agent consumes this.
**Date:** 2026-04-20

---

## 0. Dependency Manifest

### `requirements.txt`

```
quantagonia>=0.15.0
pulp>=3.3.0
pandas>=2.2.0
pydantic>=2.0
openpyxl>=3.1.0
pdfplumber>=0.11.0
python-dotenv>=1.0.0
slack-sdk>=3.30.0
google-genai>=1.5.0
```

### Version Justifications

| Package | Why This Version | Critical API Surface |
|---------|-----------------|---------------------|
| `quantagonia>=0.15.0` | Async submit/progress/status confirmed. `HybridSolver(api_key)` → `.submit()` → `.progress()` → `.status()` → `.logs()` | `HybridSolver`, `HybridSolverParameters`, `JobStatus` enum |
| `pulp>=3.3.0` | Stable `writeMPS()`, `writeLP()`, `LpSolver_CMD` interface | `LpProblem`, `LpVariable`, `lpSum`, `writeMPS`, `writeLP` |
| `pydantic>=2.0` | V2 API: `model_validator(mode='after')`, `field_validator`, strict mode, `model_dump_json()` | `BaseModel`, `Field`, `field_validator`, `model_validator`, `ConfigDict` |
| `pandas>=2.2.0` | `read_excel(engine='openpyxl')`, `read_csv()`. No `DataFrame.append()` — use `pd.concat()` | `read_excel`, `read_csv`, `DataFrame`, `pd.concat` |
| `pdfplumber>=0.11.0` | Table + text extraction from PDF contracts | `open()`, `pages`, `extract_text()`, `extract_tables()` |
| `openpyxl>=3.1.0` | Excel engine for pandas | Implicit via `pandas.read_excel(engine='openpyxl')` |
| `slack-sdk>=3.30.0` | Thread posting, file upload, reaction events | `WebClient`, `chat_postMessage`, `files_upload_v2` |
| `google-genai>=1.5.0` | Gemini 3 Flash + 3.1 Pro structured output | `GenerativeModel`, `generate_content`, `response_schema` |
| `python-dotenv>=1.0.0` | Local dev .env loading (Codespaces uses native secrets) | `load_dotenv()` |

### Python Version

**>= 3.11** (Ubuntu 22.04 Codespaces default). PuLP floor is 3.9; we target 3.11 for `tomllib`, `StrEnum`, `ExceptionGroup`.

---

## 1. File: `scripts/schemas.py`

**Purpose:** Central Pydantic v2 schema definitions. All other scripts import from here. Single source of truth for the constraint bundle JSON structure.

### 1.1 `VariableType` (StrEnum)

```
class VariableType(StrEnum):
    CONTINUOUS = "continuous"
    INTEGER = "integer"
    BINARY = "binary"
```

### 1.2 `ConstraintOperator` (StrEnum)

```
class ConstraintOperator(StrEnum):
    LEQ = "<="
    GEQ = ">="
    EQ = "=="
```

### 1.3 `ObjectiveSense` (StrEnum)

```
class ObjectiveSense(StrEnum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"
```

### 1.4 `UnitSpec` (BaseModel)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `quantity` | `str` | required | Physical quantity (e.g., "mass", "time", "volume") |
| `unit` | `str` | required | Unit string (e.g., "kg", "tons", "hours") |
| `normalized_to` | `str \| None` | optional | Target unit after normalization |
| `conversion_factor` | `float \| None` | optional | Multiplier to convert to normalized unit |

### 1.5 `DecisionVariable` (BaseModel)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str` | `min_length=1`, `pattern=r'^[a-zA-Z_][a-zA-Z0-9_]*$'` | Unique variable identifier (valid Python/MPS name) |
| `name` | `str` | required | Human-readable name |
| `type` | `VariableType` | required | Variable domain |
| `lower_bound` | `float \| None` | default `0.0` | Lower bound (None = -inf) |
| `upper_bound` | `float \| None` | default `None` | Upper bound (None = +inf) |
| `unit` | `UnitSpec \| None` | optional | Physical unit if applicable |
| `source_file` | `str` | required | Which input file this was extracted from |
| `confidence` | `float` | `ge=0.0, le=1.0` | Extraction confidence from LLM |

**Validators:**
- `field_validator('id')`: reject MPS reserved words (`ROWS`, `COLUMNS`, `RHS`, `BOUNDS`, `RANGES`, `OBJSENSE`)
- `field_validator('lower_bound', 'upper_bound')`: if both set, `lower_bound <= upper_bound`
- `field_validator('lower_bound')`: if type is BINARY, must be 0 or None
- `field_validator('upper_bound')`: if type is BINARY, must be 1 or None

### 1.6 `Coefficient` (BaseModel)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `variable_id` | `str` | required | References `DecisionVariable.id` |
| `value` | `float` | required | Coefficient value |

### 1.7 `Constraint` (BaseModel)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str` | `min_length=1`, `pattern=r'^[a-zA-Z_][a-zA-Z0-9_]*$'` | Unique constraint ID |
| `name` | `str` | required | Human-readable description |
| `lhs` | `list[Coefficient]` | `min_length=1` | Left-hand side coefficients |
| `operator` | `ConstraintOperator` | required | Comparison operator |
| `rhs` | `float` | required | Right-hand side constant |
| `source_file` | `str` | required | Origin file |
| `source_text` | `str \| None` | optional | Verbatim text from source document |
| `is_inferred` | `bool` | default `False` | True if LLM inferred (not explicit in text) |
| `confidence` | `float` | `ge=0.0, le=1.0` | Extraction confidence |

**Validators:**
- `field_validator('lhs')`: all `variable_id` values must be unique within a single constraint
- `field_validator('rhs')`: warn (don't reject) if absolute value > 1e12 (potential data error)

### 1.8 `ObjectiveTerm` (BaseModel)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `variable_id` | `str` | required | References `DecisionVariable.id` |
| `coefficient` | `float` | required | Objective coefficient |

### 1.9 `Objective` (BaseModel)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `sense` | `ObjectiveSense` | required | Minimize or maximize |
| `terms` | `list[ObjectiveTerm]` | `min_length=1` | Objective function terms |
| `constant` | `float` | default `0.0` | Constant offset |
| `description` | `str` | required | Human-readable objective description |

### 1.10 `ConstraintBundle` (BaseModel) — Top-Level Schema

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `request_id` | `str` | required | Matches folder name `<request_id>` |
| `account` | `str` | required | Client account identifier |
| `created_at` | `datetime` | required | ISO 8601 timestamp |
| `source_files` | `list[str]` | `min_length=1` | List of input filenames processed |
| `variables` | `list[DecisionVariable]` | `min_length=1` | All decision variables |
| `constraints` | `list[Constraint]` | `min_length=1` | All constraints |
| `objective` | `Objective` | required | Objective function |
| `units_normalized` | `bool` | default `False` | Whether unit normalization was applied |
| `normalization_log` | `list[str]` | default `[]` | Human-readable log of unit conversions |
| `ambiguities` | `list[str]` | default `[]` | Unresolved items requiring human input |
| `metadata` | `dict[str, Any]` | default `{}` | Extensible metadata |

**Model Validators (`model_validator(mode='after')`):**
1. All `variable_id` references in `constraints[].lhs[].variable_id` must exist in `variables[].id`
2. All `variable_id` references in `objective.terms[].variable_id` must exist in `variables[].id`
3. No duplicate `variables[].id` values
4. No duplicate `constraints[].id` values
5. Every variable must appear in at least one constraint OR in the objective (warn, don't reject)

### 1.11 `ValidationReport` (BaseModel)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `request_id` | `str` | required | |
| `passed` | `bool` | required | Overall pass/fail |
| `errors` | `list[ValidationError_]` | default `[]` | Blocking errors |
| `warnings` | `list[ValidationWarning]` | default `[]` | Non-blocking warnings |
| `unit_conversions` | `list[UnitConversion]` | default `[]` | Applied normalizations |
| `stats` | `BundleStats` | required | Summary statistics |
| `validated_at` | `datetime` | required | |

### 1.12 `ValidationError_` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `code` | `str` | Machine-readable error code (e.g., `DUPLICATE_VAR_ID`, `DANGLING_REF`, `IMPOSSIBLE_VALUE`) |
| `message` | `str` | Human-readable explanation |
| `path` | `str` | JSON path to offending field (e.g., `variables[3].lower_bound`) |
| `severity` | `Literal["error"]` | Always "error" |

### 1.13 `ValidationWarning` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `code` | `str` | e.g., `LARGE_RHS`, `UNUSED_VARIABLE`, `LOW_CONFIDENCE` |
| `message` | `str` | Human-readable |
| `path` | `str` | JSON path |
| `severity` | `Literal["warning"]` | Always "warning" |

### 1.14 `UnitConversion` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `variable_id` | `str` | Which variable was affected |
| `from_unit` | `str` | Original unit |
| `to_unit` | `str` | Normalized unit |
| `factor` | `float` | Conversion factor applied |
| `affected_constraints` | `list[str]` | Constraint IDs whose RHS/coefficients were adjusted |

### 1.15 `BundleStats` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `num_variables` | `int` | |
| `num_continuous` | `int` | |
| `num_integer` | `int` | |
| `num_binary` | `int` | |
| `num_constraints` | `int` | |
| `num_objective_terms` | `int` | |
| `density` | `float` | Non-zero coefficients / (variables * constraints) |

### 1.16 `SubmissionRecord` (BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | `str` | |
| `job_id` | `str` | HybridSolver job ID |
| `submitted_at` | `datetime` | |
| `input_file` | `str` | Path to submitted .mps.gz |
| `params` | `dict[str, Any]` | HybridSolverParameters used |
| `status` | `str` | Latest known status |
| `objective` | `float \| None` | Best objective found |
| `bound` | `float \| None` | Best bound |
| `rel_gap` | `float \| None` | Relative gap |
| `wall_time` | `float \| None` | Seconds |
| `billed_minutes` | `int \| None` | |

---

## 2. File: `scripts/validate_bundle.py`

**Purpose:** Deterministic validation gate. Reads `constraint_bundle.json`, validates against Pydantic schemas, applies unit normalization, rejects impossible values. Emits `validation_report.json`.

### 2.1 CLI Interface

```
python3 scripts/validate_bundle.py <run_dir>
```

- **Input:** `<run_dir>/constraint_bundle.json`
- **Output:** `<run_dir>/validation_report.json`
- **Exit code:** 0 = passed, 1 = failed (with report), 2 = fatal (cannot parse input)
- **Stdout:** JSON one-liner `{"passed": bool, "errors": int, "warnings": int}` (for OpenClaw JSONL capture)

### 2.2 Validation Pipeline (ordered)

| Step | Name | Logic | Error Code |
|------|------|-------|------------|
| 1 | Schema Parse | `ConstraintBundle.model_validate_json(raw)` — catches type errors, missing fields, pattern violations | `SCHEMA_INVALID` |
| 2 | Duplicate ID Check | Set-based: `variables[].id` uniqueness, `constraints[].id` uniqueness | `DUPLICATE_VAR_ID`, `DUPLICATE_CONSTRAINT_ID` |
| 3 | Referential Integrity | All `variable_id` refs in constraints + objective resolve to a declared variable | `DANGLING_VARIABLE_REF` |
| 4 | Impossible Value Rejection | (a) Negative capacities: any variable with `lower_bound < 0` where name contains "capacity"/"demand"/"quantity" → error. (b) Percentages > 100 or < 0 when unit is "%". (c) `lower_bound > upper_bound`. (d) Binary variable with bounds outside [0,1]. | `IMPOSSIBLE_VALUE` |
| 5 | Unit Normalization | Group variables by `unit.quantity`. If mixed `unit.unit` within same quantity, normalize to the most common unit. Apply `conversion_factor` to all affected RHS and coefficient values. Set `units_normalized=True`. | (warnings only unless conversion fails) |
| 6 | Orphan Variable Warning | Variables that appear in no constraint and not in objective | `UNUSED_VARIABLE` (warning) |
| 7 | Large Value Warning | Any coefficient or RHS with `abs(value) > 1e9` | `LARGE_COEFFICIENT` (warning) |
| 8 | Low Confidence Warning | Any variable/constraint with `confidence < 0.7` | `LOW_CONFIDENCE` (warning) |

### 2.3 Unit Normalization Rules

| Quantity | Canonical Unit | Known Aliases → Factor |
|----------|---------------|----------------------|
| mass | kg | tons→1000, lbs→0.453592, g→0.001 |
| time | hours | minutes→1/60, days→24, shifts→8 |
| volume | liters | m3→1000, gallons→3.78541 |
| currency | EUR | USD→(configurable), GBP→(configurable) |

The conversion table is a dict in `validate_bundle.py`. Currency conversions are NOT applied automatically — they produce a warning + ambiguity entry instead.

### 2.4 Output Contract

`validation_report.json` is written as `ValidationReport.model_dump_json(indent=2)`.

If validation **passes**: the original `constraint_bundle.json` is overwritten with the normalized version (units adjusted, `units_normalized=True`, `normalization_log` populated).

If validation **fails**: `constraint_bundle.json` is NOT modified. The report contains all errors for the LLM repair loop.

---

## 3. File: `scripts/emit_pulp_artifacts.py`

**Purpose:** Deterministic compiler. Reads validated `constraint_bundle.json`, generates a PuLP model, writes `.mps` (primary), `.lp` (optional), `.qubo` (conditional).

### 3.1 CLI Interface

```
python3 scripts/emit_pulp_artifacts.py <run_dir> [--lp] [--qubo]
```

- **Input:** `<run_dir>/constraint_bundle.json` (must have `units_normalized=True` or no unit specs)
- **Output:**
  - `<run_dir>/model.py` — generated PuLP source code (for audit)
  - `<run_dir>/artifacts/problem.mps` — primary artifact
  - `<run_dir>/artifacts/problem.mps.gz` — gzipped for submission
  - `<run_dir>/artifacts/problem.lp` — only if `--lp` flag
  - `<run_dir>/artifacts/problem.qubo` — only if `--qubo` AND all variables are BINARY
- **Exit code:** 0 = success, 1 = compilation error
- **Stdout:** JSON one-liner `{"variables": int, "constraints": int, "mps_path": str, "mps_size_bytes": int}`

### 3.2 Generation Logic

| Step | Action |
|------|--------|
| 1 | Load and parse `constraint_bundle.json` via `ConstraintBundle.model_validate_json()` |
| 2 | Create `LpProblem(name=request_id, sense=LpMinimize\|LpMaximize)` based on `objective.sense` |
| 3 | For each `DecisionVariable`: create `LpVariable(id, lowBound, upBound, cat=)` where cat maps: CONTINUOUS→`LpContinuous`, INTEGER→`LpInteger`, BINARY→`LpBinary` |
| 4 | Set objective: `prob += lpSum([coeff * var_map[term.variable_id] for term in objective.terms]) + objective.constant` |
| 5 | For each `Constraint`: `prob += (lpSum([c.value * var_map[c.variable_id] for c in lhs]) op rhs, constraint.id)` where op is `<=`, `>=`, or `==` |
| 6 | Write `prob.writeMPS(artifacts/problem.mps)` |
| 7 | If `--lp`: write `prob.writeLP(artifacts/problem.lp)` |
| 8 | Gzip: `gzip problem.mps → problem.mps.gz` |
| 9 | If `--qubo` and ALL variables are BINARY: convert to QUBO format (PuLP doesn't natively export QUBO — use Quantagonia CLI `hybridsolver submit --as-qubo-only` at submission time instead). Write a `problem.qubo_eligible` marker file. |
| 10 | Write `model.py` as a Python source file that reconstructs the PuLP model (for human audit) |

### 3.3 `model.py` Template Structure

```python
"""Auto-generated PuLP model for request: {request_id}
Generated: {timestamp}
Variables: {n_vars} | Constraints: {n_cons}
DO NOT EDIT — regenerate via emit_pulp_artifacts.py
"""
from pulp import *

prob = LpProblem("{request_id}", Lp{Minimize|Maximize})

# Variables
{for each var: x_{id} = LpVariable("{id}", {lb}, {ub}, cat="{cat}")}

# Objective
prob += {objective_expression}, "objective"

# Constraints
{for each constraint: prob += ({lhs_expression} {op} {rhs}), "{constraint_id}"}

# Export
prob.writeMPS("artifacts/problem.mps")
```

### 3.4 QUBO Eligibility Check

A problem is QUBO-eligible IFF:
- ALL variables have `type == BINARY`
- ALL constraints are equality or can be penalized into objective
- No explicit flag override preventing QUBO

If `--qubo` is passed but problem is NOT eligible: exit with error code 1 and message `"QUBO requested but problem contains non-binary variables"`.

---

## 4. File: `scripts/submit_hybridsolver.py`

**Purpose:** Async submission to Quantagonia HybridSolver. Implements the non-blocking `submit → progress → status → logs` loop documented in the SDK.

### 4.1 CLI Interface

```
python3 scripts/submit_hybridsolver.py <run_dir> [--time-limit SECONDS] [--rel-gap FLOAT] [--as-qubo]
```

- **Input:** `<run_dir>/artifacts/problem.mps.gz`
- **Output:** `<run_dir>/submission.json`
- **Exit code:** 0 = job completed (SUCCESS/FINISHED), 1 = job failed/error, 2 = timeout, 3 = cancelled
- **Stdout:** Newline-delimited JSON progress events (one per poll cycle)
- **Env required:** `QUANTAGONIA_API_KEY` (NEVER read from argv, NEVER echoed)

### 4.2 Execution Flow

```
1. Load QUANTAGONIA_API_KEY from os.environ (fail with exit 2 if missing)
2. solver = HybridSolver(api_key)
3. params = HybridSolverParameters()
4.   params.set_time_limit(time_limit)          # if --time-limit
5.   params.set_relative_gap(rel_gap)           # if --rel-gap
6. job_id = solver.submit(mps_gz_path, params, tag=request_id)
7. Print: {"event": "submitted", "job_id": job_id, "timestamp": ...}
8. LOOP (poll_frequency = 5.0 seconds):
9.   status = solver.status(job_id)
10.  progress = solver.progress(job_id)[0]
11.  Print: {"event": "progress", "job_status": ..., "solver_status": ..., 
             "objective": ..., "bound": ..., "rel_gap": ..., 
             "wall_time": ..., "num_incumbents": ..., "timestamp": ...}
12.  IF status in (JobStatus.finished, JobStatus.terminated, JobStatus.timeout): BREAK
13. logs = solver.logs(job_id)
14. Final record = SubmissionRecord(...)
15. Write submission.json
16. Print: {"event": "completed", "status": status.value, "objective": ..., "bound": ..., "rel_gap": ..., "billed_minutes": ...}
```

### 4.3 HybridSolverParameters Mapping

| CLI Flag | SDK Method | Default |
|----------|-----------|---------|
| `--time-limit` | `params.set_time_limit(int)` | 3600 (1 hour) |
| `--rel-gap` | `params.set_relative_gap(float)` | 0.01 (1%) |
| `--as-qubo` | CLI: `hybridsolver submit --as-qubo` / SDK: via kwargs | False |

### 4.4 Error Handling

| Condition | Behavior |
|-----------|----------|
| `QUANTAGONIA_API_KEY` not set | Exit 2, stderr: `"QUANTAGONIA_API_KEY environment variable not set"` |
| `.mps.gz` file not found | Exit 1, stderr: `"Input file not found: {path}"` |
| Network error during submit | Retry 3x with exponential backoff (2s, 4s, 8s), then exit 1 |
| Network error during progress poll | Log warning, continue polling |
| Job status = ERROR | Exit 1, write submission.json with error details |
| Job status = TIMEOUT | Exit 2, write submission.json |
| Job status = TERMINATED (cancelled) | Exit 3 |

### 4.5 Security Invariants

- `QUANTAGONIA_API_KEY` MUST NOT appear in:
  - stdout (progress JSON)
  - submission.json
  - Any log message
  - OpenClaw JSONL transcripts
- The script receives the key via environment only. OpenClaw's `exec` tool passes env vars without logging them.

---

## 5. File: `scripts/watch_inbox.py`

**Purpose:** Filesystem watcher. Polls `clients/*/inbox/` for new request folders. Emits structured events to stdout for OpenClaw cron consumption.

### 5.1 CLI Interface

```
python3 scripts/watch_inbox.py <workspace_root>
```

- **Input:** `<workspace_root>/clients/*/inbox/` directory tree
- **Output (stdout):** Newline-delimited JSON, one event per new request detected
- **Exit code:** 0 = scan complete (even if 0 new requests)
- **Side effect:** Moves detected request folders from `inbox/` to `staging/`

### 5.2 Detection Logic

```
1. Glob: workspace_root/clients/*/inbox/*/
2. For each folder found:
   a. Check if folder contains at least 1 file (not just subdirs)
   b. Check if folder name does NOT exist in staging/ or runs/ (already processed)
   c. If new:
      - Generate request_id from folder name (sanitize: lowercase, replace spaces with hyphens)
      - Move folder to clients/<account>/staging/<request_id>/
      - Emit: {"event": "new_request", "account": "<account>", "request_id": "<id>", 
               "files": [...], "timestamp": "..."}
3. Print summary: {"event": "scan_complete", "new_requests": int, "timestamp": "..."}
```

### 5.3 File Inventory

For each detected request, the `files` array contains objects:

```json
{"name": "filename.ext", "size_bytes": int, "type": "pdf|xlsx|csv|docx|txt|unknown"}
```

Type detection is extension-based only (no magic bytes needed for Phase 1).

### 5.4 Folder State Machine

```
inbox/<request_id>/     →  User drops files here
staging/<request_id>/   →  watch_inbox.py moves here on detection
approved/<request_id>/  →  Human moves here OR Slack APPROVE triggers move
runs/<request_id>/      →  Agent creates here for all intermediate artifacts
```

---

## 6. File: `scripts/slack_notify.py`

**Purpose:** Utility for posting structured messages to Slack threads. Called by OpenClaw skill via exec.

### 6.1 CLI Interface

```
python3 scripts/slack_notify.py <action> <run_dir> [--channel CHANNEL] [--thread-ts THREAD_TS]
```

**Actions:**

| Action | What it posts |
|--------|--------------|
| `intake` | "Processing request {id} — {n} files detected ({breakdown})" |
| `preview` | Extraction preview: facts / inferences / ambiguities (reads constraint_bundle.json) |
| `validation` | Validation report summary (reads validation_report.json) |
| `artifacts` | "Compiled problem.mps ({n_vars} variables, {n_cons} constraints). Ready for submission?" |
| `submitted` | "Submitted to HybridSolver. Job ID: {job_id}" |
| `progress` | Progress update (objective, bound, gap, wall_time) |
| `completed` | Final result summary |
| `error` | Error notification with human-readable explanation |

### 6.2 Thread Management

- On first post (`intake`): creates a new thread, writes `slack_thread.json` with `{"channel": str, "thread_ts": str}`
- On subsequent posts: reads `slack_thread.json` for `thread_ts`, posts as reply
- If `--thread-ts` provided: uses that instead (for Slack-initiated requests)

### 6.3 Message Formatting

All messages use Slack Block Kit:
- Section blocks for text
- Divider blocks between sections
- Context blocks for metadata (timestamp, request_id)
- No code blocks for non-technical users (extraction preview uses bullet lists)

### 6.4 Env Required

- `SLACK_BOT_TOKEN` — Bot User OAuth Token with scopes: `chat:write`, `files:read`, `channels:history`

---

## 7. File: `scripts/gemini_client.py`

**Purpose:** Thin wrapper around Google GenAI SDK. Provides two entry points: Flash (triage) and Pro (extraction). Enforces structured output via `response_schema`.

### 7.1 Public Functions

#### `classify_files(file_inventory: list[dict]) -> FileClassification`

- **Model:** Gemini 3 Flash
- **Input:** File inventory from watch_inbox.py
- **Output schema:**

```python
class FileClassification(BaseModel):
    files: list[ClassifiedFile]
    missing_info: list[str]       # What's missing to formulate?
    ambiguities: list[str]        # What's unclear?

class ClassifiedFile(BaseModel):
    filename: str
    detected_type: Literal["pdf_contract", "xlsx_data", "csv_data", "docx_text", "nl_instructions", "unknown"]
    parser_route: Literal["pdf_parser", "tabular_parser", "text_parser", "skip"]
    summary: str                  # One-line content summary
```

#### `extract_constraints(parsed_documents: list[ParsedDocument], prior_context: str | None) -> ConstraintBundle`

- **Model:** Gemini 3.1 Pro
- **Input:** Parsed document contents + optional MEMORY.md context
- **Output schema:** `ConstraintBundle` (from schemas.py) — enforced via `response_schema` parameter
- **System prompt must include:**
  - "You are a mathematical optimization modeling assistant."
  - "Extract ONLY constraints explicitly stated or directly inferable from the provided documents."
  - "Mark inferred constraints with is_inferred=True."
  - "NEVER fabricate coefficients not present in source data."
  - "Set confidence scores honestly."
  - Anti-hallucination guardrail: "If unsure, add to ambiguities list rather than guessing."

#### `repair_bundle(bundle_json: str, validation_errors: list[dict]) -> ConstraintBundle`

- **Model:** Gemini 3.1 Pro
- **Input:** Failed constraint_bundle.json + validation error list
- **Output schema:** `ConstraintBundle`
- **System prompt:** "Fix the following validation errors WITHOUT fabricating new data. Only restructure, correct types, or remove invalid entries."
- **Max retries:** 2 (enforced by caller, not this function)

### 7.2 Configuration

```python
FLASH_MODEL = "gemini-3-flash"
PRO_MODEL = "gemini-3.1-pro"
```

- API key via `GEMINI_API_KEY` env var
- Temperature: 0.1 for extraction, 0.0 for repair
- `response_mime_type = "application/json"`
- `response_schema` = Pydantic model's `.model_json_schema()`

---

## 8. File: `scripts/parsers/pdf_parser.py`

**Purpose:** Extract text + tables from PDF files using pdfplumber.

### 8.1 Interface

```python
def parse_pdf(file_path: str) -> ParsedDocument:
    """Returns structured text + tables from PDF."""
```

### 8.2 `ParsedDocument` Schema

```python
class ParsedDocument(BaseModel):
    filename: str
    doc_type: str
    pages: int
    full_text: str              # All text concatenated
    tables: list[ExtractedTable]
    sections: list[TextSection]  # Heading-based chunking
```

```python
class ExtractedTable(BaseModel):
    page: int
    headers: list[str]
    rows: list[list[str]]

class TextSection(BaseModel):
    heading: str | None
    content: str
    page_start: int
    page_end: int
```

### 8.3 Logic

1. Open PDF with `pdfplumber.open(file_path)`
2. For each page: extract text, extract tables
3. Chunk text by detecting heading patterns (ALL CAPS lines, numbered sections)
4. Return `ParsedDocument`

---

## 9. File: `scripts/parsers/tabular_parser.py`

**Purpose:** Parse XLSX (multi-tab) and CSV files into structured data.

### 9.1 Interface

```python
def parse_tabular(file_path: str) -> ParsedDocument:
    """Returns structured tabular data from XLSX/CSV."""
```

### 9.2 Logic

**For XLSX:**
1. `pd.ExcelFile(file_path, engine='openpyxl')`
2. For each sheet: `pd.read_excel(xls, sheet_name=name)`
3. Detect header row (first row with > 50% non-null string values)
4. Extract column names, dtypes, value ranges, units (from header suffixes like "(kg)" or "(tons)")
5. Convert to `ExtractedTable` per sheet

**For CSV:**
1. `pd.read_csv(file_path)` with encoding detection
2. Same header/unit detection logic

### 9.3 Unit Detection Heuristic

Scan column headers for patterns:
- `column_name (unit)` → extract unit
- `column_name [unit]` → extract unit
- `column_name_unit` → extract unit from suffix after last underscore

Return unit annotations in the `ParsedDocument.metadata` field.

---

## 10. File: `scripts/parsers/text_parser.py`

**Purpose:** Parse plain text / DOCX natural language instructions.

### 10.1 Interface

```python
def parse_text(file_path: str) -> ParsedDocument:
    """Returns parsed text content."""
```

For `.txt`: direct read. For `.docx`: use `python-docx` (add to requirements if needed, or extract via zipfile + XML parsing for minimal deps).

---

## 11. OpenClaw Skill Definition

**Path:** `~/opt-workspace/skills/constraint-intake-hybrid/SKILL.md`

### 11.1 Frontmatter

```yaml
---
name: constraint_intake_hybrid
description: >
  Watch folders and Slack threads for enterprise optimization data packages.
  Extract constraints via Gemini, validate deterministically, compile PuLP
  artifacts, submit to Quantagonia HybridSolver with human approval gating.
version: 0.1.0
metadata:
  openclaw:
    requires:
      env: [QUANTAGONIA_API_KEY, GEMINI_API_KEY, SLACK_BOT_TOKEN]
      bins: [python3]
---
```

### 11.2 Skill Body (Behavioral Instructions)

The SKILL.md body instructs the agent on the complete workflow:

```markdown
# Constraint Intake Hybrid

## Trigger Conditions
- Cron event: watch_inbox.py detected new request
- Slack message in #decisionai-intake with file attachments

## Workflow

### Phase A: Intake & Classification
1. Run: `exec python3 scripts/watch_inbox.py ~/opt-workspace` (if cron-triggered)
2. OR: Download Slack attachments to staging/<request_id>/
3. Run: `exec python3 scripts/gemini_client.py classify <run_dir>` (Gemini Flash)
4. Post intake receipt to Slack via slack_notify.py

### Phase B: Extraction
5. Fan out parsers (subagent lane, concurrency 4):
   - PDF files → pdf_parser.py
   - XLSX/CSV files → tabular_parser.py
   - TXT/DOCX files → text_parser.py
6. Load MEMORY.md for client terminology
7. Call gemini_client.py extract with all parsed documents + memory context
8. Write constraint_bundle.json to runs/<request_id>/

### Phase C: Validation & Repair
9. Run: `exec python3 scripts/validate_bundle.py <run_dir>`
10. IF validation fails AND repair_attempts < 2:
    - Call gemini_client.py repair with errors
    - Overwrite constraint_bundle.json
    - GOTO step 9
11. IF validation fails after 2 repairs:
    - Post error + ambiguities to Slack
    - Write questions.md
    - HALT (await human input)
12. Post extraction preview to Slack (facts/inferences/ambiguities)

### Phase D: Compilation & Approval
13. Run: `exec python3 scripts/emit_pulp_artifacts.py <run_dir> --lp`
14. Post artifact summary to Slack
15. WAIT for APPROVE signal (Slack reply OR folder move to approved/)

### Phase E: Submission & Monitoring
16. Run: `exec python3 scripts/submit_hybridsolver.py <run_dir> --time-limit 3600 --rel-gap 0.01`
17. Stream progress events to Slack thread
18. On completion: post final summary
19. Write MEMORY.md entry with any learned terminology/conventions
```

---

## 12. OpenClaw Configuration Additions

**File:** `~/.openclaw/openclaw.json`

### 12.1 Exec Tool Config

```json5
{
  tools: {
    exec: {
      security: "allowlist",
      safeBins: ["/usr/bin/python3"],
      safeBinTrustedDirs: ["/usr/bin", "/usr/local/bin"],
      approvalRunningNoticeMs: 10000,
      // All Python scripts run via: python3 scripts/<name>.py <args>
      // The allowlist trusts /usr/bin/python3 only
    }
  }
}
```

### 12.2 Cron Configuration

```json5
{
  cron: {
    inbox_check: {
      every: "0 6 * * *",
      session: "main",
      payload: {
        kind: "agentTurn",
        message: "Run watch_inbox.py and process any new requests found."
      }
    }
  }
}
```

### 12.3 Agent Configuration

```json5
{
  agents: {
    defaults: {
      workspace: "~/opt-workspace",
      model: {
        primary: "google/gemini-3-flash",
        fallbacks: ["google/gemini-3.1-pro", "anthropic/claude-sonnet-4-6"]
      },
      skills: ["constraint_intake_hybrid"]
    }
  }
}
```

### 12.4 Slack Channel Configuration

```json5
{
  channels: {
    slack: {
      allowFrom: ["U_PLANNER_ID_1", "U_PLANNER_ID_2"],
      channel: "decisionai-intake"
    }
  }
}
```

### 12.5 Messages Queue

```json5
{
  messages: {
    queue: {
      mode: "collect",
      debounceMs: 2000
    }
  }
}
```

---

## 13. Directory Layout (Complete)

```
~/opt-workspace/
├── skills/
│   └── constraint-intake-hybrid/
│       └── SKILL.md
├── scripts/
│   ├── schemas.py
│   ├── validate_bundle.py
│   ├── emit_pulp_artifacts.py
│   ├── submit_hybridsolver.py
│   ├── watch_inbox.py
│   ├── slack_notify.py
│   ├── gemini_client.py
│   └── parsers/
│       ├── __init__.py
│       ├── pdf_parser.py
│       ├── tabular_parser.py
│       └── text_parser.py
├── clients/
│   └── <account>/
│       ├── inbox/
│       ├── staging/
│       ├── approved/
│       ├── runs/
│       │   └── <request_id>/
│       │       ├── source/
│       │       ├── constraint_bundle.json
│       │       ├── validation_report.json
│       │       ├── questions.md
│       │       ├── model.py
│       │       ├── artifacts/
│       │       │   ├── problem.mps
│       │       │   ├── problem.mps.gz
│       │       │   ├── problem.lp
│       │       │   └── problem.qubo (conditional)
│       │       ├── submission.json
│       │       └── slack_thread.json
│       └── outbox/
├── MEMORY.md
├── memory/
│   └── YYYY-MM-DD.md
└── requirements.txt
```

---

## 14. Integration Contracts

### 14.1 Script → Script Data Flow

```
watch_inbox.py
    → stdout: {event: "new_request", files: [...]}
    → side-effect: moves folder to staging/

gemini_client.py classify
    → input: file inventory JSON
    → output: FileClassification JSON

parsers/*.py
    → input: file path
    → output: ParsedDocument JSON

gemini_client.py extract
    → input: list[ParsedDocument] + MEMORY.md text
    → output: constraint_bundle.json (written to run_dir)

validate_bundle.py
    → input: constraint_bundle.json
    → output: validation_report.json
    → side-effect: rewrites constraint_bundle.json if normalization applied

emit_pulp_artifacts.py
    → input: constraint_bundle.json (validated)
    → output: model.py, problem.mps, problem.mps.gz, [problem.lp], [problem.qubo]

submit_hybridsolver.py
    → input: problem.mps.gz
    → output: submission.json
    → stdout: streaming progress JSON

slack_notify.py
    → input: run_dir + action
    → side-effect: posts to Slack, writes/reads slack_thread.json
```

### 14.2 OpenClaw exec Calls (Exact Commands)

| Step | Command | Approval Required |
|------|---------|-------------------|
| Inbox scan | `python3 scripts/watch_inbox.py ~/opt-workspace` | No (safeBin) |
| Validation | `python3 scripts/validate_bundle.py ~/opt-workspace/clients/<acct>/runs/<id>` | No (safeBin) |
| Compilation | `python3 scripts/emit_pulp_artifacts.py ~/opt-workspace/clients/<acct>/runs/<id> --lp` | No (safeBin) |
| Submission | `python3 scripts/submit_hybridsolver.py ~/opt-workspace/clients/<acct>/runs/<id> --time-limit 3600` | No (safeBin) |
| Slack notify | `python3 scripts/slack_notify.py <action> ~/opt-workspace/clients/<acct>/runs/<id>` | No (safeBin) |

All commands use `/usr/bin/python3` which is in `safeBins`. No approval prompts needed.

---

## 15. Environment Variables (Codespaces Secrets)

| Variable | Source | Used By |
|----------|--------|---------|
| `QUANTAGONIA_API_KEY` | platform.quantagonia.com | submit_hybridsolver.py |
| `GEMINI_API_KEY` | Google AI Studio | gemini_client.py |
| `SLACK_BOT_TOKEN` | Slack App OAuth | slack_notify.py |
| `SLACK_CHANNEL` | Config (default: `decisionai-intake`) | slack_notify.py |
| `WORKSPACE_ROOT` | Config (default: `~/opt-workspace`) | watch_inbox.py |

---

## 16. Testing Strategy (Phase 1 Only)

### 16.1 Unit Tests

| File | Test Coverage |
|------|--------------|
| `tests/test_schemas.py` | Pydantic validation: valid bundles pass, invalid fail with correct error codes |
| `tests/test_validate_bundle.py` | Unit normalization, impossible values, duplicate detection, referential integrity |
| `tests/test_emit_artifacts.py` | MPS file validity (parse back with PuLP `readMPS`), variable/constraint counts match |
| `tests/test_parsers.py` | PDF extraction, XLSX multi-tab parsing, unit detection from headers |

### 16.2 Integration Test (MVP Acceptance)

Single end-to-end test using the fixture from ULTIMATE_PRD.md §6:
- 1 PDF (union labor contract)
- 1 XLSX (4 tabs, quarterly demand)
- 1 CSV (capacity, mixed units kg/tons)
- 1 Slack message (natural language constraints)

Pass criteria: all 10 acceptance items from ULTIMATE_PRD.md §6.

### 16.3 Test Fixtures Location

```
~/opt-workspace/tests/fixtures/
├── mvp_request/
│   ├── union_contract_sample.pdf
│   ├── demand_forecast_q2.xlsx
│   ├── capacity_limits.csv
│   └── README.txt
└── expected_outputs/
    ├── constraint_bundle.json
    ├── validation_report.json
    └── problem.mps
```

---

## 17. Anti-Replication Verification Checklist

For the execution agent to verify during implementation:

- [ ] No `import scipy.optimize` or `from ortools` anywhere
- [ ] No Simplex, Branch-and-Bound, or LP/MILP solving logic
- [ ] `emit_pulp_artifacts.py` only calls `writeMPS`/`writeLP`, never `prob.solve()`
- [ ] `submit_hybridsolver.py` only uses `HybridSolver.submit()`, never `HybridSolver.solve()` (blocking)
- [ ] `QUANTAGONIA_API_KEY` never appears in any output file or stdout
- [ ] All mathematical formulation comes from source documents via LLM extraction, never fabricated
- [ ] The system declares "formulation" not "optimization" in all user-facing text

---

*End of Phase 1 Spec. Phase 2 (advanced repair loops, multi-model consensus) and Phase 3 (production hardening, multi-tenant) are out of scope.*
