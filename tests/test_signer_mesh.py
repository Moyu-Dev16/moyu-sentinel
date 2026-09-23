import pytest
import base58
from src.policy_engine import PolicyVerdict, PolicyDecision
from src.signer_mesh import ExternalSignerMesh, SignerSecurityViolation

def test_generate_keypair_and_pubkey():
    signer = ExternalSignerMesh()
    pubkey = signer.get_public_key()
    assert isinstance(pubkey, str)
    decoded = base58.b58decode(pubkey)
    assert len(decoded) == 32 # Ed25519 public key is 32 bytes

def test_sign_approved_proposal():
    signer = ExternalSignerMesh()
    payload = b"solana_transaction_serialized_payload"
    verdict = PolicyVerdict(
        decision=PolicyDecision.APPROVED,
        approved=True,
        approval_token="cryptographic_approval_token_123"
    )

    receipt = signer.sign_transaction_proposal(payload, verdict)
    assert receipt.verified is True
    assert receipt.approval_token == "cryptographic_approval_token_123"
    assert len(receipt.signature_base58) > 0

    # Independent verification
    is_valid = ExternalSignerMesh.verify_signature(payload, receipt.signature_base58, receipt.signer_public_key_base58)
    assert is_valid is True

def test_refuse_unapproved_proposal():
    signer = ExternalSignerMesh()
    payload = b"unauthorized_transaction"
    verdict = PolicyVerdict(
        decision=PolicyDecision.REJECTED,
        approved=False,
        reasons=["Spending limit violated"]
    )

    with pytest.raises(SignerSecurityViolation):
        signer.sign_transaction_proposal(payload, verdict)

def test_tampered_payload_verification_fails():
    signer = ExternalSignerMesh()
    payload = b"original_payload"
    verdict = PolicyVerdict(decision=PolicyDecision.APPROVED, approved=True, approval_token="token_abc")
    receipt = signer.sign_transaction_proposal(payload, verdict)

    # Verify against modified payload
    tampered_payload = b"tampered_payload"
    is_valid = ExternalSignerMesh.verify_signature(tampered_payload, receipt.signature_base58, receipt.signer_public_key_base58)
    assert is_valid is False
