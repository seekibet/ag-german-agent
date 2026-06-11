"""Trace-first workflow: every agent run logs a full JSON trace."""
import json
import os
import time
import uuid


class Tracer:
    def __init__(self, traces_dir: str = "traces"):
        self.dir = traces_dir
        os.makedirs(traces_dir, exist_ok=True)

    def new_trace(self, question: str) -> dict:
        return {
            "trace_id": uuid.uuid4().hex[:12],
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "question": question,
            "steps": [],
        }

    def log_step(self, trace: dict, name: str, **payload):
        trace["steps"].append({"step": name, "t": time.time(), **payload})

    def save(self, trace: dict) -> str:
        path = os.path.join(self.dir, f"trace_{trace['trace_id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(trace, f, indent=2, ensure_ascii=False)
        return path
