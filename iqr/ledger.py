"""Run ledger: every node, tool call, and model call logged, replayable.

This ledger is the ITGC evidence for the platform itself.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from iqr import config


class RunLedger:
    def __init__(self, run_id: str):
        self.run_id = run_id
        config.ensure_dirs()
        self.path = config.RUN_LEDGER_DIR / f"{run_id}.jsonl"
        self._lock = threading.Lock()

    def log(self, event: str, **payload) -> None:
        record = {"run_id": self.run_id, "event": event,
                  "ts": datetime.now(timezone.utc).isoformat(), **payload}
        with self._lock:
            with open(self.path, "a") as f:
                f.write(json.dumps(record, default=str) + "\n")

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line]
