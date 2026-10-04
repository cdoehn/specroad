"""Static development metadata; importing it needs no build tooling."""

__version__ = "0.2.0.dev0"
MINIMUM_PYTHON = (3, 10)

# Declaration, not an assertion that these runtimes passed release verification.
DECLARED_CPYTHON_MINORS = ("3.10", "3.11", "3.12", "3.13", "3.14")
# Implemented Core model schema versions; result/request formats are separate.
SUPPORTED_SCHEMA_VERSIONS = ("0.2.0",)
