import os
import sys
import json
import asyncio
import subprocess
from datetime import datetime
from schemas_v2 import DecompositionPlan, PlanExecutionReport, StageResult

async def run_stage(stage, plan, plan_dir, env):
    stage_dir = os.path.join(plan_dir, 'stages', stage.stage_id)
    os.makedirs(stage_dir, exist_ok=True)
    
    print(json.dumps({"event": "stage_started", "stage_id": stage.stage_id}))
    sys.stdout.flush()

    time_limit = stage.time_limit_override or plan.global_params.get("time_limit", 3600)
    
    # 1. validate
    proc = await asyncio.create_subprocess_exec(
        'python3', 'scripts/validate_bundle.py', stage_dir,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )
    await proc.communicate()
    
    # 2. compile
    proc = await asyncio.create_subprocess_exec(
        'python3', 'scripts/emit_pulp_artifacts.py', stage_dir, '--lp',
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )
    await proc.communicate()

    # 3. submit MIP
    submit_cmd = ['python3', 'scripts/submit_hybridsolver.py', stage_dir, '--time-limit', str(time_limit)]
    mip_proc = await asyncio.create_subprocess_exec(
        *submit_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )
    
    # 4. parallel QUBO if eligible
    qubo_proc = None
    if stage.qubo_eligible:
        qubo_cmd = ['python3', 'scripts/submit_hybridsolver.py', stage_dir, '--time-limit', str(time_limit), '--as-qubo']
        qubo_proc = await asyncio.create_subprocess_exec(
            *qubo_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
        )

    await mip_proc.communicate()
    if qubo_proc:
        await qubo_proc.communicate()

    # Load result
    sub_path = os.path.join(stage_dir, 'submission.json')
    if os.path.exists(sub_path):
        with open(sub_path, 'r') as f:
            sub = json.load(f)
    else:
        sub = {"status": "error", "objective": None, "rel_gap": None, "wall_time": None, "billed_minutes": 0, "job_id": "none"}
        
    status = "success" if sub.get("status") in ["FINISHED", "SUCCESS", "success"] else "error"
    if sub.get("status") == "TIMEOUT":
        status = "timeout"
        
    result = StageResult(
        stage_id=stage.stage_id,
        job_id=sub.get("job_id", ""),
        status=status,
        objective=sub.get("objective"),
        bound=sub.get("bound"),
        rel_gap=sub.get("rel_gap"),
        wall_time=sub.get("wall_time", 0.0),
        billed_minutes=sub.get("billed_minutes", 0) or 0
    )
    
    # Check if needs reformulation (mock logic integration)
    if status == "timeout" or (result.rel_gap is not None and result.rel_gap > 0.05):
        # We would run reformulate.py here
        # For blueprint, we just log it
        print(json.dumps({"event": "reformulation_triggered", "stage_id": stage.stage_id}))
        
    print(json.dumps({
        "event": "stage_completed", 
        "stage_id": stage.stage_id, 
        "objective": result.objective,
        "status": result.status
    }))
    sys.stdout.flush()
    return result

async def orchestrate(plan_dir: str):
    plan_path = os.path.join(plan_dir, 'decomposition_plan.json')
    if not os.path.exists(plan_path):
        print(f"Plan file not found: {plan_path}", file=sys.stderr)
        sys.exit(1)
        
    with open(plan_path, 'r') as f:
        plan_data = json.load(f)
    plan = DecompositionPlan.model_validate(plan_data)
    
    report = PlanExecutionReport(
        plan_id=plan.plan_id,
        account=plan.account,
        started_at=datetime.utcnow(),
        stages_total=len(plan.stages),
        overall_status="running"
    )
    
    env = os.environ.copy()
    stage_results_map = {}

    for stage in plan.stages:
        # Check deps
        deps_met = True
        for dep in stage.depends_on:
            if dep not in stage_results_map or stage_results_map[dep].status != "success":
                deps_met = False
                break
                
        if not deps_met:
            result = StageResult(stage_id=stage.stage_id, job_id="", status="skipped", billed_minutes=0)
            report.stage_results.append(result)
            stage_results_map[stage.stage_id] = result
            continue
            
        # Run carry forward if depends
        if stage.depends_on:
            prev_stage = stage.depends_on[-1] # Simplification
            prev_dir = os.path.join(plan_dir, 'stages', prev_stage)
            curr_dir = os.path.join(plan_dir, 'stages', stage.stage_id)
            vars_to_carry = ",".join(stage.carry_forward_variables)
            
            if vars_to_carry:
                cf_proc = await asyncio.create_subprocess_exec(
                    'python3', 'scripts/carry_forward.py', prev_dir, curr_dir, '--variables', vars_to_carry,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
                )
                await cf_proc.communicate()
        
        result = await run_stage(stage, plan, plan_dir, env)
        report.stage_results.append(result)
        stage_results_map[stage.stage_id] = result
        
        if result.status == "success":
            report.stages_completed += 1
            report.total_wall_time += (result.wall_time or 0.0)
            report.total_billed_minutes += result.billed_minutes
            
    report.completed_at = datetime.utcnow()
    report.overall_status = "completed" if report.stages_completed == report.stages_total else "partial"
    
    with open(os.path.join(plan_dir, 'execution_report.json'), 'w') as f:
        f.write(report.model_dump_json(indent=2))
        
    print(json.dumps({"event": "plan_completed", "plan_id": plan.plan_id, "status": report.overall_status}))
    if report.overall_status == "completed":
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: orchestrate_plan.py <plan_dir>", file=sys.stderr)
        sys.exit(2)
    asyncio.run(orchestrate(sys.argv[1]))
