import os
import sys

# Add scripts directory to path to import schemas and tools
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

from schemas_v3 import HealthStatus
from health_check import check_health
from tenant_manager import load_tenants, get_registry_path

app = FastAPI(title="Quantagonia Intake Agent API")

workspace_root = os.environ.get("WORKSPACE_ROOT", os.path.expanduser("~/opt-workspace"))

@app.get("/health", response_model=HealthStatus)
def health():
    return check_health(alert_slack=False)

@app.get("/tenants")
def list_tenants():
    registry_path = get_registry_path(workspace_root)
    return load_tenants(registry_path)

@app.get("/tenants/{tenant_id}/budget")
def get_tenant_budget(tenant_id: str):
    from cost_tracker import get_db, get_tenant_config
    from datetime import datetime
    
    tenant = get_tenant_config(workspace_root, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
        
    db = get_db(workspace_root)
    current_month = datetime.utcnow().strftime('%Y-%m')
    
    month_prefix = current_month + "%"
    rows = list(db.query("SELECT SUM(billed_minutes) as total FROM cost_records WHERE tenant_id = ? AND submitted_at LIKE ?", [tenant_id, month_prefix]))
    used = rows[0]['total'] or 0
    budget = tenant.get("budget_monthly_minutes")
    
    return {
        "tenant_id": tenant_id,
        "period": current_month,
        "total_minutes_used": used,
        "budget_limit": budget,
        "budget_remaining": (budget - used) if budget is not None else None,
        "jobs_submitted": db["cost_records"].count_where("tenant_id = ?", [tenant_id]),
        "jobs_succeeded": db["cost_records"].count_where("tenant_id = ? AND status = 'completed'", [tenant_id]),
        "jobs_failed": db["cost_records"].count_where("tenant_id = ? AND status != 'completed'", [tenant_id]),
        "alert_triggered": False # Simplified
    }

@app.get("/metrics")
def get_metrics():
    # Return prometheus format metrics
    from prometheus_client import generate_latest, REGISTRY, Counter, Gauge
    
    # Normally these are global singletons updated during execution
    return generate_latest(REGISTRY)

@app.post("/webhooks/solver-complete")
def solver_complete_webhook(payload: dict):
    # Future use
    return {"status": "acknowledged"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
