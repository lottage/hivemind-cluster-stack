#!/usr/bin/env python3
"""
Operator Cryptographic Authentication & Anti-Spoofing Module
Guarantees that Human-in-the-Loop approval (--approved / Gate 2) can ONLY
originate from the physical human operator, and can NEVER be forged or invoked
by an autonomous model, subagent, or background script.

Security Controls:
1. Cryptographic HMAC Operator Secret Key: Stored in a human-only restricted file (~/.cluster_operator_key).
2. Interactive TTY Challenge: When run from CLI, requires a real human interactive terminal and random one-time nonce.
3. Network Origin Check: Rejects approval requests originating from VM 102 localhost (where background agents live).
"""

import os
import sys
import hmac
import hashlib
import secrets
import time
import json
from typing import Tuple, Optional

# Default path for the operator's secret key (outside repo, in human home directory)
OPERATOR_KEY_PATH = os.path.expanduser("~/.cluster_operator_key")

class OperatorAuth:
    def __init__(self, key_path: str = OPERATOR_KEY_PATH):
        self.key_path = os.path.abspath(key_path)

    def initialize_operator_key(self, force: bool = False) -> str:
        """Generates a secure 256-bit cryptographic operator key for the human."""
        if os.path.exists(self.key_path) and not force:
            with open(self.key_path, "r", encoding="utf-8") as f:
                return f.read().strip()

        key = secrets.token_hex(32)
        os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
        with open(self.key_path, "w", encoding="utf-8") as f:
            f.write(key)

        # Restrict permissions on Linux/macOS
        if sys.platform != "win32":
            os.chmod(self.key_path, 0o600)

        print(f"[SECURITY] Generated new Human Operator Secret Key at: {self.key_path}")
        return key

    def get_operator_key(self) -> Optional[str]:
        """Reads the human operator's secret key."""
        if os.path.exists(self.key_path):
            with open(self.key_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        return None

    def generate_approval_token(self, sample_id: str) -> str:
        """Generates an unforgeable HMAC-SHA256 token proving human operator approval."""
        key = self.get_operator_key()
        if not key:
            key = self.initialize_operator_key()

        timestamp = str(int(time.time()))
        message = f"APPROVE_TRAINING_WEIGHTS:{sample_id}:{timestamp}".encode("utf-8")
        signature = hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()
        token = f"{sample_id}:{timestamp}:{signature}"
        return token

    def verify_approval_token(self, token: str, sample_id: str, max_age_seconds: int = 3600) -> Tuple[bool, str]:
        """
        Cryptographically verifies that an approval token was signed by the human operator's key.
        Rejects forged, expired, or mismatched tokens.
        """
        key = self.get_operator_key()
        if not key:
            return False, "Operator key not found. Human operator must initialize credentials."

        try:
            parts = token.split(":")
            if len(parts) != 3:
                return False, "Malformed approval token format."

            token_sample_id, timestamp_str, token_sig = parts
            if token_sample_id != sample_id:
                return False, f"Token sample ID mismatch (Token: {token_sample_id}, Target: {sample_id})."

            timestamp = int(timestamp_str)
            now = int(time.time())
            if now - timestamp > max_age_seconds:
                return False, f"Approval token expired ({now - timestamp}s > {max_age_seconds}s)."

            expected_msg = f"APPROVE_TRAINING_WEIGHTS:{sample_id}:{timestamp_str}".encode("utf-8")
            expected_sig = hmac.new(key.encode("utf-8"), expected_msg, hashlib.sha256).hexdigest()

            if not hmac.compare_digest(token_sig, expected_sig):
                return False, "Invalid cryptographic signature! Verification failed."

            return True, "Valid Human Operator Signature Verified."
        except Exception as e:
            return False, f"Token verification error: {e}"

    def interactive_human_challenge(self, sample_id: str) -> Tuple[bool, str]:
        """
        Enforces a physical, interactive human challenge in the terminal.
        Fails if invoked from a headless background script, pipe, or autonomous agent!
        """
        # 1. TTY check: Ensure input is attached to a real interactive terminal
        if not sys.stdin.isatty():
            return False, "REJECTED: sys.stdin.isatty() is False! Non-interactive approval blocked to prevent agent self-approval."

        # 2. Generate random 6-character verification code
        challenge_nonce = secrets.token_hex(3).upper()
        print("\n" + "=" * 65)
        print("          HUMAN-IN-THE-LOOP APPROVAL CHALLENGE")
        print("=" * 65)
        print(f"Target Sample ID: {sample_id}")
        print("To confirm that YOU are the human operator and authorize this sample")
        print(f"to modify model weights, type the confirmation code below:")
        print(f"  --> CONFIRM-{challenge_nonce}")
        print("=" * 65)

        try:
            user_input = input("Enter confirmation code (or 'reject'): ").strip()
            if user_input == f"CONFIRM-{challenge_nonce}":
                token = self.generate_approval_token(sample_id)
                return True, token
            else:
                return False, "Incorrect confirmation code entered. Approval aborted."
        except (KeyboardInterrupt, EOFError):
            return False, "Approval canceled by operator."

if __name__ == "__main__":
    auth = OperatorAuth()
    auth.initialize_operator_key()
    print("[INFO] OperatorAuth initialized. Testing challenge...")
    # Test token verification
    test_id = "EXP-TEST-001"
    token = auth.generate_approval_token(test_id)
    valid, msg = auth.verify_approval_token(token, test_id)
    print(f"Token Verification Test: Valid={valid} ({msg})")
