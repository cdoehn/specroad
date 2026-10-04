"""Static development metadata; importing it needs no build tooling."""

__version__ = "0.2.0.dev0"
MINIMUM_PYTHON = (3, 10)

# Declaration, not an assertion that these runtimes passed release verification.
DECLARED_CPYTHON_MINORS = ("3.10", "3.11", "3.12", "3.13", "3.14")
# Pure contract identities shared by validators and bootstrap self-description.
# Keep this module free of model/evaluator imports and environment observation.
MODEL_SCHEMA_VERSION = "0.2.0"
SRX_LANGUAGE_VERSION = "1.0"

# Implemented Core model versions; result/request formats are separate.
SUPPORTED_SCHEMA_VERSIONS = (MODEL_SCHEMA_VERSION,)
# Public Core evaluator support; this does not register a CLI command.
SUPPORTED_SRX_VERSIONS = (SRX_LANGUAGE_VERSION,)
PYTHON_CAPABILITY_IDS = ("python.structured-request", "python.srx.evaluate")
