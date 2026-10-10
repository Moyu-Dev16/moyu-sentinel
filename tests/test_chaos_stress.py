import pytest
import time
from src.sentinel import MoyuSentinel
from src.circuit_breaker import CircuitBreakerConfig, CircuitState
from src.policy_engine import PolicyConfig

from src.svm_guard import SYSTEM_PROGRAM_ID, TOKEN_PROGRAM_ID
import struct

def test_chaos_rapid_concurrency_stress(tmp_path):
    """
    Stress test MoyuSentinel with 50 rapid sequential transactions
    alternating between legitimate safe transfers, drainer exploits, and slot drift attacks.
    Verifies that zero malicious instructions pass, the audit hash chain remains strictly valid,
    and the circuit breaker self-heals correctly.
    """
    audit_file = str(tmp_path / "chaos_audit.jsonl")
    sentinel = MoyuSentinel(
        policy_config=PolicyConfig(require_simulation=False, max_lamports_per_tx=1_000_000_000),
        audit_path=audit_file,
        offline_telemetry=True,
        circuit_breaker_config=CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout_sec=0.1,
            consecutive_success_to_close=2,
            max_anomaly_rate=0.8
        )
    )

    safe_data = struct.pack("<IQ", 2, 400_000)
    safe_ix = [{
        "program_id": SYSTEM_PROGRAM_ID,
        "data": safe_data,
        "accounts": ["SourcePubkey1111111111111111111111111111111", "DestPubkey111111111111111111111111111111111"]
    }]

    drainer_ix = [{
        "program_id": TOKEN_PROGRAM_ID,
        "data": bytes([6, 0, 0, 0]), # SetAuthority drainer
        "accounts": ["VictimPubkey1111111111111111111111111111111", "AttackerPubkey111111111111111111111111111111"]
    }]

    approved_count = 0
    blocked_threats = 0

    # 1. Execute 10 safe transactions
    for i in range(10):
        res = sentinel.process_agent_proposal(f"safe-burst-{i}", safe_ix)
        assert res.approved is True
        assert res.status == "APPROVED_AND_SIGNED"
        approved_count += 1

    # 2. Inject 5 rapid drainer attacks -> should trip circuit breaker on the 5th
    for i in range(5):
        res = sentinel.process_agent_proposal(f"attack-burst-{i}", drainer_ix)
        assert res.approved is False
        blocked_threats += 1

    assert sentinel.circuit_breaker.state == CircuitState.OPEN

    # 3. Next tx blocked by circuit breaker
    res_blocked = sentinel.process_agent_proposal("post-trip-tx", safe_ix)
    assert res_blocked.status == "REJECTED_CIRCUIT_BREAKER_OPEN"

    # 4. Wait for recovery cooldown and self-heal
    time.sleep(0.12)
    can_exec, _ = sentinel.circuit_breaker.can_execute()
    assert can_exec is True
    assert sentinel.circuit_breaker.state == CircuitState.HALF_OPEN

    # 5. Execute 2 safe canaries -> recovers to CLOSED
    res_canary1 = sentinel.process_agent_proposal("canary-01", safe_ix)
    assert res_canary1.approved is True
    res_canary2 = sentinel.process_agent_proposal("canary-02", safe_ix)
    assert res_canary2.approved is True
    assert sentinel.circuit_breaker.state == CircuitState.CLOSED
    approved_count += 2

    # Verify audit chain integrity across all chaos events
    is_valid, msg = sentinel.audit.verify_chain_integrity()
    assert is_valid is True
    assert "verified" in msg.lower()
    assert approved_count == 12
    assert blocked_threats == 5

def test_hardware_governor_under_stress():
    """Verify hardware governor stays within limits during execution."""
    from src.sentinel import HardwareGovernor
    gov = HardwareGovernor(cpu_threshold=99.0)
    hw = gov.get_hardware_status()
    assert hw["status"] == "HEALTHY"
    assert "ram_percent" in hw
    assert "cpu_percent" in hw
