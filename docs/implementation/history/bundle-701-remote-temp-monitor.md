# Korrektur 701 — Remote-Tempbereich und Monitor-Kopf, offener Rest 18.s.C

Datum: 15. November 2026. Nativ geprüfte Quelle:
`specroad-apply_Result_193306_1114_ffda3d.zip`, SHA-256
`50ec6dcd9a20724ca65ffd146ee77bb71ead1f419279eb066dd6f5da48ad82d5`.
Bundle 700 hat 18.s.W und 18.s.R mit jeweils 10836 bestandenen Tests committed.
HEAD ist `d41e34938fdc1589d0196bf30f789d6306c2a447`; der vollständige
uncommittierte C-Zielstand bleibt erhalten. C hat 10831 bestandene Tests und
einen Fehler, keinen Commit. Der Fortschritt ist bis zur grünen C-Abnahme
764/918; 765/918 und 18.t.W bleiben bedingte Zielwerte der C-Stage.

## Ursache und Reparatur

`test_profiles.ProfileWorkTests.test_build_identity_includes_profile_bytes`
scheiterte auf einem Remote-Worker mit `OSError: [Errno 122] Disk quota exceeded`
beim Schreiben des zweiten echten Builds. Eine lesende Hostprüfung zeigte
ein kleines quotiertes tmpfs für `/tmp` und ausreichend freien Plattenspeicher
im konfigurierten Host-Arbeitsbereich. Weder der Build-Identitätsvertrag noch
die Testassertion war die Fehlerursache.

Die Remote-Vorbereitung erstellt jetzt neben dem jeweiligen Quellsnapshot
einen privaten Tempbereich. Bereits der Proxy erhält die vier üblichen
Temp-Umgebungswerte, bevor Worker, Supervisor-Kinder oder spätere Live-Worker
entstehen. So erreicht derselbe Bereich auch `tempfile`, pytest-Fixtures und
Kindprozesse. Die Testmenge, Priorität, Hostlimits, Quellenprüfung, Fehlergates,
Messhistorie und lokale Apply-Tempvorgaben bleiben unverändert. Kein stiller
Retry, keine Quotenänderung und kein Löschen bestehender Diagnose-/Messdaten.

## Ausdrücklich angeforderter privater Arbeitsschritt MONITOR-HEADER

Die vorbereiteten Vorherbytes von `tools/dev/status/monitor_view.py` stimmen
exakt mit diesem Result überein. Der vollständige vorbereitete Unterschied
wird einmalig übernommen: Commitfolge vor den Hostzeilen, dynamische Kopfhöhe,
bei Platzmangel benannte ausgeblendete Hosts und weiter Platz für Suche,
Spaltenkopf, mindestens eine Testzeile und Fußbereich. Die frühere private
Vorbereitung bleibt als lokaler Beleg erhalten. Keine Änderung an `[copy]`
oder an der History-Abfrage und keine neuen Darstellungstests.

## Fortsetzung und Nachweisgrenze

Genau der offene Rest `18.s.C` wird mit seiner ursprünglichen Rolle,
Commitnachricht und vollständigen Pflichtauswahl fortgeführt. Die beiden
kleinen Werkzeugkorrekturen sind Bestandteil dieses gebundenen Reparaturschritts;
kein zusätzlicher Planfortschritt und keine Wiederholung von W/R. Die bestehende
C-Produktimplementierung und deren W/R-Testbytes bleiben unverändert.

Das Apply-Gate enthält zusätzlich den vollständigen Profiltest, Remote-/Pool-,
Supervisor-/Live-/MOVE-/Kopien- und vorhandene Monitor-Datenregressionen.
Neue Prozessabnahmen prüfen die private Anlage zweier getrennter Remote-Läufe
sowie die Temp-Vererbung über den echten Proxy, Supervisor, Worker und dessen
Kind. Die vorhandene native pytest-Poolabnahme prüft zusätzlich `tmp_path`
und `tempfile`, ohne bisherige Phasen-/Quellen-/History-Assertions zu entfernen.
Alte Testidentitäten und Rotationsanker bleiben; neue Nummern werden angehängt.
Dev prüft nur Syntax, statische Deltas, reine Collection und native Paketbindung.
Erst das erfolgreiche Apply-Gate erlaubt C-Commit und Fortschrittsabschluss.
Control bleibt gestoppt; der bestehende Watcher übernimmt die übergebene ZIP.
