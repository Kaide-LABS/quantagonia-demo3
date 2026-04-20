import os
import sys
import json
import argparse
from datetime import datetime
from schemas_v3 import TenantConfig

def get_registry_path(workspace_root: str) -> str:
    return os.path.join(workspace_root, 'tenants.json')

def load_tenants(registry_path: str) -> dict:
    if not os.path.exists(registry_path):
        return {"tenants": []}
    with open(registry_path, 'r') as f:
        return json.load(f)

def save_tenants(registry_path: str, data: dict):
    with open(registry_path, 'w') as f:
        json.dump(data, f, indent=2)

def create_tenant(workspace_root: str, tenant_id: str, name: str, planners: list, budget: int = None):
    registry_path = get_registry_path(workspace_root)
    data = load_tenants(registry_path)
    
    if any(t['tenant_id'] == tenant_id for t in data['tenants']):
        print(f"Error: Tenant {tenant_id} already exists.", file=sys.stderr)
        sys.exit(1)
        
    tenant_workspace = os.path.join(workspace_root, 'tenants', tenant_id)
    clients_dir = os.path.join(tenant_workspace, 'clients', tenant_id)
    
    dirs_to_create = [
        os.path.join(clients_dir, 'inbox'),
        os.path.join(clients_dir, 'staging'),
        os.path.join(clients_dir, 'approved'),
        os.path.join(clients_dir, 'runs'),
        os.path.join(clients_dir, 'outbox'),
        os.path.join(tenant_workspace, 'memory'),
        os.path.join(tenant_workspace, 'plans'),
    ]
    
    for d in dirs_to_create:
        os.makedirs(d, exist_ok=True)
        
    # Init MEMORY.md
    memory_path = os.path.join(tenant_workspace, 'MEMORY.md')
    if not os.path.exists(memory_path):
        with open(memory_path, 'w') as f:
            f.write(f"## Tenant: {name}\nCreated: {datetime.utcnow().isoformat()}\n")
            
    config = TenantConfig(
        tenant_id=tenant_id,
        display_name=name,
        workspace_path=tenant_workspace,
        allowed_planners=planners,
        budget_monthly_minutes=budget,
        created_at=datetime.utcnow()
    )
    
    data['tenants'].append(config.model_dump(mode='json'))
    save_tenants(registry_path, data)
    print(f"Tenant {tenant_id} created successfully.")

def list_tenants(workspace_root: str):
    data = load_tenants(get_registry_path(workspace_root))
    print(json.dumps(data, indent=2))

def get_tenant(workspace_root: str, tenant_id: str):
    data = load_tenants(get_registry_path(workspace_root))
    t = next((t for t in data['tenants'] if t['tenant_id'] == tenant_id), None)
    if not t:
        print(f"Tenant {tenant_id} not found.", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(t, indent=2))

def deactivate_tenant(workspace_root: str, tenant_id: str):
    data = load_tenants(get_registry_path(workspace_root))
    for t in data['tenants']:
        if t['tenant_id'] == tenant_id:
            t['active'] = False
            save_tenants(get_registry_path(workspace_root), data)
            print(f"Tenant {tenant_id} deactivated.")
            return
    print(f"Tenant {tenant_id} not found.", file=sys.stderr)
    sys.exit(1)

def update_tenant(workspace_root: str, tenant_id: str, budget: int):
    data = load_tenants(get_registry_path(workspace_root))
    for t in data['tenants']:
        if t['tenant_id'] == tenant_id:
            if budget is not None:
                t['budget_monthly_minutes'] = budget
            save_tenants(get_registry_path(workspace_root), data)
            print(f"Tenant {tenant_id} updated.")
            return
    print(f"Tenant {tenant_id} not found.", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create", "list", "get", "update", "deactivate"])
    parser.add_argument("--id", dest="tenant_id")
    parser.add_argument("--name")
    parser.add_argument("--planners", help="Comma separated")
    parser.add_argument("--budget", type=int)
    parser.add_argument("--workspace-root", default=os.path.expanduser("~/opt-workspace"))
    args = parser.parse_args()
    
    if args.action == "create":
        if not args.tenant_id or not args.name or not args.planners:
            print("Missing --id, --name, or --planners", file=sys.stderr)
            sys.exit(1)
        planners = [p.strip() for p in args.planners.split(',')]
        create_tenant(args.workspace_root, args.tenant_id, args.name, planners, args.budget)
    elif args.action == "list":
        list_tenants(args.workspace_root)
    elif args.action == "get":
        get_tenant(args.workspace_root, args.tenant_id)
    elif args.action == "deactivate":
        deactivate_tenant(args.workspace_root, args.tenant_id)
    elif args.action == "update":
        update_tenant(args.workspace_root, args.tenant_id, args.budget)
