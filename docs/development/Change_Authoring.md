# Actor- und Requestbindung normaler Schreibaufträge

Schritt 5.h: explizite Single-User-Akteursdeklaration gemäß Kapitel 9.5,
11.10 und SR-REQ-0236/0382/0543. Die Deklaration ist Audit-/Policyinformation,
keine kryptografische Authentifizierung und keine Dateisystemberechtigung.

`prepare_authoring_request` normalisiert durch strikte Prüfung, nicht durch
Ändern von Identitäten: Actor und Request-ID werden weder getrimmt noch in
Kleinbuchstaben gewandelt. Eine Request-ID hat den Schreibnamensraum und
exakt `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`. Fremde ID-Objekte werden nicht über
`str()` übernommen. Dieselbe Rohzeichenfolge in einem Analyzerrequest hat
keine Schreib-Receiptwirkung.

Jeder echte AI-/CI-Write verlangt eine Request-ID (fehlend: Code 2). Direkte
KI-Änderungen verlangen den Proposalweg (sonst Code 7). Die ausdrücklich
benannten Proposal-Fachbefehle werden an ihre Spezialworkflows verwiesen;
ein Kommando-Label allein bestätigt weder Inhaltsfreigabe noch Berechtigung.
Human-Reviews können nicht durch AI-/CI-/Tool-Deklarationen erzeugt werden.
Die Command-ID ist eine Auswahl durch den vertrauenswürdigen Caller, keine
vom Plan eingebettete frei ausführbare Funktion.

`bind_plan_authoring` bindet zusätzlich den tatsächlichen Planhash und seine
Basis/Scope-Angaben. `operation_sequence_sha256` ist der Hash der vollständigen
geordneten normalisierten Operationsliste; der Handoffhash bindet zusätzlich
Akteur, Command, Request-ID und Plan. Das ist noch NICHT der zukünftige
persistente Idempotenz-/Receiptvertrag. Keine IDs oder Receipts werden erzeugt.

Die normalen Apply-Einstiege prüfen die Authoringpolicy vor Fachprüfern und
vor dem Aufruf des registrierten Transaktionsbackends. Der Backendrequest
enthält diese Bindung und wird innerhalb der Transaktion erneut hergestellt.
`as_proposal=True` leitet niemals in den generischen Writer um: solange dort
kein Proposalworkflow integriert ist, gilt `proposal_workflow_required`.
Die reine Dry-Run-Bibliothek bleibt eine schreibfreie Vorschau; sie verleiht
keine spätere Write-Berechtigung. Der echte Apply prüft die Policy erneut.

Grenzen: keine neuen CLI-Befehle, keine tatsächlich authentifizierten Personen,
keine Proposal-Freigabeauswahl, kein Request-Receipt-Store, keine Wiederholung
mit Exactly-once-Zusage, keine neuen Projektlocks oder Dateisystemwriter.
`write_authorized=false`, `actor_authenticated=false` und
`idempotency_guaranteed=false` bleiben ausdrücklich im Policybericht.
Die tatsächliche Autorisierung und Livezustandsprüfung bleiben Aufgabe der
vertrauenswürdigen Anbindung. Spezialoperationen sind keine freien Fieldpatches.

Lokale Gates: ausschließlich neue/direkt betroffene Dateien mit vier Workern.
Vollsuite nur in CI; Bundle 031 parallel, nächster Doppelmodus bei Bundle 035.
Vor neuen Commits muss der fehlende parallele UND serielle CI-Nachweis des
bereits lokal abgeschlossenen Bundles 030 vollständig verifiziert sein.
