# OpenClaw + Quantagonia HybridSolver: a demo architecture

**Bottom line:** build the demo as an **autonomous optimization-engineering agent** — an OpenClaw-hosted "junior OR analyst" that ingests raw business data files, writes its own Python modeling code, compiles `.mps`/`.lp`/`.qubo` artifacts on the local filesystem, orchestrates multi-stage HybridSolver jobs through lane-queued sequential runs, and persists learned problem structure in `MEMORY.md` across sessions. This design forces every OpenClaw primitive to do real work: it cannot be collapsed into a single API call because the agent must (a) explore and validate heterogeneous input files on disk, (b) generate and execute Python via the `exec` tool to produce solver-native formats, (c) chain dependent HybridSolver jobs where each stage's solution becomes the next stage's input, and (d) accumulate institutional knowledge about a client's problem family over weeks of runs. A thin API wrapper cannot do any of those things; an agent framework with a filesystem, a shell, a queue, and durable memory can.

The two halves of the stack are asymmetric in ways that matter for the demo. OpenClaw is a **Gateway + embedded pi-mono runtime** written in TypeScript, configured via a single JSON5 file at `~/.openclaw/openclaw.json`, with a 7-layer tool security model and skills defined as directories of Markdown + scripts. Quantagonia's HybridSolver, now a Strangeworks subsidiary, solves **MILP/LP and QUBO only** (no QP/MIQP/NLP) via a blocking `HybridSolver.solve()` or an async `submit` → `progress` → `status` → `logs` pattern, with a CLI (`hybridsolver`) and a free tier of 20 jobs/month direct, or 50-variable problems via Strangeworks. Those constraints shape exactly which use cases the demo can credibly stage.

## How OpenClaw actually works under the hood

OpenClaw is a **long-lived Node 22+/24 daemon** installed as a launchd/systemd user service, exposing a typed WebSocket on `127.0.0.1:18789` for channel bridges (WhatsApp, Slack, Telegram, Discord, web chat, etc.) and internal agents. Its embedded runtime is Mario Zechner's `@mariozechner/pi-coding-agent`, which handles prompt assembly, streaming tool calls, and compaction. The gateway watches the JSON5 config and hot-reloads it; unknown keys **refuse to start**, a deliberate schema-strictness choice. Installation is `npm install -g openclaw@latest` followed by `openclaw onboard --install-daemon`.

Seven primitives matter for this demo:

**Lane Queues** are a lane-aware FIFO queue with per-lane concurrency caps — `main` defaults to 4, `subagent` to 8, and every per-session lane is strictly 1 (single writer per session). Four queue-interaction modes — `collect`, `steer`, `followup`, `steer-backlog` — govern how new inbound messages interact with an in-flight turn. For the demo, this means a multi-stage solve can run serially on one session lane while a parallel subagent lane explores alternative formulations, **without race conditions on the workspace filesystem**.

**Semantic Snapshots** replace screenshots with text renderings of the page's accessibility tree (`- button "Sign In" [ref=1]`), resolved through Playwright-over-CDP's `aria-ref` or `getByRef` helpers. Claim from docs: a 5 MB screenshot becomes a 50 KB snapshot. Not central to the optimization demo, but useful if the agent needs to scrape a supplier portal for up-to-date cost data.

**JSONL transcript memory** lives at `~/.openclaw/agents/<agentId>/sessions/<sessionId>.jsonl`, written append-only by `SessionManager`. Line 1 is a session header; subsequent lines form a tree via `id`/`parentId`, enabling branching. A separate `sessions.json` maps `sessionKey → {sessionId, tokens, model, …}`. Known caveat — exec tool stdout/stderr is **persisted verbatim**, so a redaction pass (`src/logging/redact.ts`) is applied on read; the demo must be careful not to let a raw Quantagonia API key hit stdout.

