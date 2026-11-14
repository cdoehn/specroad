# Bundle 684 — Reset-Abnahme und vollständiger R/C-Rest

14. November 2026. Das nativ geprüfte Fehler-Result von Bundle 683 hat SHA-256
`55851216a6ae098e57c88511a8731e88744b5db79dcc350511c046fb6c3248d1`.
WORKER-BUDGET-683.W wurde nach 9020 bestandenen Tests als
`54ff2a946a576bebf8e53e674751b6641e4cc342` committed. R meldet 8930 bestandene
und einen fehlgeschlagenen Test; C wurde nicht ausgebracht.

## Fehler und begrenzte Korrektur

Der neue Test
`test_explicit_reset_uses_twenty_marker_and_preserves_original_contract`
griff nach abgeschlossener Übernahme auf `validate_history(ledger)['version']`
zu. Dieser Validator prüft auch abgeschlossene Belege, gibt jedoch nur einen
noch offenen Übernahmebeleg zurück. Nach `adopt` ist `None` deshalb korrekt.
Der Fehler ist die falsche Zuordnung des Belegzustands im Test.

Die Abnahme prüft jetzt den offenen Beleg vor der Übernahme: Version 2 und
ausdrücklicher Reset. Danach verlangt sie keinen offenen Beleg mehr und liest
über `active` den abgeschlossenen Beleg des exakten Ziel-Results. Dieser muss
vollständig mit dem vorherigen Beleg übereinstimmen. Die Assertions für das
neue Zwanzigerbudget, den unveränderten ursprünglichen Nullvertrag und keinen
Modellaufruf bleiben erhalten. Der Test wird weder übersprungen noch gelockert;
Control-Verhalten, Historienformat und normative Spezifikation ändern sich nicht.

## Vollständiger Rest und Nachweisgrenze

Die Folge führt ausschließlich WORKER-BUDGET-683.R und WORKER-BUDGET-683.C
mit ihren bisherigen Rollen implementation, Nachrichten und Pflichtabnahmen
fort. Der erfolgreiche W-Commit wird nicht wiederholt. Alle fünf im Result
erhaltenen R-Änderungen gehören zum ersten Commitumfang; Vorherbytes und
Korrekturbindung stammen aus dem aktuellen Fehler-Result.

C behält die geplante Konsolidierung gemeinsamer Worker-/Budgetgrenzen.
Jede Stage wird einzeln ausgebracht, im Apply mit N=3 plus der vollständigen
Pflichtauswahl geprüft und erst danach committed. Alle 27264 Testidentitäten,
ihre Nummern und die bisherigen 144 Pflichtdateien bleiben erhalten. Dev
führt nur statische Prüfung, reine Collection und native Paketvalidierung aus;
die reparierte Abnahme ist vor ihrem neuen Apply-Gate nicht als bestanden belegt.

Die Produktpositionen bleiben bei 762/918 und nächster Position 18.s.W.
Recovery-Rückbau, aktive Katalogbindungen und private Originalvorbereitung
bleiben erhalten. Kein Control-Resume, Deployment oder Betriebsbudgetreset.
