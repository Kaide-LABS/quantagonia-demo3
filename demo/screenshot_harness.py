import os
import time
import argparse
from datetime import datetime
try:
    from slack_sdk import WebClient
except ImportError:
    pass

def capture_screenshots(output_dir: str, mode: str):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    
    print(f"Harness armed. Capturing in mode: {mode}")
    
    if mode == "terminal":
        # Usually implemented via `script` command or capturing stdout locally
        log_file = os.path.join(output_dir, f"capture_{timestamp}.log")
        with open(log_file, "w") as f:
            f.write("Demo session captured.")
        print(f"Terminal capture saved to {log_file}")
        
    elif mode == "slack":
        # Slack history export
        token = os.environ.get("SLACK_BOT_TOKEN")
        channel = os.environ.get("SLACK_CHANNEL", "decisionai-intake")
        if not token:
            print("SLACK_BOT_TOKEN required for slack capture")
            return
            
        client = WebClient(token=token)
        try:
            res = client.conversations_history(channel=channel, limit=10)
            dump_file = os.path.join(output_dir, f"slack_{timestamp}.json")
            with open(dump_file, "w") as f:
                import json
                json.dump(res.data, f, indent=2)
            print(f"Slack capture saved to {dump_file}")
        except Exception as e:
            print(f"Slack API Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="demo/captures")
    parser.add_argument("--mode", choices=["terminal", "slack"], required=True)
    args = parser.parse_args()
    
    capture_screenshots(args.output_dir, args.mode)
