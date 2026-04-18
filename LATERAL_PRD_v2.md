# Lateral PRD v2: Watch-Folder Daemon Sidecar

## The Concept

This version solves the same bottleneck as the main PRD and nothing else: turning messy enterprise business rules into strict mathematical artifacts that the Strangeworks/Quantagonia HybridSolver can actually consume. The lateral change is that the intake happens through a watched filesystem rather than a conversation surface.

The user experience is operationally conservative on purpose. Many enterprises already have shared-drive habits for inbound vendor contracts, labor agreements, route updates, and plant-level planning spreadsheets. Instead of asking those teams to begin in Slack, the sidecar watches a mounted intake folder. Users drop files into `inbox/`, and OpenClaw turns that passive file drop into an active extraction and compilation workflow.

This remains consistent with `PRD.MD`, which argues that the sidecar needs real filesystem work, terminal execution, and durable memory rather than a thin API wrapper. It also matches `CONTEXT.md`, which identifies the pre-core bottleneck as translation from fragmented PDFs, spreadsheets, and other unstructured assets into solver-ready structures. This version is for organizations where the native environment is not chat but file exchange.

## The Strategic Hook

Dirk Zechiel would prefer this version when the goal is adoption inside traditional enterprise environments that still operate through shared folders, exports, and scheduled batch handoffs. `CONTEXT.md` makes clear that his priority is not academic elegance but broad accessibility. A watch-folder sidecar is a high-leverage accessibility tactic because it removes the need to retrain operators into a new app. The magic moment becomes: drop files into a folder and receive back a validated solver package.

Philipp Hannemann should also like this approach because it uses the OpenClaw primitives he publicly maps to real execution systems: agent workflows, file manipulation, lane queues, and memory. It demonstrates that OpenClaw is not merely a chatbot framework. It is an orchestration runtime that can live beside existing enterprise data flows and bridge them into a deterministic solver boundary.

There is also explicit appeal to Matthias Wulff and Thomas Kleinert. Wulff gets a more controlled pre-core environment than chat, with strong deterministic folder conventions, manifest files, and validation reports. Kleinert gets a narrow impedance-matching layer that still ends in `.mps`, `.lp`, or `.qubo` artifacts, never in vague agentic "reasoning" output.

## The Agent Architecture

### End-to-end data flow

1. A user or upstream system drops files into `clients/<account>/inbox/<request_id>/`.
2. OpenClaw detects the new folder via a file watcher or heartbeat-driven polling loop.
3. The watcher creates a session keyed to the folder path and enqueues the request on lane `session:<request_id>` with queue mode `followup`.
4. Gemini 3 Flash performs rapid inventory:
   - identify file types
   - detect likely source roles such as policy, rates, capacities, or demand inputs
   - flag missing companion files
5. OpenClaw spawns subagents to inspect files in parallel while preserving a single owning session lane:
   - contract parser subagent
   - spreadsheet parser subagent
   - metadata synthesis subagent
6. Gemini 3 Pro merges all extracted evidence into a canonical constraint manifest.
7. `exec` runs deterministic scripts to:
   - normalize and stage parsed data
   - validate schema and ranges
   - compile a PuLP-based model emitter
   - write `.mps` as the primary artifact
8. OpenClaw writes a human-readable report into `outbox/` and a machine-readable manifest into `runs/`.
9. Submission to HybridSolver occurs only after an approval signal, such as moving the request folder from `staging/` to `approved/` or writing `approved: true` into a manifest file.
10. After submit, OpenClaw updates the run report with `progress`, `status`, and `logs`.

### OpenClaw primitives that must be explicit

- **Lane Queues:** Each watched folder request gets a serialized session lane so the same files are never being rewritten by overlapping runs. This follows the OpenClaw queue guarantee that per-session runs remain single-writer while other sessions can proceed in parallel.
- **`exec`:** `exec` handles parser helpers, validators, artifact emission, and solver submission. Keep allowlisted binaries and use pinned paths only.
- **`MEMORY.md`:** Store durable file conventions:
  - which spreadsheet tabs usually map to which entity class
  - account-specific naming conventions
  - approved defaults for absent metadata
  - recurring rejection reasons
- **Daily notes:** Store run-level observations such as "warehouse spreadsheet swapped unit columns this week" or "vendor contract used a non-standard overtime code."

### Gemini model split

- **Gemini 3 Flash**
  - file inventory
  - parser routing
  - missing-file detection
  - concise status report generation
