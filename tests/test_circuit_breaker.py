import pytest
import time
from src.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from src.sentinel import MoyuSentinel, SentinelPipelineResult

def test_circuit_breaker_initial_state():
    cb = CircuitBreaker()
    status = cb.get_status()
    assert status["state"] == "CLOSED"
    assert status["consecutive_failures"] == 0
    can_exec, reason = cb.can_execute()
    assert can_exec is True
    assert reason is None

def test_circuit_breaker_trips_on_consecutive_failures():
    config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout_sec=0.5)
    cb = CircuitBreaker(config)
    
    cb.record_failure("Error 1")
    assert cb.state == CircuitState.CLOSED
    cb.record_failure("Error 2")
    assert cb.state == CircuitState.CLOSED
    cb.record_failure("Error 3")
    assert cb.state == CircuitState.OPEN
    
    can_exec, reason = cb.can_execute()
    assert can_exec is False
    assert "Circuit Breaker TRIPPED" in reason

def test_circuit_breaker_recovers_via_half_open():
    config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout_sec=0.1, consecutive_success_to_close=2)
    cb = CircuitBreaker(config)
    
    cb.record_failure("Err 1")
    cb.record_failure("Err 2")
    assert cb.state == CircuitState.OPEN
    
    time.sleep(0.12)
    # First attempt transitions to HALF_OPEN
    can_exec, _ = cb.can_execute()
    assert can_exec is True
    assert cb.state == CircuitState.HALF_OPEN
    
    # First successful canary
    cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN
    
    # Second successful canary closes circuit
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.get_status()["state"] == "CLOSED"

def test_circuit_breaker_canary_failure_re_trips():
    config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout_sec=0.1, consecutive_success_to_close=2)
    cb = CircuitBreaker(config)
    
    cb.trip("Manual test trip")
    assert cb.state == CircuitState.OPEN
    
    time.sleep(0.12)
    can_exec, _ = cb.can_execute()
    assert can_exec is True
    assert cb.state == CircuitState.HALF_OPEN
    
    # Canary fails!
    cb.record_failure("Canary exploded")
    assert cb.state == CircuitState.OPEN
    assert "Canary execution failed" in cb.tripped_reason

def test_sentinel_pipeline_circuit_breaker_integration(tmp_path):
    audit_file = str(tmp_path / "test_audit.jsonl")
    sentinel = MoyuSentinel(
        audit_path=audit_file,
        offline_telemetry=True,
        circuit_breaker_config=CircuitBreakerConfig(failure_threshold=2, recovery_timeout_sec=1.0)
    )
    
    malicious_ix = [{
        "programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "data": "06000000", # SetAuthority drainer
        "accounts": ["VictimPubkey1111111111111111111111111111111", "AttackerPubkey111111111111111111111111111111"]
    }]
    
    # First attack rejected
    res1 = sentinel.process_agent_proposal("attack-01", malicious_ix)
    assert res1.status == "REJECTED_AST_THREAT"
    assert sentinel.circuit_breaker.state == CircuitState.CLOSED
    
    # Second attack rejected -> trips circuit breaker
    res2 = sentinel.process_agent_proposal("attack-02", malicious_ix)
    assert res2.status == "REJECTED_AST_THREAT"
    assert sentinel.circuit_breaker.state == CircuitState.OPEN
    
    # Third request blocked immediately by Circuit Breaker without inspecting instructions
    res3 = sentinel.process_agent_proposal("tx-03", [])
    assert res3.status == "REJECTED_CIRCUIT_BREAKER_OPEN"
    assert res3.approved is False
    assert "Circuit Breaker TRIPPED" in res3.reasons[0]

def test_circuit_breaker_manual_trip_and_reset():
    cb = CircuitBreaker()
    cb.trip("Security audit emergency pause")
    assert cb.state == CircuitState.OPEN
    can_exec, reason = cb.can_execute()
    assert can_exec is False
    assert "Security audit emergency pause" in reason

    cb.reset()
    assert cb.state == CircuitState.CLOSED
    can_exec, _ = cb.can_execute()
    assert can_exec is True

def test_circuit_breaker_anomaly_rate_threshold():
    # 40% failure threshold over rolling window (minimum 5 events)
    config = CircuitBreakerConfig(failure_threshold=10, max_anomaly_rate=0.4)
    cb = CircuitBreaker(config)

    # 3 successes
    cb.record_success()
    cb.record_success()
    cb.record_success()
    assert cb.state == CircuitState.CLOSED

    # 2 failures (2 out of 5 = 40% -> still at threshold)
    cb.record_failure("Transient error 1")
    cb.record_failure("Transient error 2")
    assert cb.state == CircuitState.CLOSED

    # 1 more failure (3 out of 6 = 50% -> exceeds 40%)
    cb.record_failure("Transient error 3")
    assert cb.state == CircuitState.OPEN
    assert "Anomaly rate" in cb.tripped_reason

