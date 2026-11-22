"""Thread-safe and privacy-conscious structured JSONL logging for CRM transcripts and callbacks."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from riverwood.security import mask_phone_number


def now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


class JsonlLogger:
    """Thread-safe logger writing JSON lines with optional PII redaction."""

    def __init__(self, path: Path, mask_pii: bool = True) -> None:
        self.path = path
        self.mask_pii = mask_pii
        self._lock = threading.Lock()

    def write(self, payload: Dict[str, Any]) -> None:
        """Write record to JSONL file safely with thread locking."""
        data = dict(payload)
        if self.mask_pii and "caller" in data and data["caller"]:
            data["caller"] = mask_phone_number(data["caller"])

        if "timestamp" not in data:
            data["timestamp"] = now_iso()

        line = json.dumps(data, ensure_ascii=True) + "\n"

        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(line)
            except Exception as exc:
                print(f"[warn] Failed writing log to {self.path}: {exc}")
