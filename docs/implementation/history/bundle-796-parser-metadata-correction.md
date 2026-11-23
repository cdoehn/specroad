# Bundle 796 — Metadatenfehler an ihrer Quelle melden

23. November 2026. Das native Fehler-Result mit SHA-256
`222d9ea6c841d7b56d586806d019ee8bd146ac53360418da2b355a8f4bec0856`
belegt für Bundle 795 im Gate von **21.b.W**: **1 fehlgeschlagener,
9.400 bestandene Tests**, kein Commit. Der bestätigte Stand bleibt
**891/996**, HEAD `a395c08e6b1f385af0e179120d30843dc7e2341d`.
Die Häkchen und Fortschrittswerte dieses Zielstands **21.b.R** gelten erst
nach seinem eigenen erfolgreichen Apply-Gate und Commit.

Der bestehende Fehlerfall ersetzt die Eintragsmetadaten durch
`{"extra":true}` und verlangt `artifact_type_mismatch` am betroffenen Block.
Der Parser leitete zuvor `children=[null]` für den Elternknoten ab und
prüfte diesen vor dem Kind. Dadurch verdeckte `schema_type` am Elternknoten
die eigentliche Metadatenverletzung. Die bereits vorhandene Typprüfung
erfolgt jetzt vor der Hierarchieauswertung, in allen drei Zielständen.
Unverändert bleiben die Ableitungs-, Schema-, Identitäts- und Quellprüfungen.

Die Korrektur bindet den vollständigen offenen Präfix **21.b.W/R/C** mit
allen bisherigen IDs und Rollen. Vollständige Vorherbytes stammen aus dem
erhaltenen Fehlerstand; der erste Commitumfang umfasst auch die bereits
ausgebrachten, noch uncommitteten Dateien. Kein erfolgreicher Commit wird
wiederholt. Der vollständige ursprüngliche Parser-/Quellenumfang aus
[Bundle 795](bundle-795-plan-sources.md) bleibt erhalten; dessen Bericht
beschreibt eine Vorbereitung, keinen erfolgreichen Apply-Abschluss.

Alle bisherigen Testquellen, Identitäten, Parametervarianten, Assertions,
Nummern und Pflichtauswahlen bleiben erhalten. Insbesondere wird das
fehlgeschlagene Oracle weder angepasst noch ausgelassen und gehört in
jedes der drei eigenen Gates. R enthält weiterhin die vollständigen
Randfall- und Tokenabnahmen; C extrahiert dieselben Definitionen wie R und
führt kein neues Fachverhalten ein. Dev-Verhaltenstests: **0**; Syntax,
reine Collection und native Paketprüfung sind keine Verhaltensabnahme.

Keine normative Lücke und kein Klärungscommit. Nach erfolgreichem C wären
**894/996** Positionen abgeschlossen; danach folgt der vollständige native
Authoringvertrag **21.c.W/R/C**. Graphintegration, Plattformnachweise und
die menschlichen Endabnahmen bleiben offen. Keine Release- oder
Benutzungsfreigabe, Dienstaktion oder nachträgliche Budgetänderung.
