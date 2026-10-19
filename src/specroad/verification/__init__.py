"""Passive verification contracts and test references; no test execution."""

from .contracts import (VerificationContract, VerificationContractResolution,
                        VerificationTest, prepare_verification_contract,
                        resolve_verification_contract)

__all__ = ("VerificationContract", "VerificationContractResolution", "VerificationTest",
           "prepare_verification_contract", "resolve_verification_contract")
