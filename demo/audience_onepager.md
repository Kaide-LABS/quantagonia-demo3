# DecisionAI Intake Agent — Technical Overview

## What It Does
Autonomous pre-processing pipeline: enterprise data → validated .mps artifacts → HybridSolver

## What It Doesn't Do
- Never executes Simplex, Branch-and-Bound, or Cutting Plane
- Never fabricates constraints not present in source data
- Never submits without human approval

## Architecture
1. **Intake & Classification**: Gemini Flash 
2. **Extraction**: Gemini Pro parallel processing of PDF, XLSX, CSV
3. **Deterministic Gate**: Python-based Pydantic schema validation
4. **Compilation**: PuLP `.mps` emission
5. **Solver Execution**: Quantagonia HybridSolver API

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
- **OptiMUS (Stanford, 2024)**: LLM formulation, solver computation — same pattern
- **OptiTrust (IBM, 2025)**: Verifiable LLM optimization modeling
- **MIPLIB-NL (2026)**: Validates need for deterministic post-extraction gates