**Markdown memory** is a four-layer stack: JSONL (current turn) → `memory/YYYY-MM-DD.md` (daily append logs) → `MEMORY.md` (curated long-term) → SQLite + `sqlite-vec` + FTS5 (semantic recall). `MEMORY.md` loads **only in private DM sessions**, an explicit security boundary. A pre-compaction "memory flush" turn asks the model to write durable notes to disk before context is truncated. For the demo, this is where the agent writes *"Client ACME's Q3 demand forecast has 12% variance that triggers capacity-slack in warehouse-3; pre-solve with that slack = 5 typically yields 18% faster convergence."*

**The Model Resolver** picks models in order: session override → `primary` → `fallbacks[]`; then does two-stage failover — auth-profile rotation within a provider, then cross-provider fallback. Cooldown state lives in `auth-profiles.json` with exponential backoff (1m → 5m → 25m → 1h). Billing failures disable the profile; rate-limit failures only cool it down. This is invisible to the demo but matters for reliability claims in the pitch.

**Tool use** is the real workhorse. Built-ins include `read`/`write`/`edit`/`apply_patch`, `exec`/`process` (gateway/node/sandbox hosts, with argv/cwd/env-bound approvals in `~/.openclaw/exec-approvals.json`), `browser`, `web_search`/`web_fetch`, `memory_search`/`memory_get`, and `sessions_spawn`/`sessions_send` for sub-agents. Policy resolution runs Global-deny → per-agent-deny → global-allow → per-agent-allow → default; `exec` supports `full`, `allowlist`, or approval-required modes, with allowlists matching **resolved binary paths**, not basenames. Extensions are authored as **Skills** — directories with a `SKILL.md` front-matter file plus `scripts/`, `references/`, `assets/` — lazily loaded (only `name`/`description`/`location` enter the prompt until the agent `read`s the full body). OpenClaw is also an **MCP client** (`openclaw mcp set …` or via `mcporter`) and can run as an MCP server (`openclaw mcp serve`) exposing conversation bridge tools.

**File-system and terminal interaction** enforce workspace path-escape checks (resolved realpaths must stay inside the workspace root) and scrub `PATH`/`LD_*`/`DYLD_*` env overrides before spawn to prevent binary hijacking. Shells prefer the user's `SHELL` on POSIX (fallback `bash`/`sh` if user has fish) and PowerShell 7 on Windows. Exec approvals **bind the canonical argv, cwd, env, and pinned executable path**; any drift causes rejection.

## What the HybridSolver accepts, and what it doesn't

Quantagonia's SDK (`pip install quantagonia>=0.15.0`, Python ≥3.9, BSD — note: PuLP 3.3.0 raises the floor from 3.8 to 3.9) supports three problem-file formats — **MPS** (preferred; `.mps`/`.mps.gz`), **LP** (CPLEX LP, Python API only — the CLI only takes `.mps`/`.qubo`), and **QUBO** (`.qubo`/`.qubo.gz`). Native modeling APIs include `quantagonia.mip.Model` (PySCIPOpt-based), a gurobipy-like wrapper, a DOcplex-like wrapper, a Python-MIP-like wrapper, and a PuLP adapter via `pulp_adapter.HybridSolver_CMD`. QUBO importers accept Qiskit `QuadraticProgram`, D-Wave `BinaryQuadraticModel`, and PyQUBO `Model`. **Crucially, QP, MIQP, and NLP are not supported** — docs consistently describe "MILPs and QUBOs to global optimality" and nothing else.

The async pattern is exactly what you want for an agentic orchestrator:

```python
hs = HybridSolver(os.environ["QUANTAGONIA_API_KEY"])
jobid = hs.submit("stage1.mps.gz", params)         # returns UUID
while hs.status(jobid) != JobStatus.finished:      # poll
    prog = hs.progress(jobid)[0]                   # incumbent, bound, gap
    sleep(2)
print(hs.logs(jobid)[0])
```