- **Gemini 3 Pro**
  - cross-file reconciliation
  - semantic extraction from long contracts
  - final structured bundle generation
  - repair after validator failure

### HybridSolver boundary

This version must keep the same hard boundary as the main PRD and current docs:

- default artifact is `.mps`
- `.lp` is optional for review
- `.qubo` is conditional, not assumed
- submit using the documented async interface
- the sidecar prepares and submits; HybridSolver computes

## The Native Environment UI Spec

The user interacts through a filesystem contract rather than a chat UI.

### Required folder layout

- `clients/<account>/inbox/`
- `clients/<account>/staging/`
- `clients/<account>/approved/`
- `clients/<account>/runs/`
- `clients/<account>/outbox/`
- `clients/<account>/rejected/`

### Required interaction pattern

1. User creates `inbox/<request_id>/`.
2. User drops all messy source files into that folder.
3. Agent moves or mirrors the folder into `staging/<request_id>/`.
4. Agent writes:
   - `intake_summary.md`
   - `constraint_bundle.json`
   - `validation_report.json`
   - `questions.md` if ambiguity remains
5. Human reviewer approves by:
   - moving the folder into `approved/`, or
   - editing a manifest field
6. Agent compiles artifacts, submits to HybridSolver, and writes result files into `runs/` and `outbox/`.

### Exact UX requirements

- Folder contents must be immutable once the request enters `staging/`; revisions create a new request id.
- The agent must never silently overwrite a source file.
- Human-readable reports must live beside machine-readable manifests.
- Approval state must be explicit and file-based, not inferred from timing.
- Output package must contain:
  - extracted constraints
  - unresolved assumptions
  - artifact list
  - submission metadata
  - current solver status

## Phase 1 Execution Spec

Build the MVP in GitHub Codespaces using a local folder tree inside the repo.

### Step 1: Prepare the environment

- Install OpenClaw and Python dependencies.
- Install `quantagonia>=0.15.0`, `pulp>=3.3.0`, `pandas>=2.2.0`, `pydantic`, and any OCR helper actually needed.
- Set `QUANTAGONIA_API_KEY` as a secret.

### Step 2: Create the watch-folder skill

- Add `skills/constraint-intake-folder/SKILL.md`.
- The skill must define:
  - watcher behavior
  - folder transitions
  - intermediate manifest conventions
  - approval signal semantics
  - memory write rules

### Step 3: Add deterministic scripts

- `scripts/watch_inbox.py`
  - detect new request folders
  - emit stable request ids
- `scripts/validate_constraint_bundle.py`
- `scripts/emit_pulp_artifacts.py`
- `scripts/submit_hybridsolver.py`
- `scripts/write_outbox_report.py`

### Step 4: Define the file contract

For each request, write:

- `staging/<request_id>/constraint_bundle.json`
- `staging/<request_id>/validation_report.json`
- `staging/<request_id>/questions.md`
- `runs/<request_id>/model.py`
- `runs/<request_id>/artifacts/problem.mps`
- `runs/<request_id>/submission.json`
- `outbox/<request_id>/summary.md`

### Step 5: Wire OpenClaw execution

- Use a watcher loop or heartbeat-triggered agent turn.
- Keep queue mode at `followup` so revised events queue cleanly.
- Allowlist only the required binaries for `exec`.
- Persist client-specific folder knowledge into `MEMORY.md`.

### Step 6: Define the MVP acceptance test

Use one staged folder with:
- one PDF contract
- one spreadsheet of capacities
- one CSV of costs

The MVP passes if:
- OpenClaw detects the folder automatically
- the agent writes a valid constraint bundle
- the validator rejects impossible values deterministically
- the emitter produces a valid `.mps`
- the request can be explicitly approved and then submitted

## Guardrails and Anti-Replication

- The watched-folder daemon is still only a formulation sidecar.
- It may not auto-infer missing constraints beyond documented defaults stored in `MEMORY.md`.
- It must fail closed when required files are missing.
- It may not submit directly from `inbox/`; every request must cross an approval boundary.
- It may not claim support for QP, MIQP, or NLP because the HybridSolver boundary does not support that.

## Why This Version Exists Beside the Core PRD

The main PRD proves that the sidecar needs an agent framework with a filesystem, shell, queue, and durable memory. This lateral version asks what happens when the user's native environment is a shared drive instead of a collaboration thread. The answer is a lower-friction delivery model for conservative enterprises: same OpenClaw orchestration, same Gemini stack, same HybridSolver boundary, but an intake surface that fits existing operational habits without inventing a new product.
