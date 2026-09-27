# Dry-Run und gespeicherter Change-Apply (5.g)

`dry_run_change` liefert den vollständigen unveränderten speicherbaren Plan,
semantischen Diff, direkten Impact, Diagnosen und erwartete Modellwurzel aus
`assess_change_target`. `execute_change_request` erzeugt für direkte Ausführung
und Dry-Run mit identischen Eingaben denselben Plan. IDs, Actor, Request-ID und
Zeit werden nicht aus Umgebung oder Uhrzeit erzeugt. Der Aufrufer gibt sie an.

Ein Dry-Run ist eine reine Auswertung gelieferter Bytes; kein Backend wird
angesprochen, kein Lock genommen und kein Journal/Receipt angelegt. Explizite
Fachprüfer sind vertrauenswürdiger Python-Code mit Read-only-Vertrag, nicht
Sandboxcode. `fail_on_change` liefert bei gültiger Prüfung und tatsächlicher
semantischer Änderung Code 1, ansonsten 0. Ungültige oder unvollständige Ziele
bleiben Fehler; die Schwellwertoption verdeckt weder Fehler noch fehlende Gates.
Auf einem tatsächlichen Write ist `fail_on_change` nicht zulässig.

`apply_change_plan` nutzt denselben gespeicherten Plan und dieselbe vollständige
Zielprüfung. Eine explizit registrierte `ChangeBackend`-Integration öffnet die
Transaktionsgrenze; dort werden frische Modellbytes, lokale Projektbindung und
Prüfergebnis erneut abgeglichen. Erst dann wird der unveränderte Auftrag einmal
an `publish` übergeben. Rückmeldung, Request-ID, Planbindung, betroffene Pfade,
Zielhash und tatsächlich erneut gelesene Zielbytes müssen übereinstimmen.

## Verantwortungsgrenze

Diese Stufe implementiert die Planung-/Ergebnis-/Publikationsschnittstelle,
noch keinen nativen Dateisystemwriter und noch keinen `specroad change apply`
CLI-Befehl. Ohne ausdrücklich registriertes Backend endet ein Write mit
`transaction_backend_required`. Ein als validiertes Ziel gespeicherter Wert,
ein `human`-Label oder ein Receipt-Dictionary erteilen keine Schreibberechtigung.

Der vertrauenswürdige Hostadapter ist für tatsächliche Autorisierung, vollständige
Live-Inventur, Recoveryvorprüfung, echten Projektlock, Journal, Request-Receipt
und Dauerhaftigkeit verantwortlich. Seine Kennung ist keine Authentifizierung.
Diese Infrastruktur folgt insbesondere in 5.h und den Transaktionsschritten ab
5.i. Eine gültige Backend-Rückmeldung plus gelesene Zielbytes bestätigt den
Adapterablauf, nicht unabhängig fsync oder gespeicherte Receipt-Dateien.

Tests verwenden eigenen synthetischen Speicher und echte Dateien in temporären
Verzeichnissen. Der Testadapter ist bewusst kein Produktwriter; seine erfolgreiche
Dateiwirkung ist kein Produktionsnachweis für Crashsicherheit. Die Anforderungen
bleiben deshalb `partial`, bis die native Integration tatsächlich geprüft ist.

Ein Backendfehler nach dem Betreten der Transaktionsgrenze lässt den beobachteten
Schreibzustand `unknown`; kein automatischer Retry oder destruktiver Rollback.
Insbesondere darf ein verlorener Rückgabewert nach einem Write nicht zur Behauptung
führen, es sei nichts geschrieben worden. Die folgenden Schritte können den
Ausgang später mit echten Transaktionsbelegen auflösen.

## Tests und CI

Lokal nur die neuen `test_change_execution*.py`-Dateien, vier Worker. Keine lokale
Vollsuite/serielle Vollsuite. Katalogsammlung ist kein Lauf von Testkörpern. Am Ende
von Bundle 030 startet die GitHub-Vollsuite parallel und seriell mit Vergleich,
für CPython 3.10–3.14. Der vorhandene CI-Beobachter und Resulttransport bleiben
unverändert. Meldungstexte, Layout, Farben und Dokumentation sind keine Testoracles.
