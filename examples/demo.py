import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.sentinel import MoyuSentinel, PolicyConfig
from src.svm_guard import SYSTEM_PROGRAM_ID, TOKEN_PROGRAM_ID

def main():
    print("===============================================================")
    print("   MOYU-SENTINEL: SOLANA AGENT TELEMETRY & EXECUTION MESH      ")
    print("         Built for Colosseum Global Hackathon 2026             ")
    print("===============================================================\n")

    sentinel = MoyuSentinel(
        policy_config=PolicyConfig(max_lamports_per_tx=5_000_000_000),
        offline_telemetry=True
    )

    # Step 1: Workstation Health Sentinel
    print("[1] Inspecting Host Workstation Hardware...")
    hw = sentinel.hardware.get_hardware_status()
    print(f"    -> CPU Usage: {hw['cpu_percent']}% (Health: {hw['status']})")
    print(f"    -> Memory: {hw['ram_used_gb']} GB / {hw['ram_total_gb']} GB ({hw['ram_percent']}%)")
    print(f"    -> Free Disk: {hw['disk_free_gb']} GB\n")

    # Step 2: Telemetry & Slot Cache
    print("[2] Asynchronous Dual-Stream Telemetry & Slot Cache...")
    slot, blockhash = sentinel.telemetry.get_latest_slot_and_blockhash()
    print(f"    -> Current Slot: {slot}")
    print(f"    -> Valid Blockhash: {blockhash[:24]}...")
    print("    -> Jitter Backoff & Slot Drift Guard: ACTIVE\n")

    # Step 3: Safe Transaction Proposal
    print("[3] Evaluating Safe Agent Transaction Proposal (0.5 SOL Transfer)...")
    safe_data = struct.pack("<IQ", 2, 500_000_000)
    safe_ix = [{"program_id": SYSTEM_PROGRAM_ID, "accounts": ["AgentWallet", "Vault"], "data": safe_data}]
    res_safe = sentinel.process_agent_proposal("prop_safe_001", safe_ix)
    print(f"    -> Pipeline Status: {res_safe.status}")
    print(f"    -> Decision: {'APPROVED' if res_safe.approved else 'REJECTED'}")
    if res_safe.receipt:
        print(f"    -> Signer Enclave PubKey: {res_safe.receipt.signer_public_key_base58}")
        print(f"    -> Ed25519 Signature: {res_safe.receipt.signature_base58[:32]}...")
        print(f"    -> Non-Custodial Signature Verified: {res_safe.receipt.verified}\n")

    # Step 4: Intercepting Malicious Drainer Phishing Attack
    print("[4] Simulating Phishing Attack: Malicious Token SetAuthority Takeover...")
    drain_data = bytes([6, 0, 0, 0])
    drain_ix = [{"program_id": TOKEN_PROGRAM_ID, "accounts": ["TokenAccount", "DrainerKey"], "data": drain_data}]
    res_attack = sentinel.process_agent_proposal("prop_drain_attack", drain_ix)
    print(f"    -> Pipeline Status: {res_attack.status}")
    print(f"    -> Decision: {'APPROVED' if res_attack.approved else 'REJECTED'}")
    print(f"    -> Intercepted Threats: {res_attack.reasons}\n")

    # Step 5: Intercepting Slot Drift / State Desync
    print("[5] Simulating State Desynchronization (180 Slots Lag)...")
    res_drift = sentinel.process_agent_proposal("prop_stale", safe_ix, reference_slot=slot - 180)
    print(f"    -> Pipeline Status: {res_drift.status}")
    print(f"    -> Intercepted Reasons: {res_drift.reasons}\n")

    # Step 6: Verifying Cryptographic Audit Ledger
    print("[6] Verifying Tamper-Evident SHA-256 Audit Chain...")
    valid, report = sentinel.audit.verify_chain_integrity()
    print(f"    -> Chain Integrity: {'100% VERIFIED' if valid else 'COMPROMISED'}")
    print(f"    -> Audit Report: {report}\n")

    print("===============================================================")
    print("       MOYU-SENTINEL SECURE WORKFLOW COMPLETED!                ")
    print("===============================================================")

if __name__ == "__main__":
    main()
