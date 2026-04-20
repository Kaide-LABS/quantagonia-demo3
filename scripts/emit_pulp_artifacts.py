import os
import sys
import json
import argparse
from datetime import datetime
import subprocess

from pulp import LpProblem, LpMinimize, LpMaximize, LpVariable, LpContinuous, LpInteger, LpBinary, lpSum
from schemas import ConstraintBundle, VariableType

def emit_artifacts(run_dir: str, do_lp: bool, do_qubo: bool):
    bundle_path = os.path.join(run_dir, 'constraint_bundle.json')
    artifacts_dir = os.path.join(run_dir, 'artifacts')
    os.makedirs(artifacts_dir, exist_ok=True)
    
    with open(bundle_path, 'r') as f:
        raw = f.read()
    
    try:
        bundle = ConstraintBundle.model_validate_json(raw)
    except Exception as e:
        print(f"Failed to parse validated bundle: {e}", file=sys.stderr)
        sys.exit(1)
        
    sense = LpMinimize if bundle.objective.sense == "minimize" else LpMaximize
    prob = LpProblem(bundle.request_id, sense)
    
    var_map = {}
    all_binary = True
    
    for v in bundle.variables:
        if v.type == "continuous":
            cat = LpContinuous
            all_binary = False
        elif v.type == "integer":
            cat = LpInteger
            all_binary = False
        else:
            cat = LpBinary
            
        var_map[v.id] = LpVariable(v.id, lowBound=v.lower_bound, upBound=v.upper_bound, cat=cat)
        
    obj_expr = lpSum([t.coefficient * var_map[t.variable_id] for t in bundle.objective.terms]) + bundle.objective.constant
    prob += obj_expr, "objective"
    
    for c in bundle.constraints:
        lhs_expr = lpSum([coef.value * var_map[coef.variable_id] for coef in c.lhs])
        if c.operator == "<=":
            prob += (lhs_expr <= c.rhs, c.id)
        elif c.operator == ">=":
            prob += (lhs_expr >= c.rhs, c.id)
        else:
            prob += (lhs_expr == c.rhs, c.id)
            
    mps_path = os.path.join(artifacts_dir, 'problem.mps')
    prob.writeMPS(mps_path)
    
    if do_lp:
        lp_path = os.path.join(artifacts_dir, 'problem.lp')
        prob.writeLP(lp_path)
        
    mps_gz_path = mps_path + '.gz'
    subprocess.run(['gzip', '-c', mps_path], stdout=open(mps_gz_path, 'wb'))
    
    if do_qubo:
        if not all_binary:
            print("QUBO requested but problem contains non-binary variables", file=sys.stderr)
            sys.exit(1)
        # Touch a marker file
        with open(os.path.join(artifacts_dir, 'problem.qubo_eligible'), 'w') as f:
            f.write("Problem is QUBO eligible. Use --as-qubo-only at submission.")
            
    # Write model.py template (without any solve calls)
    model_py_path = os.path.join(run_dir, 'model.py')
    model_code = f'''"""Auto-generated PuLP model for request: {bundle.request_id}
Generated: {datetime.utcnow().isoformat()}
Variables: {len(bundle.variables)} | Constraints: {len(bundle.constraints)}
DO NOT EDIT — regenerate via emit_pulp_artifacts.py
"""
from pulp import *

prob = LpProblem("{bundle.request_id}", { 'LpMinimize' if bundle.objective.sense == 'minimize' else 'LpMaximize' })

# Variables
'''
    for v in bundle.variables:
        cat_str = "LpContinuous" if v.type == "continuous" else "LpInteger" if v.type == "integer" else "LpBinary"
        model_code += f'{v.id} = LpVariable("{v.id}", {v.lower_bound}, {v.upper_bound}, cat="{cat_str}")\n'
        
    model_code += f'\n# Export (No solving allowed in this file due to FDE anti-replication rules)\n'
    model_code += f'prob.writeMPS("artifacts/problem.mps")\n'
    
    with open(model_py_path, 'w') as f:
        f.write(model_code)
        
    # Security/Anti-Replication Check
    with open(model_py_path, 'r') as f:
        content = f.read()
        if "solve(" in content or "scipy.optimize" in content or "ortools" in content:
            print("Anti-Replication Violation: solver execution code detected in generated model.py", file=sys.stderr)
            sys.exit(1)

    print(json.dumps({
        "variables": len(bundle.variables),
        "constraints": len(bundle.constraints),
        "mps_path": mps_path,
        "mps_size_bytes": os.path.getsize(mps_path)
    }))
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--lp", action="store_true")
    parser.add_argument("--qubo", action="store_true")
    args = parser.parse_args()
    
    emit_artifacts(args.run_dir, args.lp, args.qubo)
