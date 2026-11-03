"""Stable compatibility imports for failure evidence, with separated boundaries."""
from .turn_errors import error_code, failure_details
from .readonly_evidence import safe_command, source_message, prove_readonly_turn
from .retry_proof import load_failure, proof

__all__ = ["error_code", "failure_details", "safe_command", "source_message",
           "prove_readonly_turn", "load_failure", "proof"]
