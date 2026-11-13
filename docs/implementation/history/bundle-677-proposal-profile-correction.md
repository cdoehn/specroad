# Bundle 677 — Profilprüfung angewendeter Proposals korrigieren

13. November 2026. Quelle ist das native Fehler-Result 676 mit SHA-256
`d1fa13310b933e81fb2e981f99366beb959a8d3c8e5a6e7b0a255e6e958716b9`.
Der Lauf meldet 12879 bestandene und 14 fehlgeschlagene Tests bei 4275,35
Sekunden pytest-Laufzeit. 18.k.W wurde nicht committed; R/C wurden nicht
ausgebracht. HEAD bleibt der bereits erfolgreiche Klärungscommit
`8af77c07279e1784a11de2809834723296940dc7`. Die W-Checkliste des erhaltenen
Arbeitsstands beschreibt ein vorbereitetes Ziel, keinen bestätigten Fortschritt.

## Fehlerursache und begrenzte Korrektur

Die Schema- und Registrierungsfehler aus 675 sind überwunden. Die verbleibenden
14 Fehler erreichen die nächste gemeinsame Prüfschicht: observe_profile_fields
weist den bereits spezifizierten Proposal-Reifezustand applied als
profile_invalid_maturity ab. Das unterbricht die native Zielvorbereitung vor
Publikation und verdeckt in einem Negativfall den späteren Autoritätsfehler.
Öffentliche Beispiele und Schema-Integrationen erreichen dieselbe Schranke.

Das vorhandene gemeinsame Artefaktvokabular wird typspezifisch wiederverwendet:
applied gehört ausschließlich zu gespeicherten Proposals. Feldprüfungen
akzeptieren diesen Typ/Zustand und führen sämtliche Profilregeln weiter aus.
Die Komposition materialisiert Regeln für alle Reifezustände einschließlich
applied, damit erforderliche und verbotene Felder sowie erlaubte Werte nicht
versehentlich entfallen. Schnittmengen und Konflikte bleiben verbindlich.

Explizite Feld-, Lint- und Mindestrelationsselektoren dürfen applied nur mit
Proposal im Typfilter verwenden. Gemischte Typfilter erzeugen Feldregeln für
applied nur für Proposal. Relationsreview-Selektoren und die lesende Query-
Filterung kennen ebenfalls den vorhandenen Zustand; Review-Schweregrade und
unveränderliche Fehlergrenzen bleiben erhalten. Der allgemeine Lifecycle und
die generischen Transition-Schemata behalten ihr bisheriges Vokabular.

Die bereits korrigierten passiven Recordverträge bleiben erhalten: neue
applied/applied-Proposals und ältere applied/approved-Originale sind lesbar.
Lesende Prüfungen erteilen keine Freigabe oder Schreibbefugnis. Native
Proposal-Kontrollhistorie, aktuelle menschliche Reviews, Quorum, Hostautorität,
Stale-Bindungen, Receipt und gemeinsamer atomarer Write bleiben unverändert.
Es gibt keine neue normative Detailentscheidung, Spezifikationsänderung oder
Budgetänderung. Die Host-Laufprofilkorrektur aus 675 bleibt ebenfalls enthalten.

## Regressionen und vollständiger offener Rest

Acht neue Regressionen prüfen direkte und komponierte Feldregeln, explizite
und gemischte Typfilter, Wildcard-Schnittmengen und Konflikte, native Mindest-
relations- und Lintbeobachter, Relationsreview-Schweregrade, Abweisung anderer
Artefakttypen und unbekannter Zustände, lesende Query-Auswahl und byteerhaltene
Originale sowie gesperrte generische Transitionen. Die Fixtures verwenden
native passive Recordvalidierung und synthetische Profilressourcen; sie
simulieren keine menschliche Freigabe und keinen Publikationsnachweis.

Alle bisherigen Proposal-Apply-, Schema-, Herkunfts-, Quorum-, Writer-,
Receipt-, Crash-/Recovery- und Completiontests bleiben erhalten. Jede Stage
enthält zusätzlich vollständige betroffene Profil-, Relations-, Query- und
Validierungsregressionen sowie alle ursprünglichen Pflichtdateien. Es werden
keine Tests zur Umgehung der Fehler entfernt, gefiltert oder abgeschwächt.
Alle bereits vergebenen Testnummern bleiben erhalten. Neue W-Identitäten
werden angehängt; anschließend folgen die noch nicht ausgebrachten R-Tests.

Die vollständige Folge 18.k.W, 18.k.R, 18.k.C behält IDs, Commitnachrichten,
Rollen implementation und fachliche Abnahmen. W übernimmt alle erhaltenen
uncommitteten Dateien. Jede Stage wird erst nach ihrem eigenen erfolgreichen
N=3-plus-Pflichtauswahl-Gate committed; erst danach wird die nächste Stage
ausgebracht. Kein Endstand vorab, keine Wiederholung erfolgreicher Commits.
Historische Nachweise bleiben bytegleich. Fortschrittszähler gelten erst nach
dem jeweiligen erfolgreichen Apply-Gate; nach 18.k.C bleibt 18.l.W offen.

Dev prüft ausschließlich Syntax, reine Collection, Katalog-/Stagebindungen
und das native Paket. Verhaltenstests, Fixtures und Test-Unterprozesse werden
nicht in Dev ausgeführt. Die Korrektur ist vor der Apply-Ausführung noch nicht
fachlich abgenommen.
