# Bundle 649 — isolierte Apply- und Control-Testfixtures

9. November 2026. Maßgebliches Fehler-Result:
`2bfc9597a29b01ce0ab037f4349a6adbd3de43775d034dc1a132a8a3aaa4ee37`,
Base-Commit `b292024d2d4f375e577dbf3ab7d6a7b853c08914`.
Bundle 648 beendete die Auswahl von 8.998 Testidentitäten mit sieben
fehlgeschlagenen Identitäten. Es entstand kein Commit. Der erfolgreiche
18.b.W-Commit bleibt erhalten; der bestätigte Produktfortschritt bleibt
733/900. Die uncommittierten Planwerte im Fehler-Snapshot sind vorbereitete
Zielwerte und kein bestandener R-Nachweis.

Die Korrektur erhält genau die offenen IDs 18.b.R und 18.b.C mit Rolle
`implementation`, ihre Reihenfolge, ihren vollständigen Umfang und sämtliche
bisherigen Pflichtdateien. Keine neue Klärung oder Budgetänderung.

## Befund und Korrektur

Drei Fälle in `test_apply_commit_plan_right.py` setzten den verschachtelten
Kontext auf null und ließen damit den CLI-Runner die echte lokale
Hostkonfiguration verwenden. Ohne Hostpolicy lehnten zwei Fälle den Pool ab;
mit Hostpolicy scheiterte ein zusätzlicher Pool an bereits belegten Slots.
Die synthetischen Testprojekte wählen jetzt ausdrücklich `--local` und einen
verschachtelten Kontext. Eine absichtlich ungültige separate Hostdatei stellt
sicher, dass dieser lokale Test keine Hostkonfiguration benötigt. Bei aktiver
Ressourcenpolicy werden ein Worker, Nice und der gebundene Ressourcenbeleg
geprüft; die historische Fixture ohne Ressourcenpolicy bleibt erhalten.
Alle vier Parameterfälle, die exakte Pflichtunion, langsame Pflichttests,
15 dauerhafte Messphasen, absichtlich rotes Gate und unveränderter HEAD bleiben.
Poolbeleg und Pooldatei dürfen im lokalen Gate nicht entstehen.

Vier Control-Fälle lasen `request.json` des unabhängigen Test-Daemons mit dem
privaten Betriebsdateileser. Der Daemon schreibt einen gewöhnlichen JSON-
Mitschnitt, dessen Modus von der Host-umask abhängt. Wie die bestehenden
Transporttests liest die neue Vollzugriffsprüfung diesen Mitschnitt jetzt
direkt als JSON. Thread-, cwd-, Approval- und Sandbox-Prüfungen bleiben erhalten;
echte Control-Belege werden weiterhin mit dem privaten Leser geprüft.

## Erhaltener Rest und Abnahme

Die Korrekturen aus [Bundle 647](bundle-647-correction-and-access.md) und
[Bundle 648](bundle-648-host-history-writer.md) bleiben vollständig enthalten.
Die gesamte bisherige Pflichtauswahl einschließlich der Control-Suite und der
echten Remote-/execnet-/xdist-Regressionen gilt für beide Stages weiter.
Es gibt keine Änderung am produktiven Hostpool, an Zugriffsschutz, Testnummern,
Messhistorie oder Auswahlpolicy. Zusätzliche Testidentitäten sind nicht nötig.

Dieser Bericht gehört zum vorbereiteten C-Zustand. Er folgt erst auf den
erfolgreichen R-Commit und enthält ausschließlich die schon angekündigte
Proposal-Scope- und Codex-CLI-Policy-Bereinigung bei erhaltenen Korrekturen.

Dev führt nur Syntax-, Collection-, Übergangs- und native Paketprüfungen aus.
Jede Stage benötigt ihr eigenes Apply-Gate vor dem Commit. Vollzugriff und
Automatik bleiben gesonderte Betriebsaktionen nach erfolgreichem Apply und
geprüftem Deploy. 18.c und spätere Produktpositionen bleiben offen.
