import os
import json
import pytest
from src.audit_ledger import AuditLedger

def test_audit_ledger_hash_chaining(tmp_path):
    log_file = str(tmp_path / "test_audit.jsonl")
    ledger = AuditLedger(log_file)

    e0 = ledger.record_event("EVENT_A", {"key": "val1"})
    assert e0.index == 0
    assert e0.prev_hash == AuditLedger.GENESIS_HASH

    e1 = ledger.record_event("EVENT_B", {"key": "val2"})
    assert e1.index == 1
    assert e1.prev_hash == e0.hash

    valid, msg = ledger.verify_chain_integrity()
    assert valid is True
    assert "All 2 blocks cryptographically verified" in msg

def test_audit_ledger_tamper_detection(tmp_path):
    log_file = str(tmp_path / "tamper_test.jsonl")
    ledger = AuditLedger(log_file)

    ledger.record_event("EVENT_1", {"amount": 100})
    ledger.record_event("EVENT_2", {"amount": 200})
    ledger.record_event("EVENT_3", {"amount": 300})

    # Tamper with event 2 in the file
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    entry_2 = json.loads(lines[1])
    entry_2["data"]["amount"] = 9999 # Malicious edit
    lines[1] = json.dumps(entry_2) + "\n"

    with open(log_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # Verification must catch the tampering
    valid, msg = ledger.verify_chain_integrity()
    assert valid is False
    assert "Tampering detected" in msg
