# Transaktionsprüfung vor normalen Projektaufrufen

Aktueller Stand nach 18.s–18.x und RECOVERY-REMOVAL-006. Der vollständige
Betriebsablauf steht unter [Unterbrochene Writes](Interrupted_Writes.md).

`specroad.changes.transaction_preflight` beobachtet aktuelle Betriebsmetadaten
vor normaler Modellnutzung. Unterstützt sind `READ_ONLY`, `PLAN_OUTPUT`,
`GENERATED_OUTPUT` und `NORMATIVE_WRITE`, jeweils mit explizitem Dry-run-Modus.
Eine Klassenangabe authentifiziert keinen Aufrufer.

Der begrenzte Preflight lädt kein reguläres Modell, startet keine Fachoperation
und verändert weder Schutzdateien noch Receipts. Ein klarer Zustand liefert
`transaction_preflight_passed=true`, aber keine Schreibberechtigung. Ein aktiver
Writer endet mit `project_writer_active`/Exit 6; ein beschädigter oder unklarer
Zustand mit `project_corrupted` beziehungsweise `project_unknown`/Exit 5.
Begrenzte Diagnose erlaubt keinen automatischen Schluss aus nicht beobachteten
Dateien oder nicht sichtbaren Prozessen.

`recovery_attempted`, `recovery_completed`, `mutation_possible`,
`normal_operation_started` und `request_consumed` bleiben false. Eine neue
Request-ID, `authority` oder `actor` aktiviert keine Reparatur; die letzten
beiden Parameter werden nur als kompatible Aufrufparameter weiter angenommen.
Aktuelle Konfigurationen akzeptieren `auto_recover` nicht mehr. Alte
Recovery-Entscheidungen, Finalisierungs- und Bereinigungsadapter sind entfernt.

Die lesende Freimeldung ist keine Reservierung. Ein tatsächlicher neuer Writer
prüft aktuelle Quellen, Berechtigung und Schutzbestand erneut unter seinem
nativen Lock. Ein unterbrochener Root bleibt erhalten und gesperrt; Wiederanlauf
erfordert einen gültigen separaten, vom Nutzer erstellten Git-Checkout.

Die gemischten Regressionen in `test_transaction_preflight*.py`,
`test_preflight_metadata.py`, `test_write_guard*.py` und `test_git_restart*.py`
prüfen diese Grenzen. Testausführung erfolgt ausschließlich im eigenen Apply-
Gate nach [Testing.md](Testing.md); historische Recovery-Tests sind kein
Nachweis der aktuellen Abbruchsperre.
