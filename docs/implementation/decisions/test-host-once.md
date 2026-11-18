# TEST-HOST-ONCE — ausdrücklicher Nutzerauftrag vom 18. November 2026

Normative Regel: [Spezifikation 2.4.3.8](../../specification/SpecRoad_Spezifikation.md#2438-spekulative-testkopien--speculate-697).
Derselbe Test darf pro Host höchstens einmal gleichzeitig ausgeführt werden.
Die frühere Ausnahme nach Belegung aller Hosts entfällt. Eine volle Hostbelegung
ist kein Anlass für zusätzliche Kopien. Andere Tests dürfen freie Slots nutzen.
Der Geltungsbereich ist der gebundene Testlauf; getrennte Läufe und Linien
behalten ihre eigenständigen Identitäten, ihre gemeinsamen Host-Slotgrenzen
und ihre eigenen Messhistorien. Hostbudgets werden nicht geändert.

Diese ausdrücklich beauftragte OFF-PLAN-Folge hat eigene Commits und wird
nicht mit der unabhängigen Dialogoptimierung vermischt. Produktfortschritt,
N=3, Pflichtauswahl, Gewinner- und Fehlerspeicherung bleiben erhalten.

- `TEST-HOST-ONCE.W`: Auswahl ohne Mehrfachkopien je Host, reservierte Starts
  einbeziehen, Startfreigabe erneut prüfen und echte Überschneidungen im
  unabhängigen Beleg abweisen. Abnahme: fünf Hosts mit vielen freien Slots,
  gestartete/finishing Versuche, vorzeitige Reservierung und konkurrierende Freigabe.
- `TEST-HOST-ONCE.R`: ablaufende Reservierungen, Move-Reservierungen, verschiedene
  Testidentitäten und Hostaktivierung; echter lokaler/Proxy-Pool mit freien
  Zusatzslots; manipulierte native Zeitintervalle über unterschiedliche Slots.
- `TEST-HOST-ONCE.C`: reine Hostbelegungs- und Intervallprüfung vom
  Prozesscontroller trennen; R-Testbytes und Pflichtauswahl unverändert.

Jede Stage benötigt ihr eigenes erfolgreiches Apply-Gate vor dem Commit.
Dies ist die Abnahmebeschreibung, kein bereits bestandener Testnachweis.

Gebundene Übernahme: [Bundle 740](../history/bundle-740-host-once-dialog-performance.md).
