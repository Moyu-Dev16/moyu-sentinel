"""
Verifiable Cryptographic Audit Ledger for Moyu-Sentinel.
Maintains a tamper-evident, SHA-256 hash-chained JSONL record of all agent proposals,
inspections, policy verdicts, simulations, and cryptographic signatures.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import os
import time
import json
import hashlib

@dataclass
class AuditEntry:
    index: int
    timestamp_ms: int
    event_type: str
    data: Dict[str, Any]
    prev_hash: str
    hash: str

class AuditLedger:
    """
    Append-only cryptographically linked audit chain.
    """

    GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

    def __init__(self, ledger_path: Optional[str] = None):
        self.ledger_path = ledger_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sentinel_audit.jsonl"
        )
        self._last_hash = self.GENESIS_HASH
        self._last_index = -1
        self._load_tip()

    def _compute_hash(self, index: int, timestamp_ms: int, event_type: str, data: Dict[str, Any], prev_hash: str) -> str:
        serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
        blob = f"{index}:{timestamp_ms}:{event_type}:{serialized}:{prev_hash}".encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def _load_tip(self):
        """Read the last entry from the ledger file to set the tip state."""
        if not os.path.exists(self.ledger_path):
            return

        with open(self.ledger_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            if lines:
                try:
                    last_obj = json.loads(lines[-1])
                    self._last_index = last_obj.get("index", -1)
                    self._last_hash = last_obj.get("hash", self.GENESIS_HASH)
                except Exception:
                    pass

    def record_event(self, event_type: str, data: Dict[str, Any]) -> AuditEntry:
        """Append a new tamper-evident event to the ledger."""
        now_ms = int(time.time() * 1000)
        new_index = self._last_index + 1
        entry_hash = self._compute_hash(new_index, now_ms, event_type, data, self._last_hash)

        entry = AuditEntry(
            index=new_index,
            timestamp_ms=now_ms,
            event_type=event_type,
            data=data,
            prev_hash=self._last_hash,
            hash=entry_hash
        )

        os.makedirs(os.path.dirname(os.path.abspath(self.ledger_path)), exist_ok=True)
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

        self._last_index = new_index
        self._last_hash = entry_hash
        return entry

    def verify_chain_integrity(self) -> tuple[bool, Optional[str]]:
        """
        Walk through the entire audit log from genesis and verify every cryptographic link.
        Returns (is_valid, failure_reason).
        """
        if not os.path.exists(self.ledger_path):
            return True, "Ledger is empty (genesis state)."

        expected_prev = self.GENESIS_HASH
        expected_index = 0

        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                raw = line.strip()
                if not raw:
                    continue

                try:
                    entry = json.loads(raw)
                except Exception as e:
                    return False, f"Line {line_no}: Corrupted JSON: {e}"

                idx = entry.get("index")
                ts = entry.get("timestamp_ms")
                evt = entry.get("event_type")
                data = entry.get("data", {})
                prev_h = entry.get("prev_hash")
                h = entry.get("hash")

                if idx != expected_index:
                    return False, f"Line {line_no}: Index discontinuity. Expected {expected_index}, found {idx}"

                if prev_h != expected_prev:
                    return False, f"Line {line_no}: Broken prev_hash link. Expected {expected_prev}, found {prev_h}"

                recomputed = self._compute_hash(idx, ts, evt, data, prev_h)
                if recomputed != h:
                    return False, f"Line {line_no}: Tampering detected! Recomputed {recomputed} != Recorded {h}"

                expected_prev = h
                expected_index += 1

        return True, f"All {expected_index} blocks cryptographically verified with 0 anomalies."

    def get_recent_entries(self, count: int = 10) -> List[AuditEntry]:
        """Fetch the latest N entries."""
        if not os.path.exists(self.ledger_path):
            return []

        entries: List[AuditEntry] = []
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
            for line in lines[-count:]:
                try:
                    d = json.loads(line)
                    entries.append(AuditEntry(**d))
                except Exception:
                    pass
        return entries
