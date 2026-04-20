import os
import json
import time
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class CircuitBreakerOpenException(Exception):
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int, recovery_timeout: int, name: str, state_file: str = "~/opt-workspace/.circuit_breakers.json"):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.state_file = os.path.expanduser(state_file)

    def _load_state(self):
        if not os.path.exists(self.state_file):
            return {"state": "CLOSED", "failures": 0, "last_failure_time": 0}
        with open(self.state_file, 'r') as f:
            data = json.load(f)
            return data.get(self.name, {"state": "CLOSED", "failures": 0, "last_failure_time": 0})

    def _save_state(self, state):
        data = {}
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
            except Exception:
                pass
        data[self.name] = state
        # Atomic write
        tmp_file = self.state_file + ".tmp"
        with open(tmp_file, 'w') as f:
            json.dump(data, f)
        os.replace(tmp_file, self.state_file)

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            state = self._load_state()
            now = time.time()
            
            if state["state"] == "OPEN":
                if now - state["last_failure_time"] > self.recovery_timeout:
                    state["state"] = "HALF_OPEN"
                    self._save_state(state)
                else:
                    raise CircuitBreakerOpenException(f"Circuit {self.name} is OPEN")
                    
            try:
                result = func(*args, **kwargs)
                if state["state"] == "HALF_OPEN" or state["failures"] > 0:
                    state["state"] = "CLOSED"
                    state["failures"] = 0
                    self._save_state(state)
                return result
            except Exception as e:
                state["failures"] += 1
                state["last_failure_time"] = now
                if state["failures"] >= self.failure_threshold or state["state"] == "HALF_OPEN":
                    state["state"] = "OPEN"
                self._save_state(state)
                raise e
        return wrapper

class RateLimiter:
    def __init__(self, requests_per_minute: int, name: str):
        self.rpm = requests_per_minute
        self.name = name
        
    def acquire(self):
        # A simple sleep for demo blueprint
        # Real impl would use a token bucket in Redis or a shared sqlite file
        time.sleep(60.0 / self.rpm if self.rpm > 0 else 0)

def with_retry(max_attempts=3, backoff_base=2.0, backoff_max=30.0):
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=backoff_base, max=backoff_max),
        retry=retry_if_exception_type(Exception) # Specific errors in prod
    )
