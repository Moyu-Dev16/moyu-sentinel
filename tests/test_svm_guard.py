import struct
import pytest
from src.svm_guard import (
    SVMGuard,
    SecurityThreatLevel,
    ThreatCategory,
    SYSTEM_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    COMPUTE_BUDGET_PROGRAM_ID,
    JUPITER_V6_PROGRAM_ID
)

def test_system_transfer_safe():
    guard = SVMGuard(max_lamports_per_tx=1_000_000_000) # 1 SOL max
    data = struct.pack("<IQ", 2, 500_000_000) # 0.5 SOL
    parsed = guard.inspect_instruction(SYSTEM_PROGRAM_ID, ["Sender", "Recipient"], data)
    assert parsed.threat_level == SecurityThreatLevel.SAFE
    assert parsed.params["lamports"] == 500_000_000

def test_system_transfer_excessive():
    guard = SVMGuard(max_lamports_per_tx=1_000_000_000) # 1 SOL max
    data = struct.pack("<IQ", 2, 5_000_000_000) # 5 SOL
    parsed = guard.inspect_instruction(SYSTEM_PROGRAM_ID, ["Sender", "Recipient"], data)
    assert parsed.threat_level == SecurityThreatLevel.CRITICAL
    assert parsed.threat_category == ThreatCategory.EXCESSIVE_TRANSFER

def test_system_transfer_zero_value():
    guard = SVMGuard()
    data = struct.pack("<IQ", 2, 0)
    parsed = guard.inspect_instruction(SYSTEM_PROGRAM_ID, ["Sender", "Recipient"], data)
    assert parsed.threat_level == SecurityThreatLevel.WARNING
    assert parsed.threat_category == ThreatCategory.ZERO_VALUE_GRIEFING

def test_system_assign_hijack():
    guard = SVMGuard()
    data = struct.pack("<I", 1) # SystemProgram.Assign
    parsed = guard.inspect_instruction(SYSTEM_PROGRAM_ID, ["TargetAccount"], data)
    assert parsed.threat_level == SecurityThreatLevel.CRITICAL
    assert parsed.threat_category == ThreatCategory.SYSTEM_ASSIGN_HIJACK

def test_token_set_authority_trap():
    guard = SVMGuard()
    data = bytes([6, 0, 0, 0]) # Disc 6: SetAuthority
    parsed = guard.inspect_instruction(TOKEN_PROGRAM_ID, ["TokenAccount", "NewAuthority"], data)
    assert parsed.threat_level == SecurityThreatLevel.CRITICAL
    assert parsed.threat_category == ThreatCategory.AUTHORITY_TAKEOVER

def test_token_close_account():
    guard = SVMGuard()
    data = bytes([9, 0]) # Disc 9: CloseAccount
    parsed = guard.inspect_instruction(TOKEN_PROGRAM_ID, ["TokenAccount", "Destination"], data)
    assert parsed.threat_level == SecurityThreatLevel.WARNING
    assert parsed.threat_category == ThreatCategory.ACCOUNT_CLOSE_DRAIN

def test_token_transfer_checked_safe():
    guard = SVMGuard()
    data = struct.pack("<BQB", 12, 100_000, 6) # Disc 12, 100000 units, 6 decimals
    parsed = guard.inspect_instruction(TOKEN_PROGRAM_ID, ["From", "Mint", "To", "Owner"], data)
    assert parsed.threat_level == SecurityThreatLevel.SAFE
    assert parsed.params["amount"] == 100_000
    assert parsed.params["decimals"] == 6

def test_unauthorized_program_id():
    guard = SVMGuard()
    malicious_prog = "EvilDrainer11111111111111111111111111111111"
    parsed = guard.inspect_instruction(malicious_prog, ["Victim"], b"\x00")
    assert parsed.threat_level == SecurityThreatLevel.CRITICAL
    assert parsed.threat_category == ThreatCategory.UNAUTHORIZED_PROGRAM

def test_compute_budget_excessive_price():
    guard = SVMGuard()
    # Disc 3, 50,000,000 micro-lamports (excessive)
    data = struct.pack("<BQ", 3, 50_000_000)
    parsed = guard.inspect_instruction(COMPUTE_BUDGET_PROGRAM_ID, [], data)
    assert parsed.threat_level == SecurityThreatLevel.WARNING
    assert parsed.threat_category == ThreatCategory.EXCESSIVE_COMPUTE_PRICE

def test_transaction_multi_instruction_aggregation():
    guard = SVMGuard()
    ix1 = {"program_id": SYSTEM_PROGRAM_ID, "accounts": ["S", "R"], "data": struct.pack("<IQ", 2, 100_000_000)}
    ix2 = {"program_id": JUPITER_V6_PROGRAM_ID, "accounts": ["A", "B"], "data": b"swap_data"}
    report = guard.inspect_transaction([ix1, ix2])
    assert report.is_safe is True
    assert report.highest_threat_level == SecurityThreatLevel.SAFE
    assert report.total_lamports_transferred == 100_000_000
