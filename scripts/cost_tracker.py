import os
import sys
import json
import uuid
import sqlite3
import argparse
from datetime import datetime
from sqlite_utils import Database

def get_db(workspace_root: str) -> Database:
    db_path = os.path.join(workspace_root, 'cost_tracker.db')
    db = Database(db_path)
    if "cost_records" not in db.table_names():
        db["cost_records"].create({
            "id": str,
            "tenant_id": str,
            "request_id": str,
            "stage_id": str,
            "job_id": str,
            "billed_minutes": int,
            "submitted_at": str,
            "completed_at": str,
            "status": str,
            "objective": float,
            "created_at": str
        }, pk="id")
        db["cost_records"].create_index(["tenant_id", "submitted_at"])
    return db

def get_tenant_config(workspace_root: str, tenant_id: str) -> dict:
    registry = os.path.join(workspace_root, 'tenants.json')
    if not os.path.exists(registry):
        return None
    with open(registry, 'r') as f:
        data = json.load(f)
    return next((t for t in data.get('tenants', []) if t['tenant_id'] == tenant_id), None)

def record_cost(workspace_root: str, tenant_id: str, request_id: str, job_id: str, minutes: int, stage_id: str = None, objective: float = None):
    db = get_db(workspace_root)
    db["cost_records"].insert({
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "request_id": request_id,
        "stage_id": stage_id,
        "job_id": job_id,
        "billed_minutes": minutes,
        "submitted_at": datetime.utcnow().isoformat(),
        "completed_at": datetime.utcnow().isoformat(),
        "status": "completed",
        "objective": objective,
        "created_at": datetime.utcnow().isoformat()
    })
    print(f"Recorded {minutes} mins for tenant {tenant_id}, job {job_id}")

def check_budget(workspace_root: str, tenant_id: str):
    tenant = get_tenant_config(workspace_root, tenant_id)
    if not tenant:
        print(f"Tenant {tenant_id} not found", file=sys.stderr)
        sys.exit(2)
        
    budget = tenant.get("budget_monthly_minutes")
    if budget is None:
        print(json.dumps({"status": "ok", "message": "No budget limit"}))
        sys.exit(0)
        
    db = get_db(workspace_root)
    current_month = datetime.utcnow().strftime('%Y-%m')
    
    # Calculate sum
    rows = list(db.query(f"SELECT SUM(billed_minutes) as total FROM cost_records WHERE tenant_id = ? AND submitted_at LIKE '{current_month}%'", [tenant_id]))
    used = rows[0]['total'] or 0
    
    if used >= budget:
        print(json.dumps({"status": "exceeded", "used": used, "budget": budget}))
        sys.exit(1)
    
    threshold = tenant.get("budget_alert_threshold", 0.8)
    if used >= budget * threshold:
        print(json.dumps({"status": "warning", "used": used, "budget": budget}))
        sys.exit(0)
        
    print(json.dumps({"status": "ok", "used": used, "budget": budget}))
    sys.exit(0)

def export_records(workspace_root: str, fmt: str):
    db = get_db(workspace_root)
    records = list(db["cost_records"].rows)
    if fmt == "json":
        print(json.dumps(records, indent=2))
    elif fmt == "csv":
        if not records:
            return
        keys = records[0].keys()
        import csv
        writer = csv.DictWriter(sys.stdout, fieldnames=keys)
        writer.writeheader()
        writer.writerows(records)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["record", "check-budget", "summary", "export"])
    parser.add_argument("--tenant", dest="tenant_id")
    parser.add_argument("--request", dest="request_id")
    parser.add_argument("--job", dest="job_id")
    parser.add_argument("--minutes", type=int)
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--workspace-root", default=os.path.expanduser("~/opt-workspace"))
    args = parser.parse_args()
    
    if args.action == "record":
        record_cost(args.workspace_root, args.tenant_id, args.request_id, args.job_id, args.minutes)
    elif args.action == "check-budget":
        check_budget(args.workspace_root, args.tenant_id)
    elif args.action == "export":
        export_records(args.workspace_root, args.format)
