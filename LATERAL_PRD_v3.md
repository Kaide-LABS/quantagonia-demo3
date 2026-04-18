# Lateral PRD v3: Interactive Terminal Wizard Sidecar

## The Concept

This version keeps the same pre-core bottleneck and the same anti-replication boundary, but changes the delivery model into a guided terminal workflow. It is designed for analysts, solutions engineers, and technical buyers who want a highly inspectable path from messy business rules to solver-ready artifacts.

Instead of waiting on Slack or a daemonized folder watcher, the user starts an explicit session in GitHub Codespaces. OpenClaw then behaves like a guided optimization-intake operator. The agent walks the user through ingestion, extraction, reconciliation, validation, compilation, and submission in discrete terminal steps. This preserves the same core logic from `PRD.MD`: OpenClaw uses `exec`, file writes, and memory to generate solver-native artifacts. The difference is that trust is built through an interactive, checkpointed wizard rather than background automation.

This is still tightly inside scope. The agent does not solve the optimization problem. It only helps the user turn fuzzy language, spreadsheets, and contracts into a valid formulation package that HybridSolver can solve.

## The Strategic Hook

Philipp Hannemann is the clearest founder fit for this version. `CONTEXT.md` frames him as the AI-native orchestrator who understands that LLMs are poor math solvers but strong semantic routers. A terminal wizard is the purest demonstration of that principle. Every stage is visible. Every Gemini action is constrained. Every deterministic validation pass is explicit. This feels like an OpenClaw-native engineering tool rather than a black-box assistant.

Dirk Zechiel also has a reason to prefer this version for pilots and technical validation. `CONTEXT.md` says he wants broad accessibility, but he also wants to benchmark against legacy solver stacks. A Codespaces-native wizard gives a crisp benchmark story for early customer pilots: "Here is the exact flow from messy business rules to `.mps` submission, without hiring a PhD-level OR engineer to hand-code the input."

This version also strongly satisfies Wulff and Kleinert. Wulff gets maximum auditability and explicit checkpoints. Kleinert gets a rigid formulation boundary where nothing reaches HybridSolver until the user has reviewed the extracted structure and the deterministic validator has passed.

## The Agent Architecture

### End-to-end data flow

1. User starts a session from the terminal, e.g. `opt-sidecar start`.
2. OpenClaw opens a dedicated session lane keyed to the local wizard session and uses queue mode `steer` so user corrections can alter the active run at safe tool boundaries.
3. Gemini 3 Flash handles immediate prompt-response interactions:
   - classify incoming files
   - ask small clarification questions
   - summarize the current checkpoint
4. OpenClaw writes all session state into `runs/<session_id>/`.
5. Gemini 3 Pro performs the heavier synthesis:
   - unify constraints across source documents
   - draft the canonical structured bundle
   - map business language to explicit decision variables and constraint groups
6. `exec` runs deterministic validators and model emitters after each approval checkpoint.
7. The user explicitly approves the formulation draft before compile.
8. The user explicitly approves the compiled artifact before submit.
9. HybridSolver submission uses the async `submit -> progress -> status -> logs` loop and streams status back into the terminal.

### Wizard phases

1. **Ingest**
   - select files
   - label source roles if known
2. **Extract**
   - show candidate entities, variables, and hard constraints
3. **Reconcile**
   - surface conflicts and missing information
   - allow user edits and confirmations
4. **Compile**
   - run validation
   - emit `.mps`
   - optionally emit `.lp`
   - emit `.qubo` only when explicitly flagged and binary-safe
5. **Submit**
   - show final package summary
   - submit to HybridSolver on approval

### OpenClaw primitives that must be explicit

- **Lane Queues:** Use one serialized session lane per active wizard. This prevents concurrent rewrite of the same session files while still allowing separate users or separate runs in parallel.
- **`exec`:** Use `exec` for:
  - parser previews
  - validators
  - PuLP artifact emission
  - HybridSolver submission and polling
- **`MEMORY.md`:** Store durable preferences confirmed by the user:
  - preferred naming schemes
  - accepted default units
  - recurring entity mappings
  - account-specific modeling conventions
- **Daily notes:** Record session-specific anomalies and repair outcomes.
- **JSONL transcripts:** Preserve the step-by-step audit trail for every wizard turn.