`HybridSolverParameters` exposes `set_time_limit`, `set_relative_gap` (default 1e-4), `set_absolute_gap` (default 1e-9), `set_presolve`, `set_seed`, `set_heuristics_only` (QUBO), and `set_objective_limit`. The CLI adds `--as-qubo` and `--as-qubo-only` flags that automatically reformulate binary MILPs — useful for the "try MIP and QUBO in parallel" demo beat. Default `solve()` timeout is **14,400 s (4 h)**. Files >10 MB are gzipped client-side automatically.

**Authentication** is a single env var, `QUANTAGONIA_API_KEY`, obtained from `platform.quantagonia.com`. **Free tier**: 20 jobs/month direct via Quantagonia, or free up to 50-variable problems through Strangeworks (`pip install strangeworks-optimization`, solver strings `quantagonia.mps`/`quantagonia.lp`/`quantagonia.qubo`, auth via `sw.authenticate(sw_key)`). Paid pricing is usage-based by minute but not publicly listed; `hybridsolver time-billed JOB_ID` returns minutes, and `solve()` returns billed minutes as the second tuple element — useful for an agent that **reports cost to the user inline**.

## The demo: an autonomous production-planning agent for decomposed MILPs

The defensible framing is **"a HybridSolver-native optimization engineer you talk to in Slack"** — an OpenClaw agent named something like `opt-engineer` whose sole purpose is turning messy client data folders into solved production plans, quarter by quarter, without a human writing MPS files. A realistic client workflow decomposes naturally: **annual production planning split into four sequential quarterly sub-problems**, where Q1's ending inventory becomes Q2's starting inventory, and capital-expansion decisions in Q1 constrain what's physically buildable in Q2–Q4. That dependency chain is what breaks pure API-wrapper approaches: you need a loop, a filesystem, and state.

Here is what each run looks like, and which OpenClaw primitive is load-bearing:

The analyst drops a quarterly data package into `~/opt-workspace/clients/acme/2026-annual/inputs/` (CSVs for demand, capacity, SKU routing, cost curves) and Slack-messages `@opt-engineer run annual plan for acme 2026`. The gateway routes to the agent's main session, which now holds the session lane exclusively. The agent calls `read` on the directory listing, then spawns four **subagents via `sessions_spawn`** on the subagent lane to profile each CSV in parallel (schema, ranges, missing values). Results are announced back; the main session writes a validation summary to `MEMORY.md` as a new dated entry.

Next, the main agent uses the `exec` tool to run `python -c "..."` snippets that call `pandas.read_csv` and emit a clean Parquet file per input — **real terminal work that would be ugly to rebuild inside a bespoke API wrapper**. On schema drift it regenerates its Python, commits to git (also via `exec`), and logs the decision in today's `memory/2026-04-17.md`.

The agent then **writes a Python modeling script** to `workspace/acme/2026-annual/q1_model.py` using the PuLP-based skill it loaded from ClawHub (`clawhub install hybridsolver-milp`). The script imports `from quantagonia.mip import pulp_adapter` and `HybridSolverParameters`, formulates the Q1 LP-relaxed MILP, and writes `q1.mps.gz` to disk. The agent runs the script via `exec`, which exits cleanly and produces a file the agent can now `read`-verify.

**Lane queues earn their place here.** The agent enqueues four sequential jobs on its session lane — `q1 → q2 → q3 → q4` — because each stage depends on the prior stage's solution. It simultaneously spawns a **parallel subagent** on the subagent lane that submits `q1.mps.gz` with `--as-qubo` as an experimental reformulation, to flag whether QUBO-style heuristics beat branch-and-bound on this instance. The main session monitors the MIP stage via `hybridsolver monitor <jobid>` in a background `process`, tailing the log into the JSONL transcript. When `progress()[0]["num_incumbents"] >= 1`, it posts a Slack update with the current objective, bound, and billed minutes (`hs.progress`, then `hs.time-billed`). On completion, it parses the solution dict (keys: `status`, `objective`, `bound`, `relative_gap`, `solution`, `num_quantum_solutions`), extracts ending-inventory variables, and **writes them into Q2's input file** before launching Q2.

