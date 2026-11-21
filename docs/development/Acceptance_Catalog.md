# Passives Abnahmeinventar

`tools/acceptance_catalog.py` verbindet eine bereits vorhandene native reine
Collection mit dem aktuellen Katalog. Optional liest es den unveränderten Bericht
eines ausdrücklich gewählten vollständigen nativen Testlaufs und dessen vier
Bindungsfelder (`run_id`, `tool_build_sha256`, `platform_sha256`,
`configuration_sha256`) aus einer JSON-Datei. Es startet selbst keine Tests.

```sh
python3 -I -B tools/acceptance_catalog.py \
  --collection build/current-collection.json \
  --evidence build/original-full-run.json --binding build/selected-run.json \
  --output build/fresh-acceptance-inventory.json
```

Ohne Evidence/Binding bleibt die Zuordnung lesbar, alle Ergebnisse bleiben offen.
Teilgruppen, fehlende Resultate, Skip und XFail ergeben keinen vollständigen
Nachweis. Alte Spezifikations-, Quell-, Katalog- oder Laufbindungen werden nicht
umetikettiert. Ein Bericht gehört nur zu seinem gewählten Lauf; das Werkzeug
authentifiziert keine fremden Autoren. Der Ausgabepfad muss neu und entweder
unter build oder außerhalb des Projekts liegen. Vorhandene Dateien bleiben
erhalten. Exit 0 bedeutet gültiges Inventar, 1 veraltete/ungültige Run-Evidence,
4 ungültige Eingaben/Dateigrenzen; keiner dieser Codes ist eine Releasefreigabe.

Die maschinenlesbare Ausgabe nennt alle aktuellen Requirements, Testkennungen,
Fixtures, Verifikationszuordnungen und unzugeordneten Tests, unveränderte
TD-001-Ausschlüsse sowie offene Punkte. Eine vollständige Zuordnung ist keine
Ausführung. Menschliche Abnahmen und die Original-Spezifikationsfreigabe werden
nicht automatisch erfüllt. Die üblichen Apply-only-Testregeln bleiben bestehen.
