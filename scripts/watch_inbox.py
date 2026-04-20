import os
import sys
import glob
import json
import shutil
import datetime
import re

def detect_new_requests(workspace_root: str):
    inbox_pattern = os.path.join(workspace_root, 'clients', '*', 'inbox', '*')
    folders = glob.glob(inbox_pattern)
    
    new_requests = 0
    for folder in folders:
        if not os.path.isdir(folder):
            continue
            
        files = []
        for root, _, filenames in os.walk(folder):
            for filename in filenames:
                path = os.path.join(root, filename)
                files.append({
                    "name": filename,
                    "size_bytes": os.path.getsize(path),
                    "type": os.path.splitext(filename)[1].lower().strip('.') or 'unknown'
                })
                
        if not files:
            continue
            
        # extract account
        parts = folder.split(os.sep)
        account = parts[-3]
        raw_name = parts[-1]
        
        request_id = re.sub(r'[^a-z0-9]+', '-', raw_name.lower()).strip('-')
        
        staging_dir = os.path.join(workspace_root, 'clients', account, 'staging', request_id)
        runs_dir = os.path.join(workspace_root, 'clients', account, 'runs', request_id)
        
        if os.path.exists(staging_dir) or os.path.exists(runs_dir):
            continue
            
        os.makedirs(staging_dir, exist_ok=True)
        # Move files to staging
        for root, _, filenames in os.walk(folder):
            for filename in filenames:
                src = os.path.join(root, filename)
                dst = os.path.join(staging_dir, filename)
                shutil.move(src, dst)
        
        try:
            shutil.rmtree(folder)
        except:
            pass
            
        print(json.dumps({
            "event": "new_request",
            "account": account,
            "request_id": request_id,
            "files": files,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }))
        new_requests += 1

    print(json.dumps({
        "event": "scan_complete",
        "new_requests": new_requests,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }))
    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: watch_inbox.py <workspace_root>", file=sys.stderr)
        sys.exit(2)
        
    detect_new_requests(sys.argv[1])
