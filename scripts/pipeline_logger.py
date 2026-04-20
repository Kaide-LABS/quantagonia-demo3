import os
import json
from datetime import datetime
from typing import Any, Dict

def log_event(tenant_id: str, request_id: str, event_type: str, details: Dict[str, Any], duration_ms: int = None, workspace_root: str = "~/opt-workspace"):
    log_file = os.path.expanduser(os.path.join(workspace_root, "pipeline_events.jsonl"))
    
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "tenant_id": tenant_id,
        "request_id": request_id,
        "event_type": event_type,
        "details": details,
        "duration_ms": duration_ms
    }
    
    with open(log_file, "a") as f:
        f.write(json.dumps(event) + "\n")
