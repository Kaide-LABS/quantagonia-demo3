# Lateral PRD v1: Slack Thread Intake Sidecar

## The Concept

This version keeps the core sidecar exactly where the main PRD places it: between messy enterprise reality and the strict MILP/QUBO artifacts required by the Strangeworks/Quantagonia HybridSolver. The lateral change is the intake surface. Instead of starting from a watched folder of quarterly data packages, this version starts from a dedicated Slack channel and one request thread per optimization task.

The user experience is intentionally conversational. A planner drops a union contract PDF, a vendor rate sheet, screenshots of policy tables, and a messy natural-language request into a Slack thread such as: "Need the April workforce allocation constraints converted for the new warehouse model." OpenClaw remains the core orchestrator. It receives the Slack event, locks the request to a per-session lane, fans out limited parsing work to subagents, writes a canonical constraint bundle, and then uses `exec` to run deterministic validators and a PuLP-based artifact emitter. The sidecar never solves the math. It only turns the thread into a clean formulation package and submits it to HybridSolver.

This approach is grounded in the repo baseline. `PRD.MD` already frames the product as "a HybridSolver-native optimization engineer you talk to in Slack" and makes OpenClaw's filesystem, lane queue, `exec`, and `MEMORY.md` primitives load-bearing. `CONTEXT.md` also identifies the pre-core bottleneck as manual translation of constraints from PDFs, spreadsheets, Slack, and email into solver-safe structures. This variant narrows that bottleneck to the highest-visibility native environment: the collaboration thread where operations teams already negotiate messy rules.

## The Strategic Hook

Dirk Zechiel is the primary commercial reason to prefer this version first. `CONTEXT.md` makes two themes explicit: he wants to "maximize the visibility and importance of Operations Research in public" and he wants "Democratization of Planning" rather than another hidden backend optimization engine. A Slack-thread sidecar gives him the cleanest magic moment. A planner posts a messy thread; minutes later the thread shows a validated constraint summary, generated `.mps` artifact, and a live HybridSolver job id. The solver remains mathematically rigorous, but the experience becomes socially legible.

Philipp Hannemann is the technical reason. `CONTEXT.md` describes him as deeply embedded in the OpenClaw ecosystem and explicitly interested in the boundary between LLMs and deterministic mathematics. This version speaks his native language: lane queues, session memory, subagent routing, and native-environment agent UX. It demonstrates that Gemini does not pretend to solve the optimization problem. Gemini routes, extracts, reconciles, and drafts structure; HybridSolver does the MILP/QUBO work.

There is also a practical founder-fit point for Thomas Kleinert and Matthias Wulff. Kleinert gets a hard anti-replication guarantee because the thread ends in strict schema validation and artifact compilation, not fuzzy natural-language "optimization." Wulff gets an auditable JSONL transcript and deterministic validation loop before any solver submission. OpenClaw's append-only session records and `MEMORY.md` provide the audit trail, while the HybridSolver boundary stays narrow and defendable.

## The Agent Architecture

### End-to-end data flow

1. A user posts a request in a dedicated Slack channel and all follow-up assets live in one thread.
2. OpenClaw receives the inbound Slack event through the gateway bridge and creates or resumes a session keyed to that thread.
3. The request is enqueued on lane `session:<thread_key>` with queue mode `collect`, so follow-up messages collapse into one coherent next turn instead of racing the active extraction run.
4. Gemini 3 Flash performs first-pass triage:
   - classify each attachment
   - detect whether the thread contains policy text, numeric tables, or ambiguous goals
   - extract missing-information questions without attempting formulation
5. OpenClaw spawns bounded subagents on the `subagent` lane to inspect individual attachments in parallel:
   - one subagent for PDFs and contracts
   - one for spreadsheets and CSVs
   - one for freeform thread text and prior thread context
6. Gemini 3 Pro receives the merged evidence and drafts a canonical constraint package:
   - decision variables
   - entities and indices
   - bounds
   - objective intent if explicitly stated
   - hard constraints
   - unresolved ambiguities
7. OpenClaw writes a structured intermediate manifest such as `runs/<request_id>/constraint_bundle.json`.
8. `exec` calls a deterministic Python validator:
   - Pydantic or equivalent schema checks
   - unit normalization
   - impossible-value rejection
   - duplicate identifier detection
9. If validation fails, Gemini 3 Pro gets the validator output and must repair structure, not improvise math.
10. Once valid, `exec` runs the PuLP emitter to generate:
   - primary `.mps` artifact
   - optional `.lp` artifact for human inspection
   - optional `.qubo` only if the formulation is binary-safe and explicitly enabled
11. OpenClaw submits through the direct Quantagonia SDK or CLI using the documented async pattern: `submit -> progress -> status -> logs`.
12. Slack thread updates are posted at major boundaries:
   - extraction complete
   - validation pass/fail
   - artifact compiled
   - solver job submitted
   - solver status updates and billed time

### OpenClaw primitives that must be explicit

- **Lane Queues:** Use per-thread session lanes with concurrency 1. This mirrors the queue semantics documented in OpenClaw's `queue.md`, where each session is serialized to avoid collisions on session files, logs, and workspace artifacts.
- **`exec`:** Use `exec` for validators, OCR helpers if needed, PuLP compilation, and HybridSolver submission. Keep `security=allowlist` and bind exact binary paths, consistent with the OpenClaw exec model and the `PRD.MD` emphasis on pinned executable paths and approval control.
- **`MEMORY.md`:** Store durable client semantics only:
  - approved terminology mappings
  - recurring business-rule aliases
  - known unit conventions
  - client-specific forbidden assumptions
