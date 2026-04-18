# Lateral PRD v4: Email-to-API Intake Sidecar

## The Concept

This version keeps the same core sidecar architecture but changes the entry point to email. The problem being solved does not change: enterprise business rules are still messy, unstructured, and scattered across human communication. The sidecar still exists only to translate that mess into solver-safe artifacts for the Strangeworks/Quantagonia HybridSolver. The lateral move is to meet the user in the oldest and most common enterprise workflow: forwarding a thread to a dedicated mailbox.

The intended behavior is straightforward. A planner forwards an email chain containing policy changes, attachment bundles, and contradictory stakeholder comments to an intake address such as `decisionai-intake@company.com`. OpenClaw ingests the thread, extracts the actual constraints, writes a reviewable formulation package, and only then compiles and submits to HybridSolver after approval.

This is well-supported by the repo context. `CONTEXT.md` explicitly lists long-chain emails, PDFs, and spreadsheets as the messy pre-core sources that currently force humans to act as the translation layer between enterprise reality and the solver. `PRD.MD` makes the case that the right architecture needs a real queue, filesystem, `exec`, and durable memory. This variant preserves all of that while changing only the native environment.

## The Strategic Hook

Dirk Zechiel should find this variant commercially attractive because it pushes "Democratization of Planning" into the most familiar enterprise behavior possible. A user does not need to learn a wizard or join a new chat surface. They forward an email they were already going to send. That directly supports the accessibility and mainstream visibility goals described in `CONTEXT.md`.

Philipp Hannemann should like it for a different reason. The variant still leans heavily on OpenClaw-native orchestration rather than inventing a bespoke email parser product. It uses sessionized routing, structured memory, bounded tool execution, and deterministic handoff into the solver. It shows that agents can inhabit native environments without pretending to be the optimizer.

Wulff and Kleinert also get a strong assurance case. Email is messy and high-risk; therefore this version has the strictest default review posture. Nothing goes from mailbox to solver automatically. Every run produces a structured ambiguity report, validation output, and an approval gate before HybridSolver is called.

## The Agent Architecture

### End-to-end data flow

1. A user forwards an email thread and attachments to the intake mailbox.
2. An email bridge or webhook hands the inbound payload to OpenClaw.
3. OpenClaw creates a session keyed to the email thread id and enqueues it on lane `session:<thread_id>` with queue mode `collect`.
4. Gemini 3 Flash performs email-specific triage:
   - identify senders and likely roles
   - classify attachments
   - separate quoted history from the newest instruction
   - detect whether the email contains business rules, approval text, or only commentary
5. OpenClaw spawns bounded subagents for:
   - attachment parsing
   - thread summarization
   - policy extraction
6. Gemini 3 Pro merges those inputs into a canonical constraint bundle with explicit uncertainty markers.
7. OpenClaw writes the package into `runs/<request_id>/`:
   - normalized message transcript
   - extracted constraints
   - unresolved questions
   - validation report
8. `exec` runs deterministic validation and PuLP emission.
9. An approval gate is generated:
   - response email draft, or
   - status file for a reviewer surface if one already exists
10. Only after explicit approval does OpenClaw submit to HybridSolver.
11. Submission status is written back to the run package and optionally returned through email.

### OpenClaw primitives that must be explicit

- **Lane Queues:** Email follow-ups can arrive mid-run. Queue mode `collect` ensures thread-local coherence instead of duplicate extraction runs from every reply-all message.
- **`exec`:** Use `exec` for normalization, validation, artifact emission, and HybridSolver submission. Keep exact allowlisted binaries and avoid loader-path overrides.
- **`MEMORY.md`:** Store durable customer semantics:
  - recurring sender aliases
  - meaning of department shorthand
  - approved interpretation rules for forwarded threads
  - account-specific unit defaults
- **Daily notes:** Store run-specific confusion points such as "forwarded thread omitted latest attachment version" or "sender mixed physical limits with approval commentary."
- **JSONL transcripts:** Keep a factual chain of which email text and which attachment produced each extracted rule.

### Gemini model split

- **Gemini 3 Flash**
  - email triage
  - quote stripping
  - sender-role identification
  - concise reviewer summaries
