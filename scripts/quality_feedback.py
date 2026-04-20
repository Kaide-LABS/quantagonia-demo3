import os
import sys
import json
import argparse
from datetime import datetime

def generate_feedback(run_dir: str, tenant_id: str):
    sub_path = os.path.join(run_dir, "submission.json")
    if not os.path.exists(sub_path):
        print("No submission.json found.")
        sys.exit(1)
        
    with open(sub_path, 'r') as f:
        sub = json.load(f)
        
    gap = sub.get("rel_gap")
    outcome = sub.get("status")
    
    quality = "good"
    if gap is not None:
        if gap > 0.10 or outcome == "TIMEOUT":
            quality = "poor"
        elif gap > 0.01:
            quality = "acceptable"
            
    if quality == "poor":
        # FDE Boundary Enforcement:
        # The feedback loop ONLY adjusts LLM prompts to improve constraint extraction.
        # It MUST NOT manipulate solver execution flags or heuristics directly.
        additions = [
            "Given this solver failure, ensure capacities are normalized strictly to metric tons.",
            "Ensure 'overtime' refers to hours beyond 8h shift, not weekend work."
        ]
        
        workspace_root = os.environ.get("WORKSPACE_ROOT", os.path.expanduser("~/opt-workspace"))
        additions_file = os.path.join(workspace_root, "tenants", tenant_id, "prompt_additions.md")
        os.makedirs(os.path.dirname(additions_file), exist_ok=True)
        
        with open(additions_file, "a") as f:
            f.write(f"\n## Learned Extraction Guidance ({datetime.utcnow().strftime('%Y-%m-%d')})\n")
            for a in additions:
                f.write(f"- {a}\n")
                
        print(f"Generated quality feedback: {quality}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--tenant", required=True)
    args = parser.parse_args()
    
    generate_feedback(args.run_dir, args.tenant)