- **Daily memory notes:** Store per-run anomalies:
  - which document drifted
  - which validation rule fired
  - which constraint patterns were ambiguous
- **JSONL session transcripts:** Preserve the factual audit trail of what the agent extracted from which message or attachment. Never echo `QUANTAGONIA_API_KEY` into stdout because OpenClaw persists exec output before redaction.

### Gemini model split

- **Gemini 3 Flash**
  - message triage
  - attachment routing
  - ambiguity detection
  - quick summarization back into Slack
- **Gemini 3 Pro**
  - canonical constraint extraction
  - cross-document reconciliation
  - repair after validator errors
  - final packaging of the formulation draft before compile

### HybridSolver boundary

This version must repeat the anti-replication rule plainly: the sidecar never performs Branch-and-Bound, Simplex, or any solver heuristic itself. It only emits solver-native representations and submits them. The accepted formats and solver boundary must match the current docs:

- MPS is the default artifact
- LP is optional and mainly for review
- QUBO is conditional and only valid when the problem can be expressed as such
- Async status must use `submit`, `progress`, `status`, and `logs`

## The Native Environment UI Spec

The user interacts entirely through Slack.

### Channel design

- One dedicated channel, e.g. `#decisionai-intake`
- One thread per optimization request
- Thread opener must contain:
  - business objective
  - business unit or site
  - planning horizon
  - attached evidence, if any

### Required interaction pattern

1. User posts a request and attachments.
2. Agent replies with a thread-local intake receipt.
3. Agent posts an extraction preview with:
   - detected entities
   - candidate variables
   - detected hard constraints
   - unresolved ambiguities
4. User confirms or edits those items in-thread.
5. Agent posts validation result.
6. Agent posts artifact compilation result and asks for final submit approval.
7. After approval, agent posts the HybridSolver job id and async progress updates.

### Exact UX requirements

- Every request must remain thread-local; no cross-thread blending.
- Every preview must separate:
  - extracted facts
  - inferred structure
  - unresolved assumptions
- Every validation error must be human-readable, not raw tracebacks.
- Final thread output must include:
  - constraint summary
  - validation outcome
  - artifact filenames
  - HybridSolver job id
  - current status
  - relative gap if available
  - billed minutes if available

### Non-goals

- No dashboard product
- No new planning workspace
- No mathematical explanation engine
- No solver replacement logic

## Phase 1 Execution Spec

Build the MVP in GitHub Codespaces with the direct Quantagonia SDK path as the default integration.

### Step 1: Bootstrap the Codespaces workspace

- Install Python 3.11 in the Codespace.
- Install `quantagonia>=0.15.0`, `pulp>=3.3.0`, `pandas>=2.2.0`, and `pydantic`.
- Install OpenClaw and configure a local agent workspace under `.openclaw/` or project-local equivalent.
- Set `QUANTAGONIA_API_KEY` as an environment secret. Never print it.

### Step 2: Create the Slack intake skill

- Add `skills/constraint-intake-slack/SKILL.md`.
- The skill must define:
  - when to treat a thread as a new extraction run
  - how to write intermediate manifests
  - which validator and emitter scripts to call
  - what belongs in `MEMORY.md` versus daily notes

### Step 3: Add deterministic scripts

- `scripts/validate_constraint_bundle.py`
  - schema checks
  - unit normalization
  - missing-id detection
  - impossible-value rejection
- `scripts/emit_pulp_artifacts.py`
  - convert validated bundle into PuLP model code
  - emit `.mps`
  - emit `.lp` optionally
  - emit `.qubo` only behind an explicit flag
- `scripts/submit_hybridsolver.py`
  - async submit
  - progress polling
  - status and logs retrieval
  - machine-readable output for Slack updates

### Step 4: Define run-state layout

- `runs/<request_id>/source/`
- `runs/<request_id>/constraint_bundle.json`
- `runs/<request_id>/validation_report.json`
- `runs/<request_id>/model.py`
- `runs/<request_id>/artifacts/`
- `runs/<request_id>/submission.json`

### Step 5: Wire the OpenClaw pipeline

- Configure Slack bridge.
- Set queue mode to `collect`.
- Set `agents.defaults.maxConcurrent` low enough to avoid noisy parallel compile work.
- Allowlist only the required binaries for `exec`.
- Enable memory writes to `MEMORY.md` and `memory/YYYY-MM-DD.md`.

### Step 6: Define the MVP acceptance test

Run one end-to-end thread with:
- one messy policy PDF
- one spreadsheet of numeric limits
- one freeform Slack message describing the objective

The MVP passes if:
- the agent produces a validated intermediate bundle
- the agent compiles a valid `.mps`
- the agent submits the artifact to HybridSolver
- the Slack thread shows status updates without leaking secrets

## Guardrails and Anti-Replication

- The sidecar may extract, normalize, validate, and compile.
- The sidecar may not claim it solved or optimized the model.
- The sidecar may not invent business constraints that were not present or explicitly approved.
- If ambiguity remains after one repair loop, the agent must ask the user in-thread rather than fabricate coefficients.
- If a request cannot be represented as MILP/LP/QUBO, the sidecar must fail closed and say so.

## Why This Version Exists Beside the Core PRD

The main PRD proves that OpenClaw can be a durable optimization-engineering sidecar. This lateral version answers a different question: what is the most founder-aligned, commercially visible, and technically credible intake surface for early adoption? Slack is the strongest answer because it satisfies Dirk's visibility mandate, Philipp's OpenClaw-native instincts, and the repo's own baseline framing that the agent should feel like a junior OR analyst living in the team's normal communication loop.
