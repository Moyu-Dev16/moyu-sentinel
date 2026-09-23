"""
Solana AI Agent Policy Engine.
Enforces deterministic spending limits, recipient boundaries, daily quotas,
and simulation requirements on proposed Solana transactions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set
import time
import hashlib
import json

from .svm_guard import InspectionReport, SecurityThreatLevel

class PolicyDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUIRES_OPERATOR_OVERRIDE = "REQUIRES_OPERATOR_OVERRIDE"

@dataclass
class PolicyVerdict:
    decision: PolicyDecision
    approved: bool
    reasons: List[str] = field(default_factory=list)
    approval_token: Optional[str] = None
    evaluated_at: int = field(default_factory=lambda: int(time.time() * 1000))

@dataclass
class PolicyConfig:
    max_lamports_per_tx: int = 5_000_000_000       # 5 SOL default cap per tx
    max_daily_lamports: int = 20_000_000_000       # 20 SOL rolling 24h cap
    require_simulation: bool = True                # Fail-closed on missing/failed simulation
    allowed_recipients: Optional[Set[str]] = None  # If set, destination must be whitelisted
    blocked_recipients: Set[str] = field(default_factory=set) # Known drainers / malicious pools
    max_slippage_bps: int = 150                    # Max 1.5% slippage

class PolicyEngine:
    def __init__(self, config: Optional[PolicyConfig] = None):
        self.config = config or PolicyConfig()
        # Track timestamped spends: [(timestamp_sec, lamports)]
        self._spend_history: List[tuple[float, int]] = []

    def get_rolling_daily_spent(self) -> int:
        """Calculate total lamports spent in the last 24 hours."""
        now = time.time()
        cutoff = now - 86400.0
        # Prune old spends
        self._spend_history = [s for s in self._spend_history if s[0] >= cutoff]
        return sum(s[1] for s in self._spend_history)

    def record_spend(self, lamports: int):
        """Record an executed spend to rolling history."""
        if lamports > 0:
            self._spend_history.append((time.time(), lamports))

    def evaluate(
        self,
        inspection: InspectionReport,
        destination_accounts: Optional[List[str]] = None,
        simulation_result: Optional[Dict[str, Any]] = None
    ) -> PolicyVerdict:
        """
        Evaluate a transaction proposal against agent governance policies.
        """
        reasons: List[str] = []

        # 1. Check SVM Guard AST inspection
        if not inspection.is_safe or inspection.highest_threat_level == SecurityThreatLevel.CRITICAL:
            threat_msgs = [f"{t['category']}: {t['details'] or t['instruction']}" for t in inspection.threats_detected]
            reasons.append(f"Critical AST threat detected: {'; '.join(threat_msgs)}")
            return PolicyVerdict(decision=PolicyDecision.REJECTED, approved=False, reasons=reasons)

        # 2. Per-transaction Lamport cap check
        tx_lamports = inspection.total_lamports_transferred
        if tx_lamports > self.config.max_lamports_per_tx:
            reasons.append(
                f"Per-transaction spend limit exceeded: {tx_lamports} lamports > max {self.config.max_lamports_per_tx}"
            )

        # 3. Rolling daily Lamport cap check
        daily_spent = self.get_rolling_daily_spent()
        if daily_spent + tx_lamports > self.config.max_daily_lamports:
            reasons.append(
                f"Rolling 24h spend quota exceeded: current {daily_spent} + {tx_lamports} > max {self.config.max_daily_lamports}"
            )

        # 4. Destination account checks
        dests = destination_accounts or []
        for dest in dests:
            if dest in self.config.blocked_recipients:
                reasons.append(f"Destination {dest} is in the blocked recipients blacklist")
            if self.config.allowed_recipients is not None and dest not in self.config.allowed_recipients:
                reasons.append(f"Destination {dest} is not in the authorized recipients whitelist")

        # 5. Pre-flight simulation check (fail-closed)
        if self.config.require_simulation:
            if simulation_result is None:
                reasons.append("Pre-flight simulation required by policy but not provided (Fail-Closed)")
            else:
                sim_err = simulation_result.get("err")
                if sim_err is not None:
                    reasons.append(f"Pre-flight simulation failed on-chain: {sim_err}")

        if reasons:
            return PolicyVerdict(
                decision=PolicyDecision.REJECTED,
                approved=False,
                reasons=reasons
            )

        # Generate cryptographic policy approval token
        raw_payload = {
            "lamports": tx_lamports,
            "instructions_count": len(inspection.parsed_instructions),
            "timestamp": int(time.time())
        }
        token = hashlib.sha256(json.dumps(raw_payload, sort_keys=True).encode("utf-8")).hexdigest()

        return PolicyVerdict(
            decision=PolicyDecision.APPROVED,
            approved=True,
            reasons=["All policy checks passed: spend caps, AST safety, destination boundaries, and simulation."],
            approval_token=token
        )
