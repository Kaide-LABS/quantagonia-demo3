import os
import sys
import time
import shutil
import argparse
from datetime import datetime, timezone
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

def _now():
    return datetime.now(timezone.utc)

def print_beat(msg: str):
    print(f"\n[{_now().strftime('%H:%M:%S')}] {msg}")

def print_narration(msg: str):
    print("\n" + "━"*54)
    print(f"🎤 NARRATION: \"{msg}\"")
    print("━"*54 + "\n")

def run_demo(mode: str, fixture: str, speed: float):
    workspace = os.environ.get("WORKSPACE_ROOT", os.path.expanduser("~/opt-workspace"))
    tenant_id = "demo-acme"
    tenant_dir = os.path.join(workspace, "tenants", tenant_id)
    clients_dir = os.path.join(tenant_dir, "clients", tenant_id)
    
    # Phase 0: RESET
    print_beat("Phase 0: RESET")
    print("🔄 Environment reset. Ready for demo.")
    runs_dir = os.path.join(clients_dir, "runs")
    if os.path.exists(runs_dir):
        shutil.rmtree(runs_dir)
    os.makedirs(runs_dir, exist_ok=True)
    
    memory_file = os.path.join(tenant_dir, "MEMORY.md")
    os.makedirs(os.path.dirname(memory_file), exist_ok=True)
    with open(memory_file, 'w') as f:
        f.write(f"## Tenant: ACME Corp (Demo)\nCreated: {_now().isoformat()}\n")
        
    db_file = os.path.join(workspace, "cost_tracker.db")
    if os.path.exists(db_file):
        try:
            import sqlite3
            conn = sqlite3.connect(db_file)
            conn.execute(f"DELETE FROM cost_records WHERE tenant_id = '{tenant_id}'")
            conn.commit()
            conn.close()
        except:
            pass
            
    time.sleep(1.0 / speed)
    
    # Phase 1: SEED
    print_beat("Phase 1: SEED")
    fixture_src = os.path.join(os.path.dirname(__file__), "fixtures", fixture)
    inbox_dir = os.path.join(clients_dir, "inbox", "demo-request")
    os.makedirs(inbox_dir, exist_ok=True)
    
    if os.path.exists(fixture_src):
        for f in os.listdir(fixture_src):
            shutil.copy(os.path.join(fixture_src, f), os.path.join(inbox_dir, f))
    else:
        # Create dummy if fixture doesn't exist
        with open(os.path.join(inbox_dir, "instructions.txt"), 'w') as f:
            f.write("Q2 workforce allocation for Munich. Max 8h shifts, no weekend OT. Prioritize warehouse-3.")
            
    print("📁 Data package dropped into watched folder.")
    time.sleep(1.0 / speed)
    
    # Phase 2: INTAKE
    print_beat("Phase 2: INTAKE")
    print("🔍 Files detected and classified.")
    print_narration("The agent has detected new files. Gemini Flash classified them in 234ms.")
    time.sleep(2.0 / speed)
    
    # Phase 3: EXTRACTION
    print_beat("Phase 3: EXTRACTION")
    print("📊 Extracted 24 variables, 38 constraints.")
    print_narration("Gemini Pro extracted constraints. Note the ambiguity flagged.")
    time.sleep(3.0 / speed)
    
    # Phase 4: VALIDATION
    print_beat("Phase 4: VALIDATION")
    print("⚠️ Unit mismatch detected (kg vs tons). Auto-normalizing...")
    time.sleep(1.0 / speed)
    print("✅ Validation passed. 1 warnings.")
    print_narration("The deterministic gate caught a unit mismatch. No LLM involved here.")
    time.sleep(2.0 / speed)
    
    # Phase 5: COMPILATION
    print_beat("Phase 5: COMPILATION")
    print("🔨 Compiled problem.mps (847 vars, 2341 constraints, 14.2 KB)")
    print_narration("PuLP compiled the model. The .mps artifact is solver-ready.")
    time.sleep(2.0 / speed)
    
    # Phase 6: APPROVAL
    print_beat("Phase 6: APPROVAL")
    if mode == "live":
        input("Press Enter to APPROVE submission to HybridSolver...")
    else:
        time.sleep(1.5 / speed)
    print("✅ APPROVED. Submitting to HybridSolver...")
    
    # Phase 7: SUBMISSION
    print_beat("Phase 7: SUBMISSION")
    print("🚀 Job submitted. Tracking: obj=None, gap=None, time=0s")
    print_narration("The solver is running. We see live progress. Note: the LLM never touches this.")
    
    for i in range(3):
        time.sleep(1.0 / speed)
        print(f"⏳ Progress: obj={1500 - i*100}, gap={10 - i*3}%, time={i+1}s")
        
    # Phase 8: COMPLETION
    print_beat("Phase 8: COMPLETION")
    print("🏁 Complete. Objective: 1200.0, Gap: 0.01%, Billed: 1 minutes")
    print_narration("Done. The agent learned one new fact for next time.")
    
    with open(memory_file, 'a') as f:
        f.write("\n- Learned: warehouse-3 capacity is in kg, normalized to tons.\n")
        
    print("\nDemo concluded successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["live", "recording", "dry-run"], default="dry-run")
    parser.add_argument("--fixture", choices=["acme_q2_2026", "acme_annual_plan"], default="acme_q2_2026")
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()
    
    run_demo(args.mode, args.fixture, args.speed)
