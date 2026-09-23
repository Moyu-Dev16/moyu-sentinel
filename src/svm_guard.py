"""
Solana SVM Instruction Disassembler and AST Semantic Guard.
Inspects raw and structured Solana instructions to prevent drainer attacks,
authority takeovers, zero-value dust griefing, and unauthorized program calls.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set
import struct
import base64

class SecurityThreatLevel(str, Enum):
    SAFE = "SAFE"
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class ThreatCategory(str, Enum):
    NONE = "NONE"
    AUTHORITY_TAKEOVER = "AUTHORITY_TAKEOVER"
    UNAUTHORIZED_PROGRAM = "UNAUTHORIZED_PROGRAM"
    ACCOUNT_CLOSE_DRAIN = "ACCOUNT_CLOSE_DRAIN"
    EXCESSIVE_COMPUTE_PRICE = "EXCESSIVE_COMPUTE_PRICE"
    ZERO_VALUE_GRIEFING = "ZERO_VALUE_GRIEFING"
    SYSTEM_ASSIGN_HIJACK = "SYSTEM_ASSIGN_HIJACK"
    EXCESSIVE_TRANSFER = "EXCESSIVE_TRANSFER"

# Canonical Solana Program IDs
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
COMPUTE_BUDGET_PROGRAM_ID = "ComputeBudget111111111111111111111111111111"

# Standard Whitelisted DEX / DeFi Program IDs
JUPITER_V6_PROGRAM_ID = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
RAYDIUM_AMM_V4_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_CLMM_PROGRAM_ID = "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK"
ORCA_WHIRLPOOL_PROGRAM_ID = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"
COOKIE_DEX_PROGRAM_ID = "CKieDEX111111111111111111111111111111111111"

DEFAULT_ALLOWED_PROGRAMS: Set[str] = {
    SYSTEM_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    TOKEN_2022_PROGRAM_ID,
    ASSOCIATED_TOKEN_PROGRAM_ID,
    COMPUTE_BUDGET_PROGRAM_ID,
    JUPITER_V6_PROGRAM_ID,
    RAYDIUM_AMM_V4_PROGRAM_ID,
    RAYDIUM_CLMM_PROGRAM_ID,
    ORCA_WHIRLPOOL_PROGRAM_ID,
    COOKIE_DEX_PROGRAM_ID
}

@dataclass
class ParsedInstruction:
    program_id: str
    instruction_name: str
    accounts: List[str]
    params: Dict[str, Any]
    threat_level: SecurityThreatLevel = SecurityThreatLevel.SAFE
    threat_category: ThreatCategory = ThreatCategory.NONE
    threat_details: Optional[str] = None

@dataclass
class InspectionReport:
    is_safe: bool
    highest_threat_level: SecurityThreatLevel
    threats_detected: List[Dict[str, Any]] = field(default_factory=list)
    parsed_instructions: List[ParsedInstruction] = field(default_factory=list)
    total_lamports_transferred: int = 0
    total_token_transfers: List[Dict[str, Any]] = field(default_factory=list)

class SVMGuard:
    """
    Static & Semantic AST Inspector for Solana Transaction Instructions.
    Decodes serialized or structured instructions and evaluates security boundaries.
    """

    def __init__(self, allowed_programs: Optional[Set[str]] = None, max_lamports_per_tx: int = 10_000_000_000):
        self.allowed_programs = allowed_programs or set(DEFAULT_ALLOWED_PROGRAMS)
        self.max_lamports_per_tx = max_lamports_per_tx

    def inspect_instruction(self, program_id: str, accounts: List[str], data: bytes) -> ParsedInstruction:
        """Disassemble and inspect a single Solana instruction."""
        # 1. Whitelist program check
        if program_id not in self.allowed_programs:
            return ParsedInstruction(
                program_id=program_id,
                instruction_name="UnknownOrUnwhitelisted",
                accounts=accounts,
                params={"raw_len": len(data)},
                threat_level=SecurityThreatLevel.CRITICAL,
                threat_category=ThreatCategory.UNAUTHORIZED_PROGRAM,
                threat_details=f"Program {program_id} is not in allowed execution whitelist"
            )

        # 2. System Program
        if program_id == SYSTEM_PROGRAM_ID:
            return self._parse_system_instruction(program_id, accounts, data)

        # 3. SPL Token & Token-2022
        elif program_id in (TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID):
            return self._parse_token_instruction(program_id, accounts, data)

        # 4. Compute Budget Program
        elif program_id == COMPUTE_BUDGET_PROGRAM_ID:
            return self._parse_compute_budget_instruction(program_id, accounts, data)

        # 5. Known DEXs (Raydium, Jupiter, Cookie DEX)
        return ParsedInstruction(
            program_id=program_id,
            instruction_name="DefiInvocation",
            accounts=accounts,
            params={"data_len": len(data)},
            threat_level=SecurityThreatLevel.SAFE,
            threat_category=ThreatCategory.NONE
        )

    def _parse_system_instruction(self, program_id: str, accounts: List[str], data: bytes) -> ParsedInstruction:
        if len(data) < 4:
            return ParsedInstruction(program_id, "SystemMalformed", accounts, {}, SecurityThreatLevel.WARNING, ThreatCategory.NONE, "Data shorter than 4 bytes")

        disc = struct.unpack("<I", data[:4])[0]
        if disc == 2:  # Transfer: u32 (2), u64 (lamports)
            if len(data) >= 12:
                lamports = struct.unpack("<Q", data[4:12])[0]
                if lamports == 0:
                    return ParsedInstruction(
                        program_id, "SystemTransfer", accounts, {"lamports": 0},
                        SecurityThreatLevel.WARNING, ThreatCategory.ZERO_VALUE_GRIEFING,
                        "Zero-value native SOL transfer detected"
                    )
                threat_level = SecurityThreatLevel.CRITICAL if lamports > self.max_lamports_per_tx else SecurityThreatLevel.SAFE
                threat_cat = ThreatCategory.EXCESSIVE_TRANSFER if lamports > self.max_lamports_per_tx else ThreatCategory.NONE
                details = f"Transfer of {lamports} lamports exceeds limit {self.max_lamports_per_tx}" if lamports > self.max_lamports_per_tx else None
                return ParsedInstruction(program_id, "SystemTransfer", accounts, {"lamports": lamports}, threat_level, threat_cat, details)

        elif disc == 1:  # Assign: reassigns account owner to a new program
            return ParsedInstruction(
                program_id, "SystemAssign", accounts, {},
                SecurityThreatLevel.CRITICAL, ThreatCategory.SYSTEM_ASSIGN_HIJACK,
                "SystemProgram.Assign invoked: high-risk account ownership modification"
            )

        elif disc == 0:  # CreateAccount
            return ParsedInstruction(program_id, "SystemCreateAccount", accounts, {}, SecurityThreatLevel.SAFE)

        return ParsedInstruction(program_id, f"SystemGeneric_{disc}", accounts, {"disc": disc})

    def _parse_token_instruction(self, program_id: str, accounts: List[str], data: bytes) -> ParsedInstruction:
        if not data:
            return ParsedInstruction(program_id, "TokenEmpty", accounts, {}, SecurityThreatLevel.WARNING)

        disc = data[0]

        # Disc 6: SetAuthority (CRITICAL DRAINER VECTOR)
        if disc == 6:
            return ParsedInstruction(
                program_id, "TokenSetAuthority", accounts, {"disc": disc},
                SecurityThreatLevel.CRITICAL, ThreatCategory.AUTHORITY_TAKEOVER,
                "TokenProgram.SetAuthority detected: potential drainer authority hijacking"
            )

        # Disc 9: CloseAccount (Token account closing drain)
        if disc == 9:
            return ParsedInstruction(
                program_id, "TokenCloseAccount", accounts, {"disc": disc},
                SecurityThreatLevel.WARNING, ThreatCategory.ACCOUNT_CLOSE_DRAIN,
                "TokenProgram.CloseAccount detected: account destruction"
            )

        # Disc 3: Transfer (u8 3, u64 amount)
        if disc == 3 and len(data) >= 9:
            amount = struct.unpack("<Q", data[1:9])[0]
            if amount == 0:
                return ParsedInstruction(
                    program_id, "TokenTransfer", accounts, {"amount": 0},
                    SecurityThreatLevel.WARNING, ThreatCategory.ZERO_VALUE_GRIEFING,
                    "Zero-value SPL token transfer detected"
                )
            return ParsedInstruction(program_id, "TokenTransfer", accounts, {"amount": amount}, SecurityThreatLevel.SAFE)

        # Disc 12: TransferChecked (u8 12, u64 amount, u8 decimals)
        if disc == 12 and len(data) >= 10:
            amount, decimals = struct.unpack("<QB", data[1:10])
            if amount == 0:
                return ParsedInstruction(
                    program_id, "TokenTransferChecked", accounts, {"amount": 0, "decimals": decimals},
                    SecurityThreatLevel.WARNING, ThreatCategory.ZERO_VALUE_GRIEFING,
                    "Zero-value SPL token transfer checked detected"
                )
            return ParsedInstruction(program_id, "TokenTransferChecked", accounts, {"amount": amount, "decimals": decimals}, SecurityThreatLevel.SAFE)

        return ParsedInstruction(program_id, f"TokenGeneric_{disc}", accounts, {"disc": disc})

    def _parse_compute_budget_instruction(self, program_id: str, accounts: List[str], data: bytes) -> ParsedInstruction:
        if not data:
            return ParsedInstruction(program_id, "ComputeBudgetEmpty", accounts, {})

        disc = data[0]
        # Disc 2: SetComputeUnitLimit (u8 2, u32 units)
        if disc == 2 and len(data) >= 5:
            units = struct.unpack("<I", data[1:5])[0]
            return ParsedInstruction(program_id, "SetComputeUnitLimit", accounts, {"units": units})

        # Disc 3: SetComputeUnitPrice (u8 3, u64 micro_lamports)
        if disc == 3 and len(data) >= 9:
            price = struct.unpack("<Q", data[1:9])[0]
            # If price > 10,000,000 micro-lamports (10 lamports per CU, very high)
            if price > 10_000_000:
                return ParsedInstruction(
                    program_id, "SetComputeUnitPrice", accounts, {"micro_lamports": price},
                    SecurityThreatLevel.WARNING, ThreatCategory.EXCESSIVE_COMPUTE_PRICE,
                    f"Abnormally high compute unit price: {price} micro-lamports"
                )
            return ParsedInstruction(program_id, "SetComputeUnitPrice", accounts, {"micro_lamports": price})

        return ParsedInstruction(program_id, f"ComputeBudget_{disc}", accounts, {})

    def inspect_transaction(self, instructions: List[Dict[str, Any]]) -> InspectionReport:
        """
        Inspect all instructions in a proposed transaction payload.
        instructions: list of dicts with 'program_id', 'accounts', and 'data' (bytes, hex, or base64).
        """
        parsed_list: List[ParsedInstruction] = []
        threats: List[Dict[str, Any]] = []
        total_lamports = 0
        token_transfers = []
        highest_threat = SecurityThreatLevel.SAFE

        for ix in instructions:
            pid = ix.get("program_id", "")
            accounts = ix.get("accounts", [])
            raw_data = ix.get("data", b"")

            if isinstance(raw_data, str):
                if raw_data.startswith("0x"):
                    data_bytes = bytes.fromhex(raw_data[2:])
                else:
                    try:
                        data_bytes = base64.b64decode(raw_data)
                    except Exception:
                        data_bytes = raw_data.encode("utf-8")
            elif isinstance(raw_data, (bytes, bytearray)):
                data_bytes = bytes(raw_data)
            else:
                data_bytes = b""

            parsed = self.inspect_instruction(pid, accounts, data_bytes)
            parsed_list.append(parsed)

            if parsed.instruction_name == "SystemTransfer":
                total_lamports += parsed.params.get("lamports", 0)
            elif parsed.instruction_name in ("TokenTransfer", "TokenTransferChecked"):
                token_transfers.append({
                    "program": parsed.program_id,
                    "amount": parsed.params.get("amount", 0),
                    "accounts": parsed.accounts
                })

            if parsed.threat_level in (SecurityThreatLevel.WARNING, SecurityThreatLevel.CRITICAL):
                threats.append({
                    "instruction": parsed.instruction_name,
                    "program_id": parsed.program_id,
                    "threat_level": parsed.threat_level.value,
                    "category": parsed.threat_category.value,
                    "details": parsed.threat_details
                })
                if parsed.threat_level == SecurityThreatLevel.CRITICAL:
                    highest_threat = SecurityThreatLevel.CRITICAL
                elif highest_threat != SecurityThreatLevel.CRITICAL and parsed.threat_level == SecurityThreatLevel.WARNING:
                    highest_threat = SecurityThreatLevel.WARNING

        is_safe = (highest_threat != SecurityThreatLevel.CRITICAL)

        return InspectionReport(
            is_safe=is_safe,
            highest_threat_level=highest_threat,
            threats_detected=threats,
            parsed_instructions=parsed_list,
            total_lamports_transferred=total_lamports,
            total_token_transfers=token_transfers
        )
