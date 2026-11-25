# Bundle 817 — Byteparser und eingefrorene Forcebefunde

Maßgebliche Quelle ist das native Fehler-Result
`01a4b88029c094df5ad01b8f8a2e948fdce2fbaa7738823c1a2ae3740aaffd8d`.
Bundle 816 hat den Klärungscommit **FORCE-OPERATIONS-816** nach **9.886**
bestandenen Tests als `c2a97f6e8fce68930a4e0a9029876dbcc3025355`
committed. Der folgende vollständige W-Testlauf endete mit **26.299 bestanden,
92 fehlgeschlagen**, ohne Skip/XFail, Timeout oder Abbruch. W wurde nicht
committed; R/C wurden nicht installiert. Der erfolgreiche Präfix bleibt
erhalten und wird nicht wiederholt. Bestätigt sind weiterhin 903/999 Positionen.

## Diagnose und begrenzte Korrektur

- **88 Byteparserfälle:** Das Archivmodul lud die neue Force-Policy erst
  innerhalb der Byteverarbeitung. Die unveränderte Isolationsprüfung verbietet
  dort alle Dateiöffnungen und erkannte daher auch den verspäteten Modulimport
  als unerlaubten Effekt. Die reinen Policyfunktionen werden jetzt mit dem
  Archivmodul geladen, vor Beginn der Byteverarbeitung. Die Auditgrenzen,
  Netzwerk-/Prozesssperren, ursprünglichen Eingaben und sämtliche normalen
  Ablehnungsoracles bleiben unverändert, sowohl für Core als auch Distribution.
- **Zwei öffentliche Force-Aufrufe:** Ergebnisobjekte frieren verschachtelte
  Bindungen als Mapping-/Tuple-Werte ein. Eine flache dict-Kopie entfernte
  diese inneren unveränderlichen Typen nicht; die strenge JSON-Kanonisierung
  wies sie ab. Die gemeinsame Aufrufgrenze benutzt nun den bestehenden
  rekursiven thaw-Adapter vor der weiterhin vollständigen Overrideprüfung.
  Negative Modellbefunde, Work-Eigentümer und ursprüngliche Requestdaten
  werden vollständig erhalten; weder JSON-Validator noch Forcevertrag werden
  gelockert.
- **Zwei veraltete Optionserwartungen:** X.12.3 erlaubt --force bei work.resume
  sowie --force-owner als gemeinsame explizite Auswahl. Der fehlende Workpfad
  bleibt ein Modellfehler mit unveränderten Dateien und ohne benutzten
  Override; die entfernten Takeover-Optionen bleiben Usagefehler. Die
  maschinenlesbare Description-Abnahme enthält jetzt die vollständige
  Optionsmenge und prüft weiterhin fehlenden veränderlichen gemeinsamen Zustand.

Die Korrektur gilt ab W und bleibt in R/C erhalten. Keine Sicherheitsprüfung,
Testvariante oder stabile Testidentität wird entfernt. Insbesondere bleiben
die 88 Isolationsfälle selbst bytegleich; ihre Zugriffssperre wird nicht
umgangen oder abgeschaltet. Alle 92 Fehlerfälle, ihre vollständigen Dateien,
die vorherigen Pflichtmengen und die betroffenen Produktverbraucher werden
in jeder Folgestage verpflichtend ausgewählt.

## Vollständiger Rest und Abnahme

Der genaue offene Rest bleibt **21.e2.W**, **21.e2.R**, **21.e2.C**, jeweils
mit Rolle implementation und ursprünglicher Commitnachricht. W enthält den
vollständigen betrieblichen Forceumfang, R die bereits geplanten Identitäts-,
Quellenwechsel- und Belegprüfungen, C deren strukturelle Bereinigung mit
bytegleichen R-Tests. Keine weitere Aufteilung, neue Klärung oder Scopeerweiterung.
Spezifikation 0.2.109 und alle aktiven Katalogbindungen bleiben unverändert.

Jede Stage benötigt ihr eigenes gefiltertes N=3-plus-Pflichtauswahl-Gate vor
dem Commit. Aus dem belegten Präfix folgt W-Gruppe 1, danach R-Gruppe 2 und
C-Gruppe 0; nur erfolgreiche Commits schalten weiter. Die Zielstände
904/905/906 gelten erst nach dem jeweiligen eigenen Gate. Danach folgt 21.f.W.
Die frühere Vorbereitung in Bundle 816 ist kein bestandener Produktnachweis.
Historische Ressourcenbelege bleiben bytegleich und die finale CPU-/RSS-
Abnahme pending. Dev führt nur statische Prüfung, reine Collection und native
Paketvalidierung aus; die Korrektur ist noch keine bestandene Apply-Abnahme.
