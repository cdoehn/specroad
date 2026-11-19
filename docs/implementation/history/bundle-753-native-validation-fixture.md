# Bundle 753 — vollständige native Validierungsdaten

19. November 2026. Maßgebliches natives Fehler-Result:
SHA-256 `7332e8e38f2e01da17205cafef58d93770ce8341eb17f513c0b40966dc7b23d4`,
HEAD `6a0408c800e82faf5f732f77fc5c92ab54837bfa`.
Bundle 752 bestätigte 19.g.W/R/C und 19.h.W mit jeweils eigenem Apply-Gate
und Commit. Bestätigt sind 823/918. 19.h.R meldet zwei fehlgeschlagene und
11.149 bestandene Tests; ausschließlich 19.h.R und 19.h.C bleiben offen.

Die zwei Varianten von test_native_validate_and_its_lint_pipeline_do_not_initialize_analyzers
verwenden bislang das kleine Subjectleser-Projekt ohne Profile. Die native
InspectionSnapshot verlangt über compose_profiles hingegen ein vorhandenes
core@0.2.0. Die statische Pfadprüfung erklärt damit den Modellfehler 3 vor
der beabsichtigten Lint-Ausführung. Die frühere Vorbereitung belegt diese
Verhaltensabnahme nicht; das native Fehler-Result ist maßgeblich.

Die Korrektur ergänzt ausschließlich diesen Testaufbau um die vorhandenen
nativen Produktions-Validierungshelfer: ausgeliefertes Core-/Softwareprofil,
explizit gebundene kleine Sprachregisterdaten für en und de-DE und eine
passive lokale SRX-Regel. Deren Warnbefund muss für beide unveränderten
Anweisungstexte tatsächlich aus dem nativen profile_lint-Gate erscheinen.
Zusätzlich werden vollständige Prüfung, erfolgreiche Sprachdeklarationsprüfung,
Code 0 ohne strict und Code 1 mit strict geprüft. Modellimporte, Prozess-/
Netzwerkaufrufe und Schreibversuche bleiben gesperrt; Inventarbytes bleiben
unverändert. Kein Validator wird ersetzt, kein Fehlercode 3 als Erfolg erlaubt.
Die vollständigen Register- und Produktions-Validierungsreferenzen bleiben
unverändert und werden zusätzlich verpflichtend ausgewählt.

Korrekturbindung: `6538ff52f8521ad081159890d69a8d252fa935dc5868e89af5fc566c209b5dbf`.
Beide offenen IDs, Rollen implementation, Nachrichten und Abnahmen bleiben
erhalten. Alle 15 uncommittierten Quellpfade gehören zum ersten Commitumfang;
vollständige Vorherbytes stammen aus dem effektiven neuen Snapshot.
Die vier erfolgreichen Commits werden nicht wiederholt. Die ursprünglichen
Produktzustände h.R und h.C bleiben bytegleich; C trennt weiterhin den
Dateiadapter vom bekannten internen Ausführungsadapter und erhält sämtliche
R-Testbytes. Testidentitäten, Parameter und stabile Nummern bleiben erhalten.
Historische Belege 749–752 werden nicht umgeschrieben.

Die anschließende priorisierte Gruppe 19.i wurde mit T.3 und Anhang P sowie
dem bestehenden Workcodec abgeglichen. Dieser bindet vollständig vorliegende
Eingangsbytes unveränderlich und akzeptiert normalized_arguments nur mit
arguments/options. Frühe analysis_id und noch unvollständiger Snapshot
brauchen eine zusammenhängende Erweiterung von Bindung, Codec und Resume.
Diese Reparatur hängt keinen unvollständigen 19.i-Teilzustand an und führt
keine neue Detailentscheidung in den belegten Korrekturrest ein. 19.i.W/R/C
und nachfolgende Work-Abnahmen bleiben vollständig unverändert offen.

Zielstand **19.h.R** zählt erst nach seinem eigenen Apply-Gate und Commit
**824/918**; danach folgt **19.h.C**.
Jedes Gate behält die bisherige ungefilterte Pflichtauswahl und alle
früher korrigierten Oracles zusätzlich zur fälligen gefilterten N=3-Gruppe.
Dev führt ausschließlich statische Prüfung, reine Collection und native
Paketvalidierung aus. Dies ist kein bestandener Verhaltenstest oder
Vollsuiten-/Plattformnachweis. Keine Specänderung, neue Klärung oder
Budgetänderung; Übergabestatus patch_ready.
