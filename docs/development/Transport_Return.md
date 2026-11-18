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

## Explizite lokale Hostintegration

`specroad.transport.return_receive.ReturnReceiver` erhält `package`,
`expected_sha256`, `reference`, `reference_sha256`, `repository`, `workspace`,
`patchharbor_pyz`, `patchharbor_pyz_sha256`, `authorize_transport`, `authority`
und optional `timeout`. Alle Pfade sind absolut; `workspace` ist ein frischer
externer Pfad. Der registrierte Host liefert die Funktion `authorize_transport`
und eine native `PublicationAuthority`; Paketdaten dürfen sie nicht erzeugen.
Die Funktion erhält den Paket-SHA, Repository, ursprüngliche Referenz, Projekt-ID
und Proposalbindung und muss exakt True liefern. Der Writer prüft seine eigene
Authority anschließend unter der nativen Projektsperre erneut.

`receive()` führt synchron genau einen zugelassenen nativen Apply aus.
`proposal_received` bedeutet ausschließlich einen nachgewiesenen lokalen Draft.
`draft_completion`, `patchharbor` und `receiver_failure` zeigen die tatsächlichen
getrennten Teilzustände. Ein fehlgeschlagenes PH-Result ist kein sicherer Retry.
Für fachliche Änderungen folgen unabhängiges Validate, Check, menschliches
Review und der normale transaktionale Proposal-Apply. Der Adapter benötigt einen
Linux-Host mit Python und Bash; die Sandbox benötigt diese Hostwerkzeuge nicht.

Ein nachweislich empfangenes Paket kann mit `prior_result` und
`prior_result_sha256` schreibfrei erneut beobachtet werden. Das Originalresult,
der aktuelle native Zustand, die erhaltenen Paket-/Draftbytes und der native
SpecRoad-Abschluss müssen übereinstimmen. Es gibt dann keinen zweiten Apply.
Bei fehlenden oder veränderten Belegen bleibt die Übernahme gesperrt.

Der Transportbeleg enthält die nach dem Schreiben erneut nativ gelesene
historische Abschlussbeobachtung. Die unmittelbare Schreibantwort darf
`current_target_verified=true` und `replayed=false` melden; das spätere reine
Lesen meldet entsprechend `false` und `true`. Diese Beobachtungen sind keine
bytegleichen Antworten. Der gespeicherte historische Beleg wird beim Replay
weiter vollständig und kanonisch verglichen, einschließlich dieser Flags.
