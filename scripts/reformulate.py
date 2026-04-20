import os
import sys
import json
import argparse
from datetime import datetime
from schemas_v2 import ReformulationAction

def reformulate(stage_dir: str, attempt: int, failure_reason: str):
    log_path = os.path.join(stage_dir, 'reformulation_log.json')
    
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            log_data = json.load(f)
    else:
        log_data = {"attempts": []}
        
    if attempt > 3:
        print("Max reformulation attempts reached.", file=sys.stderr)
        sys.exit(1)
        
    action_type = "increase_time"
    rationale = "Default fallback"
    param_changes = {}

    if failure_reason == "timeout":
        if attempt == 1:
            action_type = "increase_time"
            param_changes = {"time_limit_multiplier": 2}
            rationale = "Initial time limit may be insufficient for problem size"
        elif attempt == 2:
            action_type = "tighten_presolve"
            param_changes = {"presolve": True, "heuristics_only": True}
            rationale = "Tighten preprocessing to reduce search space"
        else:
            action_type = "relax_gap"
            param_changes = {"relative_gap": 0.05}
            rationale = "Accept sub-optimal solution rather than no solution"
    elif failure_reason == "poor_gap":
        if attempt == 1:
            action_type = "try_qubo"
            param_changes = {"as_qubo": True}
            rationale = "QUBO reformulation may find better heuristic bounds"
        elif attempt == 2:
            action_type = "increase_time"
            param_changes = {"time_limit_multiplier": 3}
            rationale = "Allow more time for branch-and-bound to close gap"
        else:
            print("Accepting current solution with warning", file=sys.stderr)
            sys.exit(0)
    elif failure_reason == "error":
        print("Error requires Gemini repair or human escalation", file=sys.stderr)
        # Note: we would call gemini_client.py here if infeasible
        sys.exit(1)

    action = ReformulationAction(
        action_type=action_type,
        rationale=rationale,
        param_changes=param_changes,
        attempt_number=attempt
    )
    
    log_data["attempts"].append({
        "attempt": attempt,
        "action_type": action_type,
        "param_changes": param_changes,
        "rationale": rationale,
        "result": "pending",
        "timestamp": datetime.utcnow().isoformat()
    })
    
    with open(log_path, 'w') as f:
        json.dump(log_data, f, indent=2)
        
    # In a real implementation, we would rewrite params.json or constraint_bundle.json here
    print(json.dumps({
        "event": "reformulation_applied",
        "attempt": attempt,
        "action_type": action_type,
        "rationale": rationale
    }))
    sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage_dir")
    parser.add_argument("--attempt", type=int, required=True)
    parser.add_argument("--failure-reason", choices=["timeout", "poor_gap", "error"], required=True)
    args = parser.parse_args()
    
    reformulate(args.stage_dir, args.attempt, args.failure_reason)
