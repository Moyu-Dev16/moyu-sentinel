import struct
import pytest
from src.sentinel import MoyuSentinel, PolicyConfig
from src.svm_guard import SYSTEM_PROGRAM_ID, TOKEN_PROGRAM_ID

def test_sentinel_end_to_end_safe_proposal(tmp_path):
    audit_file = str(tmp_path / "e2e_audit.jsonl")
    sentinel = MoyuSentinel(
        policy_config=PolicyConfig(max_lamports_per_tx=2_000_000_000),
        audit_path=audit_file,
        offline_telemetry=True
    )

    # 1. Proposal for 0.5 SOL transfer
    safe_data = struct.pack("<IQ", 2, 500_000_000)
    instructions = [{
        "program_id": SYSTEM_PROGRAM_ID,
        "accounts": ["AgentWallet", "WhitelistedDexVault"],
        "data": safe_data
    }]

    result = sentinel.process_agent_proposal(
        proposal_id="prop_test_001",
        instructions=instructions,
        destination_accounts=["WhitelistedDexVault"]
    )

    assert result.approved is True
    assert result.status == "APPROVED_AND_SIGNED"
    assert result.receipt is not None
    assert result.receipt.verified is True
    assert result.audit_hash is not None

    # Check that audit chain recorded this event and remains intact
    is_valid, msg = sentinel.audit.verify_chain_integrity()
    assert is_valid is True

def test_sentinel_end_to_end_blocked_set_authority(tmp_path):
    audit_file = str(tmp_path / "e2e_audit_block.jsonl")
    sentinel = MoyuSentinel(audit_path=audit_file, offline_telemetry=True)

    # Malicious attempt to change token authority
    malicious_data = bytes([6, 0, 0, 0])
    instructions = [{
        "program_id": TOKEN_PROGRAM_ID,
        "accounts": ["VaultTokenAccount", "AttackerDrainerKey"],
        "data": malicious_data
    }]

    result = sentinel.process_agent_proposal(
        proposal_id="prop_drain_attack",
        instructions=instructions
    )

    assert result.approved is False
    assert result.status == "REJECTED_AST_THREAT"
    assert result.receipt is None
    assert any("AUTHORITY_TAKEOVER" in r for r in result.reasons)

    # Verify audit chain records the rejection and remains intact
    is_valid, msg = sentinel.audit.verify_chain_integrity()
    assert is_valid is True

def test_sentinel_end_to_end_slot_drift_halt(tmp_path):
    audit_file = str(tmp_path / "e2e_audit_drift.jsonl")
    sentinel = MoyuSentinel(audit_path=audit_file, offline_telemetry=True)

    current_slot, _ = sentinel.telemetry.get_latest_slot_and_blockhash()
    stale_reference_slot = current_slot - 180 # 180 slots lag

    safe_data = struct.pack("<IQ", 2, 100_000_000)
    instructions = [{
        "program_id": SYSTEM_PROGRAM_ID,
        "accounts": ["A", "B"],
        "data": safe_data
    }]

    result = sentinel.process_agent_proposal(
        proposal_id="prop_stale_slot",
        instructions=instructions,
        reference_slot=stale_reference_slot
    )

    assert result.approved is False
    assert result.status == "REJECTED_SLOT_DRIFT"
    assert result.receipt is None
    assert any("State desync / slot drift" in r for r in result.reasons)
