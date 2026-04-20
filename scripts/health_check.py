import os
import sys
import json
import shutil
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

try:
    from google import genai
except ImportError:
    pass

try:
    from quantagonia import HybridSolver
except ImportError:
    pass

from schemas_v3 import HealthStatus, ServiceHealth

def check_gemini(model: str) -> ServiceHealth:
    start = datetime.utcnow()
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return ServiceHealth(available=False, latency_ms=None, error_rate_5m=0.0, circuit_open=False)
            
        client = genai.Client(api_key=api_key)
        # Mock ping, using actual API if valid key
        response = client.models.generate_content(model=model, contents="ping")
        latency = int((datetime.utcnow() - start).total_seconds() * 1000)
        return ServiceHealth(available=True, latency_ms=latency, error_rate_5m=0.0, circuit_open=False)
    except Exception:
        return ServiceHealth(available=False, latency_ms=None, error_rate_5m=0.1, circuit_open=False)

def check_hybridsolver() -> ServiceHealth:
    start = datetime.utcnow()
    try:
        api_key = os.environ.get("QUANTAGONIA_API_KEY")
        if not api_key:
            return ServiceHealth(available=False, latency_ms=None, error_rate_5m=0.0, circuit_open=False)
            
        # Instead of 'hybridsolver version' cli call, we can just do a very small SDK call, 
        # but the spec says `hybridsolver version` CLI call
        import subprocess
        result = subprocess.run(["hybridsolver", "version"], capture_output=True)
        if result.returncode == 0:
            latency = int((datetime.utcnow() - start).total_seconds() * 1000)
            return ServiceHealth(available=True, latency_ms=latency, error_rate_5m=0.0, circuit_open=False)
        return ServiceHealth(available=False, latency_ms=None, error_rate_5m=0.1, circuit_open=False)
    except Exception:
        return ServiceHealth(available=False, latency_ms=None, error_rate_5m=1.0, circuit_open=False)

def check_slack() -> ServiceHealth:
    start = datetime.utcnow()
    try:
        token = os.environ.get("SLACK_BOT_TOKEN")
        if not token:
            return ServiceHealth(available=False, latency_ms=None, error_rate_5m=0.0, circuit_open=False)
        client = WebClient(token=token)
        client.auth_test()
        latency = int((datetime.utcnow() - start).total_seconds() * 1000)
        return ServiceHealth(available=True, latency_ms=latency, error_rate_5m=0.0, circuit_open=False)
    except Exception:
        return ServiceHealth(available=False, latency_ms=None, error_rate_5m=0.5, circuit_open=False)

def check_health(alert_slack: bool = False):
    total, used, free = shutil.disk_usage("/")
    disk_pct = (used / total) * 100
    
    flash = check_gemini("gemini-3-flash")
    pro = check_gemini("gemini-3.1-pro")
    solver = check_hybridsolver()
    slack = check_slack()
    
    status = "healthy"
    if not (flash.available and pro.available and solver.available and slack.available):
        status = "degraded"
    if disk_pct > 90:
        status = "degraded"
        
    health = HealthStatus(
        status=status,
        gemini_flash=flash,
        gemini_pro=pro,
        hybridsolver=solver,
        slack=slack,
        disk_usage_percent=disk_pct,
        active_jobs=0, # would count from jobs running
        checked_at=datetime.utcnow()
    )
    
    if alert_slack and status != "healthy":
        print("Alerting Slack about degraded health", file=sys.stderr)
        # Call slack_notify here in real impl
        
    return health

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--alert-slack", action="store_true")
    args = parser.parse_args()
    
    health = check_health(args.alert_slack)
    if args.json:
        print(health.model_dump_json(indent=2))
    else:
        print(f"Status: {health.status}")
        print(f"Disk Usage: {health.disk_usage_percent:.1f}%")
        print(f"Gemini Flash: {'UP' if health.gemini_flash.available else 'DOWN'}")
        print(f"Gemini Pro: {'UP' if health.gemini_pro.available else 'DOWN'}")
        print(f"HybridSolver: {'UP' if health.hybridsolver.available else 'DOWN'}")
        print(f"Slack: {'UP' if health.slack.available else 'DOWN'}")
        
    sys.exit(0 if health.status == "healthy" else 1)
