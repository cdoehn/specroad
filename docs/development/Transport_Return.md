# Proposal-Rückgabe

Der Rückexport verlangt das ursprüngliche Hinpaket, dessen vollständigen Hash,
den Projektroot, einen expliziten Proposal und die gebundene PatchHarbor-PYZ:

```sh
python3 specroad.pyz bundle create --profile ai-runtime --direction return \
  --project /sandbox/project --proposal /sandbox/proposal.json \
  --reference /sandbox/reference/outbound.zip --expected-sha256 "$outbound_sha256" \
  --patchharbor-pyz /sandbox/runtime/patchharbor-1.8.0.pyz \
  --patchharbor-pyz-sha256 "$patchharbor_sha256" \
  --output-root /output --output return.zip --format json
```

`created` nennt die einzelne native ZIP und ihren SHA-256. `no_changes` erzeugt
keine Patch-Datei. Der Export führt weder Git noch Shell noch Netzwerk aus.
Fachänderungen außerhalb des expliziten Proposals werden abgewiesen. Die ZIP
darf nur durch den gebundenen lokalen Empfangsadapter angenommen werden;
der feste Entrypoint allein erteilt keine Hostautorität oder fachliche Freigabe.

Normativer Vertrag: [Spezifikation W.5.1](../specification/SpecRoad_Spezifikation.md#w51-geschlossener-proposal-rückvertrag--return-transport-743).
