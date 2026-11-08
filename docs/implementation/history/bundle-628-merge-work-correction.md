# Bundle 628 — Korrektur des offenen Schritts 17.l.W

8. November 2026. Quelle ist das nativ geprüfte Fehler-Result
`specroad-apply_Result_194318_1107_26d0df.zip`, SHA-256
`b6fa44abca9775c3182849f62bb876348db0697dcecc2a4c0a7aa558d5c8f543`.
Sein HEAD ist `3a03be16a03524e140b948a7f4236f58ae8aaa0b`, sein
Fingerprint `bf03d177dd577158` mit `patchharbor-state-v1`.

Der Klärungscommit `MERGE-WORK-627` hat sein Gate mit 7.054 bestandenen Tests
abgeschlossen. `17.l.W` wurde danach vollständig ausgebracht, aber nicht
committed. Das Gate endete nach ungefähr 71 Minuten mit Exit 1. Die gebundenen
Beobachtungen enthalten 11.487 bestandene und 69 fehlgeschlagene Testidentitäten;
die zusätzliche pytest-Untertestzählung ist kein weiterer Erfolgsnachweis.
Der bestätigte Produktfortschritt bleibt vor dieser Korrektur 726/900.

## Ursachen und Korrektur

- Das neue Ergebnisschema verwendete eine Typenliste, während der bestehende
  geschlossene Schema-Prüfer einzelne Typen und `anyOf` unterstützt. Die
  semantisch gleiche `anyOf`-Form erhält `boolean|null`, ohne den Prüfer zu
  erweitern. Damit werden auch Schema-Katalog, Schema-CLI und die betroffenen
  Work-Abschlüsse wieder prüfbar.
- Die neue gemeinsame Erfolgsvorlage enthielt kein Hauptdokument. Die native
  Vollprojektprüfung meldete deshalb korrekt `document_primary_missing`.
  Die Vorlage erhält das Dokument vor der nativen Baseline-Erzeugung; alle vier
  Quellarten bekommen weiterhin dieselben vollständig gebundenen Daten.
- Der allgemeine Schreibwächter verbot zugleich jeden Prozessstart und damit
  die vorgesehenen nativen Git-Leseaufrufe. Die öffentliche Quellenmatrix nutzt
  jetzt den vorhandenen Wächter für ausschließlich zulässige Git-Lesebefehle;
  Schreib-, Netzwerk- und fremde Prozessaufrufe bleiben verboten.
- Drei ältere Registry-/Capability-Erwartungen berücksichtigen den neuen
  `merge.plan`-Befehl. Ein Registry-Ausschnitt mit ausschließlich diesem
  fortsetzbaren Planer muss die Work-Engine tatsächlich ausweisen.

Zwei zusätzliche Regressionen prüfen den strikten booleschen/Null-Vertrag
einschließlich Ablehnung von Zahlen und anderen Werten sowie den weiterhin
negativen vollständigen Work-Abschluss bei fehlendem Hauptdokument. Bestehende
Testidentitäten und Parametervarianten bleiben erhalten. Die neuen Nummern
werden ausschließlich angehängt. Die öffentliche Quellenmatrix verlangt nun
zusätzlich ein tatsächlich validiertes, unverändertes Ziel.

## Gebundene Übergabe und offene Abnahme

Der Commitplan setzt ausschließlich die belegte offene ID `17.l.W` mit ihrer
unveränderten Rolle `implementation` und exakten Plan-Commitnachricht fort.
Der erfolgreiche Klärungspräfix wird nicht wiederholt; es gibt keine neue
Detailklärung. Vollständige Vorherbytes und der gesamte noch uncommittete
W-Umfang sind an dieses Fehler-Result gebunden. Die historische Vorbereitung
in [Bundle 627](bundle-627-merge-work.md) bleibt als damaliger Nachweis erhalten.

Die bisherige Pflichtauswahl bleibt vollständig enthalten. Alle geänderten
Testdateien, neuen Regressionen und jede zuvor fehlgeschlagene Testidentität
gehören zum neuen Apply-Gate, gemeinsam mit der weiterhin fälligen gefilterten
N=3-Gruppe. In Dev wurden keine Testkörper, Fixtures oder Test-Unterprozesse
ausgeführt. Syntax, reine Collection und native Paketvalidierung belegen
ausschließlich die Vorbereitung.

727/900, `17.l.W` als abgeschlossen und Bundle 628 sind nur der vorbereitete
Zielzustand nach erfolgreichem Gate und tatsächlichem Commit. `17.l.R/C`, die
öffentliche Merge-Apply-/portable Gesamtintegration und M17-Abnahme bleiben offen.
Diese Testkorrektur aktualisiert keine installierte Control-Version und startet
keinen Dienst, keine CI und keine eigene Apply-Schleife.
