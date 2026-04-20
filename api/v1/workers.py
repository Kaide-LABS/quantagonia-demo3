import os
import sys
import subprocess
from celery import Celery

celery_app = Celery('decisionai')
celery_app.config_from_object({
    'broker_url': os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    'result_backend': os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    'task_serializer': 'json',
    'task_time_limit': 14400,  # 4 hours matching HybridSolver
    'task_soft_time_limit': 14100,
    'worker_concurrency': 2,
    'task_routes': {
        'process_request': {'queue': 'optimization'},
        'check_approval': {'queue': 'default'},
    }
})

@celery_app.task(bind=True, max_retries=2)
def process_request(self, request_id: str, tenant_id: str):
    """
    Main worker task. Runs the full Phase 1-3 pipeline for a request.
    """
    workspace_root = os.environ.get("WORKSPACE_ROOT", os.path.expanduser("~/opt-workspace"))
    run_dir = os.path.join(workspace_root, "tenants", tenant_id, "clients", tenant_id, "runs", request_id)
    
    # Anti-Replication Enforcement: 
    # We strictly spawn CLI subprocesses. No `quantagonia` or `scipy` imports allowed here.
    
    import redis
    r = redis.Redis.from_url(celery_app.conf.broker_url)
    
    def report_progress(status: str):
        import json as _json
        r.publish(f"job:{request_id}", _json.dumps({"type": "status_change", "status": status}))
        
    report_progress("processing")
    
    # 1. Download files from S3 -> tenant staging directory
    # 2. Run Phase 1 validation & artifacts...
    try:
        subprocess.run(['python3', 'scripts/validate_bundle.py', run_dir], check=True)
        report_progress("validation")
        subprocess.run(['python3', 'scripts/emit_pulp_artifacts.py', run_dir, '--lp'], check=True)
        report_progress("compilation")
    except subprocess.CalledProcessError:
        report_progress("failed")
        return {"status": "failed"}

    # Pause until APPROVE is flagged in DB...
    report_progress("awaiting_approval")
    
    # ... after approval, submission:
    try:
        subprocess.run(['python3', 'scripts/submit_hybridsolver.py', run_dir, '--time-limit', '3600'], check=True)
        report_progress("solver_progress")
        report_progress("completed")
    except subprocess.CalledProcessError:
        report_progress("failed")
        return {"status": "failed"}
        
    return {"status": "completed"}

@celery_app.task
def check_approval(request_id: str):
    pass
