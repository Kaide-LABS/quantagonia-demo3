import os
import sys
import json
import argparse
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

def notify(action: str, run_dir: str, channel: str = None, thread_ts: str = None):
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("SLACK_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)
        
    client = WebClient(token=token)
    
    # Try to load existing thread context
    thread_file = os.path.join(run_dir, 'slack_thread.json')
    if not channel or not thread_ts:
        if os.path.exists(thread_file):
            with open(thread_file, 'r') as f:
                data = json.load(f)
                channel = channel or data.get("channel")
                thread_ts = thread_ts or data.get("thread_ts")
                
    if not channel:
        channel = os.environ.get("SLACK_CHANNEL", "decisionai-intake")
        
    request_id = os.path.basename(os.path.normpath(run_dir))
    
    blocks = []
    text = f"Notification for request {request_id}"
    
    if action == "intake":
        text = f"Processing request {request_id}"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Intake:* Processing request `{request_id}`"}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": "Files detected and parsing initiated."}]}
        ]
    elif action == "preview":
        text = "Extraction Preview"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Extraction Preview* for `{request_id}`"}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": "Awaiting human review. Reply APPROVE to proceed."}]}
        ]
    elif action == "validation":
        # Load validation_report.json
        report_path = os.path.join(run_dir, 'validation_report.json')
        if os.path.exists(report_path):
            with open(report_path, 'r') as f:
                report = json.load(f)
            passed = report.get("passed", False)
            status = "✅ PASSED" if passed else "❌ FAILED"
            text = f"Validation {status}"
            blocks = [
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*Validation Report:* {status}"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"Errors: {len(report.get('errors', []))} | Warnings: {len(report.get('warnings', []))}"}}
            ]
    elif action == "artifacts":
        text = "Artifacts Compiled"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Compiled `problem.mps`. Ready for submission?"}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": "Move to approved/ or reply APPROVE."}]}
        ]
    elif action == "submitted":
        text = "Submitted to HybridSolver"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"🚀 *Submitted to HybridSolver*"}}
        ]
    elif action == "progress":
        text = "Solver Progress"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"⏳ *Solver Progress Update*"}}
        ]
    elif action == "completed":
        text = "Solver Completed"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"🏁 *Solver Completed*"}}
        ]
    elif action == "error":
        text = "Error encountered"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"⚠️ *Error encountered in pipeline*"}}
        ]
    # Phase 2 additions
    elif action == "plan_detected":
        text = "Detected multi-stage optimization"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Detected multi-stage optimization. Reply APPROVE to execute."}}
        ]
    elif action == "stage_started":
        text = "Starting stage"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Starting stage..."}}
        ]
    elif action == "stage_complete":
        text = "Stage complete"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Stage complete. Objective/gap updated."}}
        ]
    elif action == "qubo_result":
        text = "QUBO comparison"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"QUBO comparison complete."}}
        ]
    elif action == "reformulating":
        text = "Reformulating stage"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Stage failed, attempting reformulation."}}
        ]
    elif action == "plan_complete":
        text = "Plan complete"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Plan complete."}}
        ]
    elif action == "memory_learned":
        text = "Memory learned"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Learned facts."}}
        ]
    else:
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": f"Unknown action: {action}"}}]

    try:
        if thread_ts:
            response = client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text, blocks=blocks)
        else:
            response = client.chat_postMessage(channel=channel, text=text, blocks=blocks)
            # Save thread info
            with open(thread_file, 'w') as f:
                json.dump({"channel": channel, "thread_ts": response["ts"]}, f)
    except SlackApiError as e:
        print(f"Slack API error: {e.response['error']}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["intake", "preview", "validation", "artifacts", "submitted", "progress", "completed", "error", "plan_detected", "stage_started", "stage_complete", "qubo_result", "reformulating", "plan_complete", "memory_learned"])
    parser.add_argument("run_dir")
    parser.add_argument("--channel")
    parser.add_argument("--thread-ts")
    args = parser.parse_args()
    
    notify(args.action, args.run_dir, args.channel, args.thread_ts)
