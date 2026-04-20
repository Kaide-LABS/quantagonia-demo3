import os
import sys
import argparse
from datetime import datetime

def write_memory(action: str, run_dir: str, workspace: str):
    memory_file = os.path.join(workspace, 'MEMORY.md')
    date_str = datetime.utcnow().strftime('%Y-%m-%d')
    daily_file = os.path.join(workspace, 'memory', f'{date_str}.md')
    os.makedirs(os.path.dirname(daily_file), exist_ok=True)
    
    timestamp = datetime.utcnow().isoformat()
    
    if action == "stage_complete":
        # Simplified memory update
        update = f"\n### {timestamp} - Stage Complete in {run_dir}\n- Stage finished successfully.\n"
        with open(daily_file, 'a') as f:
            f.write(update)
            
    elif action == "plan_complete":
        update = f"\n### Plan Complete: {run_dir}\n- Plan execution finished.\n"
        with open(daily_file, 'a') as f:
            f.write(update)
            
        mem_update = f"\n## Client Execution {date_str}\n- Execution completed for {run_dir}\n"
        with open(memory_file, 'a') as f:
            f.write(mem_update)
            
    elif action == "qubo_comparison":
        update = f"\n### QUBO Comparison\n- Compared QUBO vs MIP for {run_dir}\n"
        with open(memory_file, 'a') as f:
            f.write(update)
            
    elif action == "reformulation_learned":
        update = f"\n### Reformulation Learned\n- Reformulation succeeded in {run_dir}\n"
        with open(memory_file, 'a') as f:
            f.write(update)
            
    elif action == "client_terminology":
        update = f"\n### Terminology Learned\n- Found new terminology in {run_dir}\n"
        with open(memory_file, 'a') as f:
            f.write(update)

    print(f"Memory updated for {action}")
    sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["stage_complete", "plan_complete", "qubo_comparison", "reformulation_learned", "client_terminology"])
    parser.add_argument("run_dir")
    parser.add_argument("--workspace", default=os.path.expanduser("~/opt-workspace"))
    args = parser.parse_args()
    
    write_memory(args.action, args.run_dir, args.workspace)
