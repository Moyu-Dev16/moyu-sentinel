"""
Autonomous Circuit Breaker & Chaos Watchdog for Solana AI Agents.
Provides self-healing circuit states (CLOSED, OPEN, HALF_OPEN), anomaly rate tripwires,
and cascading failure containment.
"""

from enum import Enum
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

class CircuitState(Enum):
    CLOSED = "CLOSED"         # Normal operation, all transactions pass to pipeline
    OPEN = "OPEN"             # Tripped, all transactions fail-closed immediately
    HALF_OPEN = "HALF_OPEN"   # Testing recovery with canary transactions

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 3           # Consecutive failures to trip circuit
    recovery_timeout_sec: float = 5.0    # Seconds to wait before attempting HALF_OPEN canary
    consecutive_success_to_close: int = 2 # Successful canary txs required to reset to CLOSED
    window_duration_sec: float = 60.0    # Rolling window for anomaly tracking
    max_anomaly_rate: float = 0.4        # Max allowed failure rate in rolling window (40%)

class CircuitBreaker:
    """
    Self-healing circuit breaker preventing cascading exploits and RPC exhaustion.
    """
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.last_state_change = time.time()
        self.tripped_reason = ""
        self.failure_history: List[float] = []
        self.success_history: List[float] = []

    def can_execute(self) -> Tuple[bool, Optional[str]]:
        """
        Check if transaction execution is currently permitted by the circuit breaker.
        """
        now = time.time()
        
        if self.state == CircuitState.OPEN:
            # Check if cooldown has elapsed to transition to HALF_OPEN
            if now - self.last_state_change >= self.config.recovery_timeout_sec:
                self.state = CircuitState.HALF_OPEN
                self.consecutive_successes = 0
                self.last_state_change = now
                return True, None
            return False, f"Circuit Breaker TRIPPED (OPEN): {self.tripped_reason}. Cooldown remaining: {round(self.config.recovery_timeout_sec - (now - self.last_state_change), 2)}s"

        elif self.state == CircuitState.HALF_OPEN:
            # Canary mode allows trial execution
            return True, None

        # CLOSED state allows execution
        return True, None

    def record_success(self):
        """Record successful transaction execution."""
        now = time.time()
        self.success_history.append(now)
        self.consecutive_failures = 0

        if self.state == CircuitState.HALF_OPEN:
            self.consecutive_successes += 1
            if self.consecutive_successes >= self.config.consecutive_success_to_close:
                # Successfully recovered
                self.state = CircuitState.CLOSED
                self.tripped_reason = ""
                self.last_state_change = now

        self._prune_history(now)

    def record_failure(self, reason: str):
        """Record a pipeline failure, threat detection, or anomaly."""
        now = time.time()
        self.failure_history.append(now)
        self.consecutive_failures += 1
        self.consecutive_successes = 0

        if self.state == CircuitState.HALF_OPEN:
            # Immediate failback to OPEN if canary fails
            self.state = CircuitState.OPEN
            self.tripped_reason = f"Canary execution failed: {reason}"
            self.last_state_change = now
            return

        if self.state == CircuitState.CLOSED:
            if self.consecutive_failures >= self.config.failure_threshold:
                self.trip(f"Exceeded {self.config.failure_threshold} consecutive failures: {reason}")
                return

            # Check rolling anomaly rate
            self._prune_history(now)
            total = len(self.failure_history) + len(self.success_history)
            if total >= 5:
                anomaly_rate = len(self.failure_history) / total
                if anomaly_rate > self.config.max_anomaly_rate:
                    self.trip(f"Anomaly rate {anomaly_rate*100:.1f}% exceeded threshold {self.config.max_anomaly_rate*100:.1f}%: {reason}")

    def trip(self, reason: str):
        """Manually or automatically trip the circuit breaker into OPEN state."""
        self.state = CircuitState.OPEN
        self.tripped_reason = reason
        self.last_state_change = time.time()

    def reset(self):
        """Force reset circuit breaker to healthy CLOSED state."""
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.tripped_reason = ""
        self.last_state_change = time.time()
        self.failure_history.clear()
        self.success_history.clear()

    def _prune_history(self, now: float):
        cutoff = now - self.config.window_duration_sec
        self.failure_history = [t for t in self.failure_history if t >= cutoff]
        self.success_history = [t for t in self.success_history if t >= cutoff]

    def get_status(self) -> Dict[str, Any]:
        """Return real-time circuit status."""
        now = time.time()
        self._prune_history(now)
        total = len(self.failure_history) + len(self.success_history)
        anomaly_rate = (len(self.failure_history) / total) if total > 0 else 0.0

        return {
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "tripped_reason": self.tripped_reason if self.state == CircuitState.OPEN else None,
            "seconds_in_current_state": round(now - self.last_state_change, 2),
            "rolling_anomaly_rate": round(anomaly_rate, 3),
            "recent_failures_count": len(self.failure_history),
            "recent_successes_count": len(self.success_history)
        }
