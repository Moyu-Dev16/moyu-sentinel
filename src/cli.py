"""
Moyu-Sentinel CLI & Operator Terminal.
Provides command-line diagnostics, audit verification, and live transaction simulations.
"""

import sys
import json
import argparse
import struct
import base64
from typing import Dict, Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


from .sentinel import MoyuSentinel, PolicyConfig
from .svm_guard import SYSTEM_PROGRAM_ID, TOKEN_PROGRAM_ID

def cmd_status(sentinel: MoyuSentinel):
    print("=" * 65)
    print("🛡️  MOYU-SENTINEL: SOLANA AGENT DEFENSE & TELEMETRY MESH")
    print("=" * 65)
    status = sentinel.get_status_overview()
    print(f"🔑 Signer Enclave PubKey : {status['signer_pubkey']}")
    print(f"⚡ Current Solana Slot   : {status['telemetry']['slot']}")
    print(f"🧱 Recent Blockhash      : {status['telemetry']['blockhash'][:24]}...")
    print(f"⏱️  RPC Latency          : {status['telemetry']['rpc_latency_ms']} ms")
    print(f"🎯 Cache Hit Rate        : {status['telemetry']['cache_hit_rate'] * 100:.1f}%")
    print("-" * 65)
    print(f"🖥️  Workstation Hardware  : CPU {status['hardware']['cpu_percent']}% | RAM {status['hardware']['ram_used_gb']}/{status['hardware']['ram_total_gb']} GB ({status['hardware']['ram_percent']}%)")
    print(f"🔒 Audit Chain Health    : {'[VALID]' if status['audit_chain']['is_intact'] else '[BROKEN]'} {status['audit_chain']['verification_message']}")
    print(f"💰 Rolling Daily Spent   : {status['policy']['daily_spent_lamports'] / 1e9:.3f} / {status['policy']['max_daily_lamports'] / 1e9:.1f} SOL")
    print("=" * 65)

def cmd_audit(sentinel: MoyuSentinel):
    print("Verifying audit chain integrity...")
    is_valid, msg = sentinel.audit.verify_chain_integrity()
    print(f"Verification result: {'PASSED' if is_valid else 'FAILED'}")
    print(f"Details: {msg}")
    print("\nRecent Ledger Entries:")
    entries = sentinel.audit.get_recent_entries(5)
    for e in entries:
        print(f"  #{e.index:03d} [{e.event_type}] Hash: {e.hash[:16]}... Prev: {e.prev_hash[:16]}...")

def cmd_demo(sentinel: MoyuSentinel):
    print("=" * 65)
    print("🚀 RUNNING MOYU-SENTINEL BATTLE-TEST SUITE DEMO")
    print("=" * 65)

    # 1. Safe Native Transfer
    print("\n[Scenario 1] Safe Agent Swap/Transfer (0.5 SOL)")
    safe_data = struct.pack("<IQ", 2, 500_000_000)
    safe_ix = [{"program_id": SYSTEM_PROGRAM_ID, "accounts": ["Sender", "Recipient"], "data": safe_data}]
    res1 = sentinel.process_agent_proposal("prop_safe_001", safe_ix)
    print(f"  Verdict: {res1.status} (Approved={res1.approved})")
    if res1.receipt:
        print(f"  Signature: {res1.receipt.signature_base58[:32]}...")

    # 2. Threat: SetAuthority Hijack
    print("\n[Scenario 2] Phishing Threat: Token SetAuthority Takeover Attempt")
    threat_data = bytes([6, 0, 0, 0])
    threat_ix = [{"program_id": TOKEN_PROGRAM_ID, "accounts": ["TokenAccount", "Attacker"], "data": threat_data}]
    res2 = sentinel.process_agent_proposal("prop_attack_002", threat_ix)
    print(f"  Verdict: {res2.status} (Approved={res2.approved})")
    print(f"  Intercepted Reasons: {res2.reasons}")

    # 3. Policy Limit Violation (100 SOL transfer on 5 SOL cap)
    print("\n[Scenario 3] Policy Violation: Excessive Spend (100 SOL)")
    whale_data = struct.pack("<IQ", 2, 100_000_000_000)
    whale_ix = [{"program_id": SYSTEM_PROGRAM_ID, "accounts": ["Sender", "Destination"], "data": whale_data}]
    res3 = sentinel.process_agent_proposal("prop_whale_003", whale_ix)
    print(f"  Verdict: {res3.status} (Approved={res3.approved})")
    print(f"  Intercepted Reasons: {res3.reasons}")

    # 4. Slot Drift Desync (Lagging 200 slots)
    print("\n[Scenario 4] State Desync: Stale Blockhash Slot Lag (>150 slots)")
    current_slot, _ = sentinel.telemetry.get_latest_slot_and_blockhash()
    stale_slot = current_slot - 200
    res4 = sentinel.process_agent_proposal("prop_stale_004", safe_ix, reference_slot=stale_slot)
    print(f"  Verdict: {res4.status} (Approved={res4.approved})")
    print(f"  Intercepted Reasons: {res4.reasons}")

    # 5. Audit Chain Verification
    print("\n[Scenario 5] Cryptographic Audit Chain Verification")
    valid, audit_msg = sentinel.audit.verify_chain_integrity()
    print(f"  Chain Integrity: {'100% VERIFIED' if valid else 'COMPROMISED'}")
    print(f"  Audit Report: {audit_msg}")
    print("=" * 65)

def main():
    parser = argparse.ArgumentParser(description="Moyu-Sentinel CLI")
    parser.add_argument("command", choices=["status", "audit", "demo"], default="status", nargs="?")
    parser.add_argument("--offline", action="store_true", help="Run with offline simulated telemetry")
    args = parser.parse_args()

    sentinel = MoyuSentinel(offline_telemetry=args.offline)

    if args.command == "status":
        cmd_status(sentinel)
    elif args.command == "audit":
        cmd_audit(sentinel)
    elif args.command == "demo":
        cmd_demo(sentinel)

if __name__ == "__main__":
    main()