- **Gemini 3 Pro**
  - full business-rule extraction
  - reconciliation across attachments and thread history
  - validator-driven repair
  - final formulation package drafting

### HybridSolver boundary

The same hard rules apply:

- HybridSolver accepts the final MILP/LP/QUBO artifacts
- the sidecar only prepares and submits
- default output is `.mps`
- `.lp` is optional
- `.qubo` is conditional and never assumed
- submission uses the documented async interface

## The Native Environment UI Spec

The user interacts by email.

### Mailbox contract

- Dedicated intake address such as `decisionai-intake@...`
- Allowed attachment types:
  - PDF
  - XLSX
  - CSV
  - TXT
  - DOCX only if explicitly parsed in scope
- Recommended subject format:
  - `[Account] [Planning Horizon] [Request Type]`

### Required interaction pattern

1. User forwards the email chain and attachments.
2. Agent sends an intake receipt.
3. Agent produces a review package containing:
   - extracted rules
   - inferred structure
   - unresolved assumptions
   - validator outcome
4. Reviewer approves or rejects.
5. On approval, agent compiles artifacts and submits.
6. Agent returns the job id and status summary.

### Exact UX requirements

- The latest email content must be separated from quoted history.
- Each extracted rule must reference its source email or attachment.
- Approval must be explicit and attributable.
- The returned package must include:
  - constraint summary
  - ambiguity report
  - validation result
  - artifact filenames
  - solver job id
  - current status

### Non-goals

- No new inbox product
- No standalone reviewer dashboard
- No post-solve workforce dispatch system

## Phase 1 Execution Spec

Build the MVP in GitHub Codespaces using a mocked email payload fixture first.

### Step 1: Prepare the environment

- Install OpenClaw and Python dependencies.
- Install `quantagonia>=0.15.0`, `pulp>=3.3.0`, `pandas>=2.2.0`, `pydantic`.
- Configure `QUANTAGONIA_API_KEY` as a secret.

### Step 2: Create the email intake skill

- Add `skills/constraint-intake-email/SKILL.md`.
- The skill must define:
  - how to parse forwarded email chains
  - how to split quoted history from the newest request
  - what triggers a reviewer approval requirement
  - how to store durable sender and terminology knowledge

### Step 3: Add deterministic scripts

- `scripts/normalize_email_payload.py`
- `scripts/validate_constraint_bundle.py`
- `scripts/emit_pulp_artifacts.py`
- `scripts/submit_hybridsolver.py`
- `scripts/render_reviewer_package.py`

### Step 4: Define the run layout

- `runs/<request_id>/email.json`
- `runs/<request_id>/normalized_thread.md`
- `runs/<request_id>/constraint_bundle.json`
- `runs/<request_id>/validation_report.json`
- `runs/<request_id>/review_package.md`
- `runs/<request_id>/model.py`
- `runs/<request_id>/artifacts/`
- `runs/<request_id>/submission.json`

### Step 5: Wire OpenClaw behavior

- Configure the email bridge or mocked local adapter.
- Use queue mode `collect`.
- Keep `exec` locked to allowlisted binaries.
- Write approved customer-specific email semantics into `MEMORY.md`.

### Step 6: Define the MVP acceptance test

Use one fixture containing:
- a forwarded email chain
- one PDF attachment
- one spreadsheet
- contradictory stakeholder comments in the email body

The MVP passes if:
- the newest actionable request is isolated correctly
- the constraint bundle is validated
- a valid `.mps` is emitted
- approval is required before submission
- HybridSolver submission metadata can be returned cleanly

## Guardrails and Anti-Replication

- Email language is evidence, not executable truth.
- The sidecar may not treat all prose in a forwarded thread as hard constraints.
- If an email mixes policy, commentary, and approvals, the agent must separate them explicitly.
- No direct mailbox-to-solver automation without approval.
- No out-of-scope formulation types beyond MILP/LP/QUBO.

## Why This Version Exists Beside the Core PRD

The main PRD establishes why the sidecar needs OpenClaw and why HybridSolver must remain the math boundary. This lateral version answers a different adoption question: what if the most realistic enterprise intake surface is not Slack or a folder, but a forwarded email thread full of buried business rules? The answer is still the same core architecture, just attached to a different trigger. That makes this version useful for conservative enterprises where email remains the true operating system of coordination.
