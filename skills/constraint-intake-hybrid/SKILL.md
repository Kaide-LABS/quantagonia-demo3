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
