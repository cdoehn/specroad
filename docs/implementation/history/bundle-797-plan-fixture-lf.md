# Bundle 797 — Physische LF-Zeilen in Plan-Testdaten

23. November 2026. Das native Result mit SHA-256
`cfc4420e1dcf9eba1422020eed4eec53f960d0ea15d340f71de9936022600a60`
bestätigt **21.b.W** mit **9.335 bestandenen Tests** und Commit
`7499d6bb4375e0ea5700869cb2c7f326533ad5bd`. Bestätigt sind **892/996**
Positionen. Das anschließende R-Gate scheiterte mit **1 fehlgeschlagenen,
9.441 bestandenen Tests**. Der vollständige offene Rest ist **21.b.R/C**;
W wird nicht wiederholt. Diese Stage **21.b.R** wird erst nach ihrem
eigenen erfolgreichen Apply-Gate und Commit abgeschlossen.

Der Fehler liegt im unabhängigen Testdatenhelfer `plan_sources.block`:
`str.splitlines()` zerlegte den Beschreibungstext auch an U+2028/U+2029
und fügte dort Einrückungsleerzeichen ein. Die Testeingabe enthielt somit
andere Bytes als das beabsichtigte Oracle. Der Produktparser erhält diese
zusätzlichen Leerzeichen korrekt; physische Zeilen sind nach X.3/X.4 durch
LF getrennt. Der Helfer rückt deshalb jetzt nur physische LF-Zeilen ein.
Leer-/Whitespacezeilen, fehlendes oder vorhandenes Schluss-LF und die
Unicode-Zeichen bleiben unverändert. Keine Produktprüfung wird abgeschwächt.

Der vorhandene Test prüft zusätzlich seine vollständigen erwarteten
Beschreibungsvorherbytes als unabhängiges Literal. Seine bisherigen
Assertions zur Projektion und zum exakten Editergebnis bleiben unverändert,
ebenso alle Testidentitäten und Nummern. Beide direkten Helferkonsumenten
`test_plan_markdown.py` und `test_plan_markdown_right.py` sowie die gesamte
bisherige Pflichtauswahl gehören zu jedem Gate des offenen R/C-Rests.
Der fehlerhafte Fall bleibt ausdrücklich verpflichtend.

Die ursprünglichen vollständigen R/C-Zielstände einschließlich der
[Metadatenkorrektur 796](bundle-796-parser-metadata-correction.md) bleiben
erhalten. Der erste Commitumfang enthält auch die bereits ausgebrachten,
noch uncommitteten R-Dateien; seine Vorherbytes stammen vollständig aus
diesem Fehler-Result. C behält identische W/R-Testquellen und dieselben
Fachdefinitionen wie R; es wird nur die bereits geplante Struktur bereinigt.

Dev-Verhaltenstests: **0**. Syntax, reine Collection, native Rekonstruktion,
Paket- und passive Control-Prüfung ersetzen keine Verhaltensabnahme.
Keine normative Lücke, kein Klärungscommit, keine neue Produktfreigabe.
Nach erfolgreichem C wären **894/996** Positionen abgeschlossen; danach
folgt der vollständige Authoringvertrag **21.c.W/R/C**. Die späteren
Integrationen, Plattformnachweise und menschlichen Endabnahmen bleiben offen.
