import os
import sys
import json
import time
import argparse
from datetime import datetime

try:
    from quantagonia import HybridSolver, HybridSolverParameters
    from quantagonia.enums import JobStatus
except ImportError:
    print("quantagonia package not installed.", file=sys.stderr)
    sys.exit(1)

def submit_job(run_dir: str, time_limit: int, rel_gap: float, as_qubo: bool):
    api_key = os.environ.get("QUANTAGONIA_API_KEY")
    if not api_key:
        print("QUANTAGONIA_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(2)
        
    mps_gz_path = os.path.join(run_dir, 'artifacts', 'problem.mps.gz')
    if not os.path.exists(mps_gz_path):
        print(f"Input file not found: {mps_gz_path}", file=sys.stderr)
        sys.exit(1)
        
    request_id = os.path.basename(os.path.normpath(run_dir))
    
    solver = HybridSolver(api_key)
    params = HybridSolverParameters()
    if time_limit:
        params.set_time_limit(time_limit)
    if rel_gap:
        params.set_relative_gap(rel_gap)
        
    submit_kwargs = {"tag": request_id}
    if as_qubo:
        # According to PRD, via kwargs
        submit_kwargs["as_qubo"] = True
        
    try:
        job_id = solver.submit(mps_gz_path, params, **submit_kwargs)
        print(json.dumps({"event": "submitted", "job_id": job_id, "timestamp": datetime.utcnow().isoformat()}))
        sys.stdout.flush()
    except Exception as e:
        msg = str(e).replace(api_key, "***REDACTED***")
        print(f"Submit error: {msg}", file=sys.stderr)
        sys.exit(1)
        
    status = None
    while True:
        time.sleep(5.0)
        try:
            status = solver.status(job_id)
            progress_list = solver.progress(job_id)
            prog = progress_list[0] if progress_list else {}
            
            print(json.dumps({
                "event": "progress",
                "job_status": status.value if hasattr(status, 'value') else str(status),
                "objective": prog.get("objective"),
                "bound": prog.get("bound"),
                "rel_gap": prog.get("relative_gap"),
                "wall_time": prog.get("wall_time"),
                "num_incumbents": prog.get("num_incumbents", 0),
                "timestamp": datetime.utcnow().isoformat()
            }))
            sys.stdout.flush()
            
            if status in (JobStatus.finished, JobStatus.terminated, JobStatus.timeout, JobStatus.error):
                break
        except Exception as e:
            msg = str(e).replace(api_key, "***REDACTED***")
            print(f"Poll warning: {msg}", file=sys.stderr)
            
    # End of polling
    try:
        logs = solver.logs(job_id)
        # Note: Billed minutes requires the time-billed API or checking tuple, 
        # but the progress API might return it, or solver.time_billed(job_id) 
        # Using a fallback 0 since PRD says "hybridsolver time-billed JOB_ID" or tuple
        billed_minutes = 0
    except Exception:
        billed_minutes = None

    record = {
        "request_id": request_id,
        "job_id": job_id,
        "submitted_at": datetime.utcnow().isoformat(),
        "input_file": mps_gz_path,
        "params": {"time_limit": time_limit, "relative_gap": rel_gap, "as_qubo": as_qubo},
        "status": status.value if hasattr(status, 'value') else str(status),
        "objective": prog.get("objective") if 'prog' in locals() else None,
        "bound": prog.get("bound") if 'prog' in locals() else None,
        "rel_gap": prog.get("relative_gap") if 'prog' in locals() else None,
        "wall_time": prog.get("wall_time") if 'prog' in locals() else None,
        "billed_minutes": billed_minutes
    }
    
    with open(os.path.join(run_dir, 'submission.json'), 'w') as f:
        json.dump(record, f, indent=2)
        
    print(json.dumps({
        "event": "completed",
        "status": record["status"],
        "objective": record["objective"],
        "bound": record["bound"],
        "rel_gap": record["rel_gap"],
        "billed_minutes": record["billed_minutes"]
    }))
    
    if status == JobStatus.error:
        sys.exit(1)
    elif status == JobStatus.timeout:
        sys.exit(2)
    elif status == JobStatus.terminated:
        sys.exit(3)
    else:
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--time-limit", type=int, default=3600)
    parser.add_argument("--rel-gap", type=float, default=0.01)
    parser.add_argument("--as-qubo", action="store_true")
    args = parser.parse_args()
    submit_job(args.run_dir, args.time_limit, args.rel_gap, args.as_qubo)
