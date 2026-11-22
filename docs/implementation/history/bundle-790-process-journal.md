# Bundle 790 — Prozess- und Journalgrenzen des offenen C-Rests

22. November 2026. Das native Result mit SHA-256
`473d3f14945ce4b7b6e09be3fb8e5b371d4aed715ceb5c3b47d5983c58150571`
bestätigt 20.h.W mit 12.278 bestandenen Tests und Commit
`2a887edeed9a92cddfda4b91534393d456b43946` sowie 20.h.R mit 12.507 Tests
und Commit `29011d0b185adcad55abf62b002538fc98d33f07`.
Damit sind 887/918 Produktpositionen committed. C blieb nach 12.527 bestandenen
Tests, einem Fehler und einem Fixture-Setupfehler offen. Die Pythonmatrix aus
[789](bundle-789-validation-matrix.md) ist im erfolgreichen W/R-Präfix erhalten;
dieser Bericht ersetzt dessen noch offenen W/R-Status, nicht seine Prüfaussagen.

Der jetzt vollständig sichtbare innere pytest-Fehler entsteht beim Lesen der
Laufzeithistorie in `RuntimeHistory.start`/`runtime_copies.enabled`:
`sqlite3.OperationalError: database is locked`. Der Lauf hatte noch keinen
seiner vier Tests ausgeführt. Der zweite Fehler ist der Ablauf des bisherigen
60-Sekunden-Wächters in der Migration bei `space/request_receipt`; das Kind
lief noch. Das Log belegt außerdem Forks aus mehrthreadigen Workern. Es enthält
keinen Kind-Stack, der einen bestimmten Deadlock oder einen langsamen fsync
als alleinige Ursache beweisen würde.

Die Korrektur entfernt die beiden vermeidbaren Konfliktstellen:

- `start` und `observe` reservieren ihre kurze SQLite-Schreibtransaktion vor
  den Zustandsabfragen. Liveness-/Attempt-Prüfung und Speicherung bleiben so
  gegenüber konkurrierenden Schreibern zusammen. FULL-Sync, Timeout,
  Schemas, Originalhistorie, Fehlersignale und Auswahllogik bleiben erhalten;
  kein automatischer Retry und kein Ignorieren eines Datenbankfehlers.
  Drei native SQLite-Regressionsfälle prüfen den konkurrierenden Abschluss,
  Phasenpersistenz und die Freigabe nach einer abgelehnten doppelten Attempt.
- Die Fehlerprozesse starten einen frischen Interpreter über den bestehenden
  geschlossenen Prozesshelfer. Native Planbytes, ursprüngliche Quellen und
  Backupbeschreibungen gehen als eigene Testeingaben mit. Merge-Quellen und
  die Change-Prüfung werden nativ wieder gebunden; die vorhandenen synthetischen
  Testautoritäten werden ausdrücklich neu erzeugt. Laufende Python-Threads,
  SQLite-Verbindungen und Lockobjekte werden nicht per Fork mitgenommen.
  Die bisherigen In-Process-Aufrufer behalten ihren ursprünglichen Aufruf.
  SIGKILL und EIO/ENOSPC/EDQUOT bleiben echte Abbrüche am exakt benannten
  Checkpoint. Ein fehlender Checkpoint bleibt Exit 84/85 und scheitert.
  Der unbelegte einzelne 60-Sekunden-Timeout wird nicht mehr als Produktfehler
  gewertet; native Checkpoint-/Exit- und unveränderte Dateioracles entscheiden.

Alle Parametervarianten, Prefix-/Receipt-/Korruptions-/Git-Neustart-Assertions
und W/R-Matrixfälle bleiben erhalten. Neue Testnummern werden ausschließlich
hinten angehängt. Pflichtauswahl: kompletter bisheriger C-Plan, geänderte
Tests, direkte und indirekte Helferaufrufer sowie Journal-, Runner-,
Parallelitäts-, Evidence- und Hostregressionen. Fehlende oder ungültige
Messungen werden weiterhin nicht zu Erfolg umgedeutet.

`correction_of` bindet ausschließlich den öffentlichen Plan von Bundle 789
`ac6e648f883275f23ad103aa52b3ed7e08987b2bcd06ab040e891c363716b653`
und dessen vollständigen offenen Rest **20.h.C**, Rolle `implementation` und
ursprüngliche Nachricht. Erfolgreiche Commits werden nicht wiederholt.
Spezifikation, Entscheidungsvertrag und Produktvalidator bleiben unverändert;
es gibt keine normative Detaillücke und keinen Klärungspräfix.

Dev: **tests_run=0**; nur statische Kontrolle, reine Collection und native
Paket-/Fortsetzungsprüfung. Das C-Gate muss die Reparatur erst abnehmen.
Erst danach gelten 888/918 und Bundle 790 als abgeschlossen. Nächster Schritt
bleibt 20.i.W mit Referenzmessungen nach §14.1 (unter anderem keine
konkurrierende Benchmark-/SpecRoad-Last); normale Poolzeiten sind kein Ersatz.
Menschliche Reviews und noch fehlende Release-/Plattformnachweise bleiben offen.
