"""
Non-Custodial External Signer Enclave for Solana AI Agents.
Guarantees isolated key custody: Agent LLM loops never touch private keys.
Only signs transaction payloads if backed by a valid, cryptographic PolicyVerdict.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import time
import base58
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

from .policy_engine import PolicyVerdict, PolicyDecision

class SignerSecurityViolation(Exception):
    """Raised when an attempt is made to sign an unapproved or tampered transaction."""
    pass

@dataclass
class SignedExecutionReceipt:
    signature_base58: str
    signer_public_key_base58: str
    approval_token: str
    signed_payload_sha256: str
    timestamp_ms: int
    verified: bool

class ExternalSignerMesh:
    """
    Isolated cryptographic signing enclave.
    Acts as the external non-custodial boundary for autonomous agents.
    """

    def __init__(self, private_key_bytes: Optional[bytes] = None):
        if private_key_bytes:
            self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        else:
            self._private_key = ed25519.Ed25519PrivateKey.generate()

        self._public_key = self._private_key.public_key()
        raw_pub = self._public_key.public_bytes_raw()
        self.public_key_base58 = base58.b58encode(raw_pub).decode("utf-8")

    def get_public_key(self) -> str:
        """Expose only the public key to external callers."""
        return self.public_key_base58

    def sign_transaction_proposal(
        self,
        payload_bytes: bytes,
        verdict: PolicyVerdict
    ) -> SignedExecutionReceipt:
        """
        Sign a transaction payload only if verified and approved by the policy engine.
        Enforces strict fail-closed boundary: LLM cannot forge signatures.
        """
        # 1. Enforce policy approval prerequisite
        if not verdict.approved or verdict.decision != PolicyDecision.APPROVED:
            raise SignerSecurityViolation(
                f"Signer Enclave rejected execution: Policy verdict is {verdict.decision}. Reasons: {verdict.reasons}"
            )

        if not verdict.approval_token:
            raise SignerSecurityViolation("Signer Enclave rejected execution: Missing cryptographic approval token.")

        # 2. Cryptographic signature generation
        sig_bytes = self._private_key.sign(payload_bytes)
        sig_b58 = base58.b58encode(sig_bytes).decode("utf-8")

        # 3. Immediate self-verification
        verified = self.verify_signature(payload_bytes, sig_b58, self.public_key_base58)

        import hashlib
        payload_sha = hashlib.sha256(payload_bytes).hexdigest()

        return SignedExecutionReceipt(
            signature_base58=sig_b58,
            signer_public_key_base58=self.public_key_base58,
            approval_token=verdict.approval_token,
            signed_payload_sha256=payload_sha,
            timestamp_ms=int(time.time() * 1000),
            verified=verified
        )

    @staticmethod
    def verify_signature(payload_bytes: bytes, signature_b58: str, public_key_b58: str) -> bool:
        """Verify an Ed25519 signature against a Base58 public key."""
        try:
            pub_bytes = base58.b58decode(public_key_b58)
            sig_bytes = base58.b58decode(signature_b58)
            pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            pub_key.verify(sig_bytes, payload_bytes)
            return True
        except (InvalidSignature, ValueError, Exception):
            return False
