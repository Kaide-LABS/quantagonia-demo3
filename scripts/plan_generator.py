import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from schemas_v2 import DecompositionPlan, StageDefinition

def generate_plan(input_dir: str, account: str, strategy: str):
    # Mock generation using heuristics since Gemini API requires actual key
    request_id = os.path.basename(os.path.normpath(input_dir))
    
    stages = []
    if strategy == "quarterly":
        for i in range(1, 5):
            stages.append(StageDefinition(
                stage_id=f"q{i}_2026",
                stage_order=i,
                depends_on=[f"q{i-1}_2026"] if i > 1 else [],
                input_files=[f"demand_q{i}.csv", "capacity.csv"],
                carry_forward_variables=[f"ending_inventory_q{i}"] if i < 4 else [],
                qubo_eligible=True
            ))
    else:
        stages.append(StageDefinition(
            stage_id="main_stage",
            stage_order=1,
            input_files=["data.csv"],
            qubo_eligible=False
        ))

    plan = DecompositionPlan(
        plan_id=request_id,
        account=account,
        description=f"Auto-generated {strategy} plan",
        stages=stages,
        global_params={"time_limit": 3600},
        carry_forward_strategy="ending_inventory",
        created_at=datetime.utcnow()
    )
    
    plan_path = os.path.join(input_dir, 'decomposition_plan.json')
    with open(plan_path, 'w') as f:
        f.write(plan.model_dump_json(indent=2))
        
    print(json.dumps({"event": "plan_generated", "plan_id": request_id, "strategy": strategy}))
    sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir")
    parser.add_argument("--account", required=True)
    parser.add_argument("--strategy", choices=["quarterly", "custom"], required=True)
    args = parser.parse_args()
    
    generate_plan(args.input_dir, args.account, args.strategy)