### Gemini model split

- **Gemini 3 Flash**
  - short interactive prompts
  - triage
  - checkpoint summaries
  - local clarification turns
- **Gemini 3 Pro**
  - final extraction
  - cross-document synthesis
  - repair after validation failure
  - final formulation draft

### HybridSolver boundary

As in the main PRD and the current external docs:

- solver-supported outputs remain MILP/LP/QUBO only
- no QP, MIQP, or NLP claims
- the wizard does not optimize anything itself
- the wizard compiles and submits only

## The Native Environment UI Spec

The user interacts through a terminal inside GitHub Codespaces.

### Required CLI entrypoints

- `opt-sidecar start`
- `opt-sidecar resume <session_id>`
- `opt-sidecar status <session_id>`
- `opt-sidecar submit <session_id>`

### Required interaction pattern

At each step, the terminal must show:
- current phase
- files currently in scope
- extracted facts
- inferred structure
- unresolved assumptions
- next required user decision

### Exact UX requirements

- The wizard must be resumable after disconnect.
- The wizard must never hide validator errors.
- The wizard must present diffs when the extracted structure changes after user edits.
- Every approval boundary must be explicit:
  - approve extraction
  - approve compiled artifact
  - approve submission
- Final terminal output must include:
  - request summary
  - artifact paths
  - solver job id
  - current status
  - gap/time data if available

### Session-state requirements

Persist a checkpoint file such as `runs/<session_id>/checkpoint.json` with:
- current phase
- accepted entities
- accepted assumptions
- unresolved questions
- artifact paths
- submission metadata

## Phase 1 Execution Spec

Build the MVP entirely inside GitHub Codespaces.

### Step 1: Prepare the environment

- Install OpenClaw.
- Install Python packages: `quantagonia>=0.15.0`, `pulp>=3.3.0`, `pandas>=2.2.0`, `pydantic`.
- Set `QUANTAGONIA_API_KEY` in the Codespaces secrets store.

### Step 2: Create the wizard skill

- Add `skills/constraint-intake-wizard/SKILL.md`.
- The skill must define:
  - phase order
  - what the model is allowed to infer
  - which approvals are mandatory
  - memory promotion rules

### Step 3: Add CLI wrappers

- `scripts/wizard_start.py`
- `scripts/wizard_resume.py`
- `scripts/validate_constraint_bundle.py`
- `scripts/emit_pulp_artifacts.py`
- `scripts/submit_hybridsolver.py`

### Step 4: Define the run layout

- `runs/<session_id>/source/`
- `runs/<session_id>/constraint_bundle.json`
- `runs/<session_id>/validation_report.json`
- `runs/<session_id>/checkpoint.json`
- `runs/<session_id>/model.py`
- `runs/<session_id>/artifacts/`
- `runs/<session_id>/submission.json`

### Step 5: Wire OpenClaw behavior

- Queue mode `steer`
- safe binary allowlist for Python and HybridSolver CLI only
- write confirmed durable preferences into `MEMORY.md`
- write transient notes into `memory/YYYY-MM-DD.md`

### Step 6: Define the MVP acceptance test

Use one synthetic customer brief containing:
- one natural-language requirements memo
- one policy PDF
- one spreadsheet of capacities and costs

The MVP passes if:
- a user can start and complete the wizard without hand-editing solver code
- the agent produces a valid `.mps`
- the checkpoint file allows resume mid-run
- HybridSolver submission can be triggered explicitly after review

## Guardrails and Anti-Replication

- The terminal wizard may guide, extract, validate, compile, and submit.
- It may not silently infer objective functions or coefficients that were never provided or approved.
- It may not skip approval checkpoints in the name of convenience.
- It must fail closed when the problem is outside MILP/LP/QUBO scope.
- It must surface uncertainty to the user rather than bury it in logs.

## Why This Version Exists Beside the Core PRD

The main PRD optimizes for an autonomous optimization-engineering sidecar. This lateral version optimizes for trust-building during implementation, presales, and technical onboarding. It is the strongest shape when the buyer wants to inspect every translation step before letting the system run in the background. Same bottleneck, same OpenClaw core, same Gemini stack, same HybridSolver boundary, but a different UX contract: explicit checkpoints instead of silent orchestration.
