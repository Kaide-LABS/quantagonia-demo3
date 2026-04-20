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
