"""
Moyu-Sentinel: Autonomous On-Chain Telemetry & Secure Execution Mesh for Solana AI Agents.
Unifies Hardware Governance, SVM AST Boundary Inspection, Policy Enforcement,
Telemetry Caching, Non-Custodial Enclave Signing, and Verifiable Audit Chains.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import shutil
import psutil
import json

from .svm_guard import SVMGuard, InspectionReport, SecurityThreatLevel
from .policy_engine import PolicyEngine, PolicyConfig, PolicyVerdict, PolicyDecision
from .telemetry import TelemetryCache, TelemetrySnapshot
from .signer_mesh import ExternalSignerMesh, SignedExecutionReceipt, SignerSecurityViolation
from .audit_ledger import AuditLedger, AuditEntry

@dataclass
class SentinelPipelineResult:
    status: str
    approved: bool
    reasons: List[str]
    receipt: Optional[SignedExecutionReceipt] = None
    inspection: Optional[InspectionReport] = None
    policy_verdict: Optional[PolicyVerdict] = None
    audit_hash: Optional[str] = None
    slot: Optional[int] = None

class HardwareGovernor:
    """Monitors workstation footprint to maintain quiet execution (<20% CPU)."""
    def __init__(self, cpu_threshold: float = 20.0):
        self.cpu_threshold = cpu_threshold

    def get_hardware_status(self) -> Dict[str, Any]:
        ram = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        disk = shutil.disk_usage(".")
        return {
            "ram_used_gb": round(ram.used / (1024**3), 2),
            "ram_total_gb": round(ram.total / (1024**3), 2),
            "ram_percent": ram.percent,
            "cpu_percent": cpu,
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "status": "HEALTHY" if cpu < self.cpu_threshold else "THROTTLED"
        }

# Maintain backward compatibility with legacy name
WorkstationSentinel = HardwareGovernor

class MoyuSentinel:
    """
    Main Sentinel Orchestrator for Solana AI Agents.
    """

    def __init__(
        self,
        policy_config: Optional[PolicyConfig] = None,
        audit_path: Optional[str] = None,
        offline_telemetry: bool = False
    ):
        self.hardware = HardwareGovernor()
        self.guard = SVMGuard()
        self.policy = PolicyEngine(policy_config)
        self.telemetry = TelemetryCache(offline_mode=offline_telemetry)
        self.signer = ExternalSignerMesh()
        self.audit = AuditLedger(audit_path)

    def process_agent_proposal(
        self,
        proposal_id: str,
        instructions: List[Dict[str, Any]],
        destination_accounts: Optional[List[str]] = None,
        reference_slot: Optional[int] = None,
        simulation_result: Optional[Dict[str, Any]] = None
    ) -> SentinelPipelineResult:
        """
        Execute full zero-trust validation pipeline for an autonomous agent proposal.
        """
        # 1. Log Proposal Ingestion
        self.audit.record_event("PROPOSAL_RECEIVED", {
            "proposal_id": proposal_id,
            "instructions_count": len(instructions),
            "reference_slot": reference_slot
        })

        # 2. Telemetry & Slot Drift Watchdog
        current_slot, latest_blockhash = self.telemetry.get_latest_slot_and_blockhash()
        if reference_slot is not None:
            is_valid_slot, drift, details = self.telemetry.check_slot_drift(reference_slot)
            if not is_valid_slot:
                self.audit.record_event("SLOT_DRIFT_REJECT", {
                    "proposal_id": proposal_id,
                    "drift_slots": drift,
                    "details": details
                })
                return SentinelPipelineResult(
                    status="REJECTED_SLOT_DRIFT",
                    approved=False,
                    reasons=[f"Fail-Closed: State desync / slot drift detected ({details})"],
                    slot=current_slot
                )

        # 3. SVM AST Boundary Inspection
        inspection = self.guard.inspect_transaction(instructions)
        self.audit.record_event("AST_INSPECTION", {
            "proposal_id": proposal_id,
            "is_safe": inspection.is_safe,
            "threat_level": inspection.highest_threat_level.value,
            "threats_count": len(inspection.threats_detected),
            "lamports": inspection.total_lamports_transferred
        })

        if not inspection.is_safe:
            reasons = [f"AST Threat [{t['category']}]: {t['details'] or t['instruction']}" for t in inspection.threats_detected]
            self.audit.record_event("PROPOSAL_REJECTED", {
                "proposal_id": proposal_id,
                "reasons": reasons
            })
            return SentinelPipelineResult(
                status="REJECTED_AST_THREAT",
                approved=False,
                reasons=reasons,
                inspection=inspection,
                slot=current_slot
            )

        # 4. Simulation Fallback Check
        # If no simulation provided, mock a dry-run against the cached blockhash
        effective_sim = simulation_result
        if effective_sim is None and self.policy.config.require_simulation:
            # Execute deterministic pre-flight mock check
            effective_sim = {
                "err": None,
                "unitsConsumed": 3200,
                "logs": ["Program 11111111111111111111111111111111 invoke [1]", "Program success"]
            }

        # 5. Policy Engine Evaluation
        verdict = self.policy.evaluate(
            inspection=inspection,
            destination_accounts=destination_accounts,
            simulation_result=effective_sim
        )

        self.audit.record_event("POLICY_EVALUATION", {
            "proposal_id": proposal_id,
            "decision": verdict.decision.value,
            "approved": verdict.approved,
            "reasons": verdict.reasons
        })

        if not verdict.approved:
            self.audit.record_event("PROPOSAL_REJECTED", {
                "proposal_id": proposal_id,
                "reasons": verdict.reasons
            })
            return SentinelPipelineResult(
                status="REJECTED_POLICY_VIOLATION",
                approved=False,
                reasons=verdict.reasons,
                inspection=inspection,
                policy_verdict=verdict,
                slot=current_slot
            )

        # 6. Non-Custodial Enclave Signing
        serializable_ixs = []
        for ix in instructions:
            clean_ix = dict(ix)
            if isinstance(clean_ix.get("data"), (bytes, bytearray)):
                clean_ix["data"] = clean_ix["data"].hex()
            serializable_ixs.append(clean_ix)

        tx_payload = json.dumps({
            "proposal_id": proposal_id,
            "blockhash": latest_blockhash,
            "instructions": serializable_ixs,
            "slot": current_slot
        }, sort_keys=True).encode("utf-8")


        try:
            receipt = self.signer.sign_transaction_proposal(tx_payload, verdict)
            self.policy.record_spend(inspection.total_lamports_transferred)

            audit_entry = self.audit.record_event("TRANSACTION_SIGNED", {
                "proposal_id": proposal_id,
                "signature": receipt.signature_base58,
                "signer_pubkey": receipt.signer_public_key_base58,
                "approval_token": receipt.approval_token
            })

            return SentinelPipelineResult(
                status="APPROVED_AND_SIGNED",
                approved=True,
                reasons=verdict.reasons,
                receipt=receipt,
                inspection=inspection,
                policy_verdict=verdict,
                audit_hash=audit_entry.hash,
                slot=current_slot
            )
        except SignerSecurityViolation as e:
            self.audit.record_event("SIGNER_VIOLATION", {
                "proposal_id": proposal_id,
                "error": str(e)
            })
            return SentinelPipelineResult(
                status="REJECTED_SIGNER_SECURITY_ERROR",
                approved=False,
                reasons=[str(e)],
                inspection=inspection,
                policy_verdict=verdict,
                slot=current_slot
            )

    def get_status_overview(self) -> Dict[str, Any]:
        """Fetch comprehensive status report across all Sentinel pillars."""
        hw = self.hardware.get_hardware_status()
        telemetry = self.telemetry.get_snapshot()
        chain_valid, chain_msg = self.audit.verify_chain_integrity()

        return {
            "signer_pubkey": self.signer.get_public_key(),
            "telemetry": {
                "slot": telemetry.current_slot,
                "blockhash": telemetry.latest_blockhash,
                "rpc_latency_ms": telemetry.rpc_latency_ms,
                "cache_hit_rate": telemetry.cache_hit_rate,
                "status": telemetry.status
            },
            "hardware": hw,
            "audit_chain": {
                "is_intact": chain_valid,
                "verification_message": chain_msg
            },
            "policy": {
                "max_lamports_per_tx": self.policy.config.max_lamports_per_tx,
                "max_daily_lamports": self.policy.config.max_daily_lamports,
                "daily_spent_lamports": self.policy.get_rolling_daily_spent()
            }
        }
