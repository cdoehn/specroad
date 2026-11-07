# Anhang D – gekoppelte Regressionen R-01 bis R-75

Unveränderte fachliche Zuordnung; [Zentraler Fortschritt](../SpecRoad_Implementierungsplan.md). Zeitbezogene Übergabeangaben ersetzen den dortigen aktuellen Stand nicht.

## Anhang D – gekoppelte Regressionen R-01 bis R-75

Die genaue Vorbedingung und das vollständige Oracle stehen im versionierten Anhang R der Spezifikation und werden nicht durch die Kurztitel ersetzt. Die Fachschritte nehmen die Fälle früh auf; `20.c` und `20.d` sichern ihre tatsächliche gemeinsame Abnahme. Bei R-63 wird die Sicherheitswirkung geprüft, nicht das visuelle Erscheinungsbild des escaped Texts.

| Fall | Gegenstand | Verantwortliche Meilensteine | Abschlussgate |
|---|---|---|---|
| `R-01` | Reguläre und migrierte Relation | 2, 16 | 20.c |
| `R-02` | Merge-Metadaten | 17 | 20.c |
| `R-03` | Unveränderte Übernahme | 17 | 20.c |
| `R-04` | Relationsreview | 7 | 20.c |
| `R-05` | Review-Auswahl | 7 | 20.c |
| `R-06` | Proposal-Einfügen | 18 | 20.c |
| `R-07` | Legacy-Unveränderbarkeit | 16 | 20.c |
| `R-08` | Historische Evidence | 12, 16 | 20.c |
| `R-09` | Proposal-Komplettlauf | 18 | 20.c |
| `R-10` | Befehlsklassen | 1, 5, 6 | 20.c |
| `R-11` | Überzogenes Arbeitsziel | 6 | 20.c |
| `R-12` | Sehr kleine Schritte | 6 | 20.c |
| `R-13` | Globaler Graph | 3, 6 | 20.c |
| `R-14` | Query und Diagnose-Spooling | 6, 8 | 20.c |
| `R-15` | Frische Sandbox | 6, 15 | 20.c |
| `R-16` | Veränderte Zielbasis | 5, 6 | 20.c |
| `R-17` | Beschädigter Checkpoint | 6 | 20.c |
| `R-18` | Retry nach Ausgabeabbruch | 5, 6 | 20.c |
| `R-19` | Echter Commitabbruch | 5 | 20.c |
| `R-20` | Prompt-/Actorgrenze | 6, 18 | 20.c |
| `R-21` | Kein Platz / harte Policy | 6 | 20.c |
| `R-22` | Unbekannte Quota | 6 | 20.c |
| `R-23` | Permanente Scope-Grenze | 3, 18 | 20.c |
| `R-24` | Proposal-Basiszulässigkeit | 18 | 20.c |
| `R-25` | Neuer Produktstand | 12 | 20.c |
| `R-26` | Retest desselben Stands | 12 | 20.c |
| `R-27` | Pflichtmenge und widersprechende Läufe | 12 | 20.c |
| `R-28` | Ungültige Ablösung | 12 | 20.c |
| `R-29` | Selfdescription-Projektion | 1, 7 | 20.c |
| `R-30` | Query-Wahrheitstabelle | 4, 8 | 20.c |
| `R-31` | Bewertung und Fortsetzung | 6, 12 | 20.c |
| `R-32` | Bewertung und Release-Baseline | 10, 12, 13 | 20.c |
| `R-33` | Reiner Abschluss | 5, 7 | 20.c |
| `R-34` | Fachinhalt und gemischter Lifecycle | 5, 7 | 20.c |
| `R-35` | Pflichtrelation ablehnen | 7 | 20.c |
| `R-36` | Erneut bestätigen | 7 | 20.c |
| `R-37` | Draft, optionale Relation und Authority | 7 | 20.c |
| `R-38` | Review-Transaktion und Retry | 5, 7 | 20.c |
| `R-39` | Review-Kontextstabilität | 7 | 20.c |
| `R-40` | Bundle-Arten | 15 | 20.c |
| `R-41` | Nichtkanonisches Teilbundle | 15 | 20.c |
| `R-42` | Manifest-Hashdomäne | 15 | 20.c |
| `R-43` | Manipulationsabgrenzung | 15 | 20.c |
| `R-44` | Vollständiger Baseline-Restore | 15 | 20.c |
| `R-45` | Unvollständige Restore-Quelle | 15 | 20.c |
| `R-46` | Geschützte Geschichte | 15 | 20.c |
| `R-47` | Restore-Atomarität | 5, 15 | 20.c |
| `R-48` | Force ohne Keyword | 2, 7, 11 | 20.d |
| `R-49` | Verbot | 2, 4 | 20.d |
| `R-50` | Tag-Policy | 2, 4 | 20.d |
| `R-51` | Mischung | 4, 11 | 20.d |
| `R-52` | Echte Erkennung | 19 | 20.d |
| `R-53` | Unsicherheit | 19 | 20.d |
| `R-54` | Grobe Sprache | 19 | 20.d |
| `R-55` | Verbotene Sprache | 19 | 20.d |
| `R-56` | Fremdanalyzer | 19 | 20.d |
| `R-57` | Alter Bericht | 19 | 20.d |
| `R-58` | Fehlende Library | 1, 19 | 20.d |
| `R-59` | Promptfortsetzung | 6, 19 | 20.d |
| `R-60` | Echter Hostblocker | 19 | 20.d |
| `R-61` | Migration | 16 | 20.d |
| `R-62` | SRX-Präzision | 4 | 20.d |
| `R-63` | Output-Sicherheit | 11, 19 | 20.d |
| `R-64` | Automatischer Work-Root | 6, 19 | 20.d |
| `R-65` | Expliziter Work-Root | 6, 19 | 20.d |
| `R-66` | Kleiner Auftrag | 6, 19 | 20.d |
| `R-67` | Automatische Analysekennung | 6, 19 | 20.d |
| `R-68` | Manuelle Analysekennung | 6, 19 | 20.d |
| `R-69` | Projektloser Request | 6, 19 | 20.d |
| `R-70` | Getrennte Namensräume | 6, 19 | 20.d |
| `R-71` | Work-Bindung | 6, 19 | 20.d |
| `R-72` | Expliziter Request und Override | 6, 19 | 20.d |
| `R-73` | Request-/Report-Paar | 6, 19 | 20.d |
| `R-74` | Echter Speicherblocker | 6, 19 | 20.d |
| `R-75` | Unterbrochener Requestaufbau | 6, 19 | 20.d |