Between stages, the agent updates `MEMORY.md` with structured facts: *"ACME Q1 2026: 847 binaries, 14 continuous blocks; solved to 0.01% gap in 147s; capacity-slack on W3 binds; quantum-heuristic reformulation produced identical objective in 89s — use `--as-qubo` first next quarter."* That entry is **semantically retrievable** by the memory_search tool next time the agent sees ACME data — the whole point of the Markdown+SQLite+sqlite-vec stack.

On failure modes, OpenClaw's agent loop earns its keep. If `hs.status` returns `TIMEOUT` with a poor gap, the agent reads the solver log, reasons about whether to (a) tighten presolve, (b) try QUBO reformulation via `set_heuristics_only(True)`, (c) relax gap tolerance, or (d) split the problem further — then modifies its Python and re-submits. A pure API wrapper cannot do this; an LLM call without file I/O and a shell cannot either. **Only an agent with workspace access, terminal execution, and a sequential queue can iterate on formulation until the solver succeeds.**

Finally, a **cron job** defined in config (`cron: { every: "0 6 * * *", session: "main", payload: { kind: "agentTurn", message: "check for new demand forecasts in ~/opt-workspace/inbox" } }`) runs every morning. If new forecasts arrive, the agent auto-triggers a re-optimization, appends deltas to `MEMORY.md`, and DMs the analyst a diff report. Heartbeat (every 30 min) ensures long `solve()` calls don't stall the gateway.

## Concrete configuration you'd ship with the demo

A minimal `~/.openclaw/openclaw.json` for this agent:

```json5
{
  gateway: { port: 18789 },
  agents: {
    defaults: {
      workspace: "~/opt-workspace",
      model: {
        primary: "anthropic/claude-sonnet-4-6",
        fallbacks: ["openai/gpt-5.4", "google/gemini-2.5-pro"]
      },
      maxConcurrent: 4,
      sandbox: { mode: "non-main", workspaceAccess: "rw" }
    },
    list: [{
      agentId: "opt-engineer",
      workspace: "~/opt-workspace",
      skills: { load: { extraDirs: ["~/opt-workspace/skills"] } }
    }]
  },
  channels: { slack: { allowFrom: ["U0123ANALYST"] } },
  tools: {
    exec: {
      security: "allowlist",
      safeBins: [
        "/usr/bin/python3", "/usr/local/bin/hybridsolver",
        "/usr/bin/git", "/bin/ls", "/bin/cat"
      ],
      approvalRunningNoticeMs: 10000
    }
  },
  messages: { queue: { mode: "collect", debounceMs: 2000 } }
}
```

A custom skill at `~/opt-workspace/skills/hybridsolver-milp/SKILL.md`:

```yaml
---
name: hybridsolver-milp
description: Formulate MILPs in PuLP, emit MPS, submit to Quantagonia HybridSolver, poll for solutions.
version: 0.1.0
metadata:
  openclaw:
    requires:
      env: [QUANTAGONIA_API_KEY]
      bins: [python3, hybridsolver]
---
# Usage
Call `scripts/submit.py <model.py> <params.json>` from the agent workspace...
```

The `scripts/submit.py` implements the async `submit → progress → status` loop, streams progress JSON back through stdout (captured verbatim into JSONL, mindful of the redaction caveat — the API key must be passed only via env, never in argv).

## Why this specific demo justifies the framework

A reviewer who asks *"couldn't you just write a Python script that calls HybridSolver?"* has four answers waiting. **First**, the script has to decide what model to build from unseen data — that requires an LLM reasoning loop grounded in file-system reads, which is exactly the agent loop. **Second**, sequential quarterly stages with dependencies require durable state between solves; OpenClaw's JSONL + MEMORY.md gives you that for free, whereas a script needs custom state management. **Third**, formulation iteration on solver failures requires code generation, execution, and re-submission — an agent with `write`+`exec` tools does this natively; a script cannot. **Fourth**, institutional knowledge accumulation across clients and quarters is exactly what the layered memory stack is built for, and explains why the *fifth* time the agent sees ACME data it finishes in half the time of the first.

