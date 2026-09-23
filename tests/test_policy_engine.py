import pytest
from src.svm_guard import InspectionReport, SecurityThreatLevel
from src.policy_engine import PolicyEngine, PolicyConfig, PolicyDecision

def test_policy_approved_normal():
    config = PolicyConfig(max_lamports_per_tx=2_000_000_000, max_daily_lamports=10_000_000_000)
    engine = PolicyEngine(config)

    report = InspectionReport(
        is_safe=True,
        highest_threat_level=SecurityThreatLevel.SAFE,
        total_lamports_transferred=1_000_000_000
    )
    sim = {"err": None, "unitsConsumed": 2000}

    verdict = engine.evaluate(report, simulation_result=sim)
    assert verdict.approved is True
    assert verdict.decision == PolicyDecision.APPROVED
    assert verdict.approval_token is not None

def test_policy_per_tx_cap_violation():
    config = PolicyConfig(max_lamports_per_tx=1_000_000_000)
    engine = PolicyEngine(config)

    report = InspectionReport(
        is_safe=True,
        highest_threat_level=SecurityThreatLevel.SAFE,
        total_lamports_transferred=2_000_000_000
    )
    sim = {"err": None}

    verdict = engine.evaluate(report, simulation_result=sim)
    assert verdict.approved is False
    assert verdict.decision == PolicyDecision.REJECTED
    assert any("Per-transaction spend limit" in r for r in verdict.reasons)

def test_policy_daily_quota_exhaustion():
    config = PolicyConfig(max_lamports_per_tx=5_000_000_000, max_daily_lamports=6_000_000_000)
    engine = PolicyEngine(config)

    # Record prior spends of 5 SOL
    engine.record_spend(5_000_000_000)
    assert engine.get_rolling_daily_spent() == 5_000_000_000

    # Next attempt tries 2 SOL (5 + 2 = 7 > 6 SOL daily max)
    report = InspectionReport(
        is_safe=True,
        highest_threat_level=SecurityThreatLevel.SAFE,
        total_lamports_transferred=2_000_000_000
    )
    verdict = engine.evaluate(report, simulation_result={"err": None})
    assert verdict.approved is False
    assert any("Rolling 24h spend quota exceeded" in r for r in verdict.reasons)

def test_policy_blocked_recipient():
    engine = PolicyEngine(PolicyConfig(blocked_recipients={"MaliciousDrainerPool1111111111111111"}))
    report = InspectionReport(is_safe=True, highest_threat_level=SecurityThreatLevel.SAFE)
    verdict = engine.evaluate(report, destination_accounts=["MaliciousDrainerPool1111111111111111"], simulation_result={"err": None})
    assert verdict.approved is False
    assert any("blocked recipients blacklist" in r for r in verdict.reasons)

def test_policy_simulation_failure_fail_closed():
    engine = PolicyEngine(PolicyConfig(require_simulation=True))
    report = InspectionReport(is_safe=True, highest_threat_level=SecurityThreatLevel.SAFE)

    # Simulation returned an InstructionError
    sim_error = {"err": {"InstructionError": [0, "Custom(1)"]}}
    verdict = engine.evaluate(report, simulation_result=sim_error)
    assert verdict.approved is False
    assert any("simulation failed" in r for r in verdict.reasons)
