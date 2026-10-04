# Current Core self-description

`version` and `capabilities` describe the installed distribution without loading
a project. `schema list/show` returns exact structural resources. The command
registry determines executable CLI operations; a version or schema does not
register a command.

| Machine field | Current meaning and value |
|---|---|
| `version.supported_schema_versions`, `capabilities.semantic.supported_versions.schema` | Core model schema versions accepted by the artifact/configuration validators: `0.2.0`. Independent result, request and Change Plan versions are not additional model versions. |
| `capabilities.semantic.supported_versions.srx` | SRX language versions implemented by the public Core evaluator: `1.0`, exactly as accepted by `SrxProgram`/`parse_program`. This is a language version, not a reformatted SemVer or a schema ID. |
| `capabilities.semantic.capability_ids` | `cli.<command-id>` identifies an actual registered command. `python.srx.evaluate` identifies the public `specroad.srx.evaluate` library API; `python.structured-request` identifies the existing structured request API. |
| `capabilities.semantic.commands`, `command_groups`, `command_classes` | Only the current registry's executable commands and their published contracts. Library capabilities are not inserted into these lists. |
| `version.supported_output_format_versions` | Implemented serializers: JSON envelope `2.0.0` and SARIF `2.1.0`. |
| `capabilities.semantic.output_formats` | Formats actually accepted by the registered commands, currently `json` and `pretty`. A SARIF serializer alone does not make a command accept `--format sarif`. |
| `capabilities.semantic.exchange_formats` | Currently empty; no executable exchange workflow is claimed. |
| `capabilities.semantic.supported_versions.proposal` | Currently empty; the complete versioned Proposal workflow remains in milestone 18. The existing proposal record field schema belongs to model `0.2.0` and is available separately through `schema show`. |

The SRX foundation is implemented through 4.i, including the versioned operator
and error corpus. `python.srx.evaluate` consumes an explicit validated program
and context; it neither loads a project nor introduces `query`, `validate`,
`srx evaluate` or Proposal commands. Unknown commands and unknown exact schema
IDs retain their existing usage errors. Unsupported SRX and model versions
retain their structured input errors.

An available artifact schema establishes its declared field-validation scope.
It does not establish graph validity, workflow completion, authorization or
release readiness. In particular, retrieving the proposal record schema does
not authorize proposal creation or publication. SRX library support does not
invent a standalone JSON Schema catalog entry.

Result format versions are unchanged because these corrections update values
inside the existing result contract. All returned version and capability lists
are independent values; editing one result cannot alter later queries. Runtime
limits remain fresh observations outside the deterministic semantic projection.
Declared Python versions remain separate from measured release evidence.

`AUDIT-CONTRACT-01.R` verifies these boundaries through real library evaluation,
CLI/request rejection, schema validation and isolated module/zipapp execution.
The full future agent workflow of 18.m remains open. Test execution follows the
local `AGENTS.md` and [Testing.md](Testing.md).

The C step shares the model and SRX version identities through the pure static
`_metadata` module. The model version facade, SRX parser, view filter field
schema and supported-version declarations use those same values. Bootstrap
self-description reads these constants without importing the evaluator or
loading any model. The Python capability IDs are declared alongside them;
CLI capability IDs continue to come from the active registry. Existing result
values, schema documents, version rejections and W/R behavior tests are unchanged.
