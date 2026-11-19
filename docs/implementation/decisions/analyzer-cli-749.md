# ANALYZER-CLI-749 — Explizite Datei- und CLI-Bindungen

19. November 2026; delegiert gemäß SPECROAD-DECISION-1 und 2.4.3.1,
gebundener Vertrag 4 mit positivem Restbudget. Scope sind vollständig 19.g/h,
SR-REQ-0689/0690 und 0694–0696. Die native erfolgreiche Basis 748 enthält
vollständige Request-/Report-/Package- und Aktualitätsvalidatoren, aber noch
keinen Analyzer-CLI- oder Workeradapter. Alle sieben vorherigen Stages sind
belegt committed; die Quelle ist im Bundleverlauf mit ihrem SHA-256 gebunden.

T.5 verlangt CLI und sichere Dateien, T.8.1 verlangt unabhängige aktuelle
Inputs, lässt deren CLI-Zuführung offen. Ebenso fehlen konkrete Regeln für
die Kombination mehrerer Exitgründe und das maschinenlesbare Variadicargument.
Eine implizite Konfigurationssuche nach externen Descriptoren wäre zusätzliche
Autorität; Kopieren der gespeicherten Requestwerte wäre ein zirkulärer
Aktualitätsnachweis. Einzelne freie JSON-/Settings-Schalter würden den vorhandenen
geschlossenen Vertrag duplizieren. Gewählt wird eine optionale explizite
passive JSON-Datei mit genau den vorhandenen vier Inputkoordinaten.

Die bestehende native Root-/Symlink- und atomare Create-only-Publikation hat
Vorrang vor einem neuen Überschreib- oder Persistenzprotokoll. Vorhandene
Eltern sind Pflicht; keine implizite Verzeichnis-/Work-Erzeugung. Bytegleiche
Ziele sind ohne Mutation No-op; andere Originale bleiben Konflikt. Externe
Ziele erfordern einen expliziten absoluten Pfad oder Ausgabe-Root. Ein freier
Projektpfad würde Modelldateien gefährden und wird nicht eingeführt.

Evaluate mit alten oder unprüfbaren Berichten darf keinen Erfolg vortäuschen.
Die vorhandenen Codes bleiben getrennt, ein deterministischer Gesamtcode
ersetzt nicht die einzelnen sichtbaren Gründe. Der gemeinsame Registrybinder
erhält einen letzten wiederholbaren Positionsparameter, statt Evaluate einen
zweiten, abweichenden Parser zu geben. Skalare Verträge bleiben byte-/API-kompatibel.

Normative Zielregel: T.5.2. Positive Abnahmen: vollständige native Auswahl,
Projektlosigkeit datentragender Dateien, exakter Originalimport, alle Reports,
unabhängige Aktualität, Fremddescriptoren ohne Worker. Negative Abnahmen:
fehlende/fehlerhafte Inputs, verbotene Schreiboptionen, Quellenwechsel,
Symlinks/Hardlinks/Sonderziele, abweichende Ausgabebytes, unzulässige Overrides
und instructionartige passive Daten. Partialumfang bleibt manifestgebunden.

Die Entscheidung liegt vollständig im bestätigten Scope, ist versioniert
rücknehmbar und erhält Originaldaten, Kompatibilität, Sicherheitsniveau und
alle menschlichen Review-/Evidencepflichten. Keine fremden Fakten, Credentials
oder individuelle Nutzerfachfreigabe werden erfunden. Worker, Distribution,
Sprachpolicy und durable Workadapter behalten ihre späteren eigenen Gates.
Die Klärung ist keine Produktabnahme. Alle echten W/R/C-Zustände folgen separat;
Dev führt keine Verhaltenstests aus, nur erlaubte statische/Collection-Prüfungen.
