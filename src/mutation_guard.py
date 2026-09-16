"""
Semantic Mutation Guard Engine.
Guards against AST boundary escapes, half-open window mutations, and zero-value griefing.
"""

from typing import Dict, Any, List

class MutationGuard:
    @staticmethod
    def evaluate_floor(balance: int, floor: int) -> str:
        """
        Original rule: cmpDec(bal, floor) < 0 -> BROKEN, otherwise HELD.
        Mutant: <= 0 (where exact floor balance falsely triggers default).
        """
        if balance < floor:
            return "BROKEN"
        return "HELD"

    @staticmethod
    def evaluate_window(transfer_time: int, window_from: int, window_to: int) -> str:
        """
        Half-open window [from, to):
        t >= window_from and t < window_to -> transfer is WITHIN window (BROKEN).
        """
        if transfer_time >= window_from and transfer_time < window_to:
            return "BROKEN"
        return "HELD"

    @staticmethod
    def evaluate_disclosure(disclosed_at: int, transfer_at: int, deadline_ms: int) -> str:
        """
        Disclosure deadline: d <= t + deadline -> HELD, otherwise BROKEN.
        """
        if disclosed_at <= transfer_at + deadline_ms:
            return "HELD"
        return "BROKEN"

    @staticmethod
    def evaluate_transfer_validity(sender: str, subject: str, value: int) -> bool:
        """
        Anti-Griefing Guard:
        A transfer of 0 value via ERC-20 transferFrom requires no allowance.
        Transfers with value <= 0 must be ignored to prevent false default triggers.
        """
        if sender == subject and value > 0:
            return True
        return False