The pitch lands because the demo showcases **three OpenClaw features that are simultaneously load-bearing and visually obvious on stage**: the Slack conversation streams live; the file tree at `~/opt-workspace/clients/acme/` fills up with generated `.py`, `.mps.gz`, and solution files in real time; and a `MEMORY.md` diff at the end shows learned facts that will make the *next* run faster. Under the hood, the HybridSolver is doing what it's best at — MILP and QUBO at global optimality — and nothing it doesn't support.

## Key caveats to design around

Three facts the demo build-out must respect. **(1)** Quantagonia's public docs explicitly limit the solver to MILP/LP/QUBO; the demo must not imply QP/NLP support, and should probably stick to MILP with optional `--as-qubo` reformulation for the "show the hybrid" moment. **(2)** Post-Strangeworks acquisition (Aug 2025), the direct `platform.quantagonia.com` endpoint is still alive with 2026 copyright but Strangeworks routing (`strangeworks-optimization` package, `quantagonia.mps` solver string) may be more durable long-term — consider supporting both, selected via config. **However**, note that `strangeworks-optimization` v0.2.28 (Aug 2024) has not been updated post-acquisition and requires Python 3.10–3.11; prefer the direct `quantagonia>=0.15.0` SDK for the demo unless Strangeworks releases a post-acquisition update. **(3)** OpenClaw persists exec stdout/stderr verbatim in JSONL before redaction; pass `QUANTAGONIA_API_KEY` only via env and never echo it, and prefer `hybridsolver api-key` inspection only in redacted contexts.

## Takeaways

The demo's credibility hinges on decomposition: annual-plan-as-four-dependent-quarters is a textbook OR problem that genuinely needs sequential task queuing, durable state, file-system-resident artifacts, and terminal-driven code generation — every OpenClaw primitive earns its keep and HybridSolver does what it's uniquely good at. A side benefit is that the same agent design generalizes trivially to **supply-chain rebalancing, portfolio optimization under rolling constraints, or multi-site energy scheduling** — any problem family where successive solves share learned structure. The framework choice becomes self-evident the moment a reviewer imagines removing OpenClaw and trying to rebuild the demo as a single script: they cannot, because the demo's value is precisely the things a single script cannot do.

---

## Appendix A: SDK Dependency Audit (2026-04-18)

Audit performed against live PyPI and official documentation. All API surfaces verified current.

| Package | Pinned Version | Python Req | Status |
|---|---|---|---|
| `quantagonia` | ≥0.15.0 (Mar 2026) | ≥3.8 | **Current.** Async `submit→progress→status→logs` pattern, `HybridSolverParameters` setters, CLI `--as-qubo`/`--as-qubo-only` flags — all verified unchanged. No deprecated methods. |
| `strangeworks-optimization` | 0.2.28 (Aug 2024) | 3.10–3.11 | **Stale.** No post-acquisition release. Solver strings `quantagonia.mps`/`.lp`/`.qubo` and `sw.authenticate()` still documented but package predates merger. Prefer direct Quantagonia SDK for demo; monitor for Strangeworks v0.3.x. |
| `PuLP` | ≥3.3.0 | ≥3.9 | **Current.** `LpProblem`, `LpSolver_CMD` interface stable. Python floor raised from 3.8→3.9. Custom `CMD` adapters like `HybridSolver_CMD` unaffected. |
| `pandas` | ≥2.2.0 | ≥3.9 | **Current.** `read_csv` stable. `DataFrame.append()` removed in 2.0 (use `pd.concat()`). No impact on this architecture. |

**Effective Python floor for the demo environment: ≥3.9** (driven by PuLP 3.3.0 and pandas 2.2.x).

**No PRD logic changes required.** The `submit → progress → status` async loop, `--as-qubo` CLI flags, `pulp_adapter.HybridSolver_CMD`, and all `HybridSolverParameters` setter methods are confirmed current as of this audit date.