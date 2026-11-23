# Bundle 801 — Zwei verbleibende Authoring-Fehler korrigieren

Datum: 23. November 2026. Maßgeblich ist das native Result
`specroad-apply_Result_083225_1123_e8e452.zip`, SHA-256
`203c461c2c90e14a8f649e7cadbf28a122b8ce98f31846c8081e86e95db4eb05`.
Bundle 800 endete mit **26.639 bestandenen und drei fehlgeschlagenen Tests**.
Kein Commit entstand; der vollständige offene Rest bleibt **21.c.W/R/C**.
Der erfolgreiche Klärungsstand und sämtliche bisherigen Reparaturen bleiben
erhalten. Diese Korrektur enthält keine neue normative Entscheidung.

1. Der Raw-CLI-Reihenfolgetest verwendete `/extensions/b` als bleibenden
   Schlüssel. SR-REQ-0018 verlangt einen Namespace. Die gültigen Testdaten
   verwenden nun `test.a` und `test.b`; die vollständige interleavte
   Set/Unset/Set-Reihenfolge und unveränderte Projektbytes bleiben geprüft.
   Die Namespace-Validierung wird nicht abgeschwächt.
2. Der AI-Umleitungstest verlangte ein Baseline-Proposal. Kapitel 10.8.1
   verbietet ausdrücklich Baseline-Ziele in eingebetteten Proposal-Plänen.
   Der bisherige Testfall samt ID bleibt erhalten und verlangt stattdessen
   die konkrete Ablehnung mit Code 3, unveränderte Originalbytes, fehlende
   Freigabe und dieselbe schreibfreie Ablehnung bei erneuter Anfrage.
   Die native öffentliche Route weist diese bekannte Scope-Verletzung bereits
   vor ID-Vergabe und Writer-Eintritt zurück. Damit wird sie auch nicht als
   unbekannter Schreibzustand mit vermeintlicher Recoverypflicht ausgegeben.
   Zulässige Proposal-Ziele und direkte autorisierte Baseline-Erzeugung behalten
   ihre bisherigen positiven Oracles.

R ergänzt vier Grenzen für menschlichen beziehungsweise AI-Akteur und Preview
beziehungsweise Veröffentlichung: weder Identitätsvergabe noch Writer dürfen
bei der verbotenen Baseline-Umleitung erreicht werden. Ein weiterer negativer
Raw-CLI-Fall sichert die unveränderte Ablehnung unqualifizierter Extension-Keys.
Alle alten Testnummern bleiben erhalten; fünf neue Nummern werden in R angehängt
und unverändert nach C übernommen. C behält seine reine Strukturbereinigung.
Die aktive Katalogzuordnung verweist auf die bestehenden Regeln 0018/0242/0406.

Jede Stage behält ihre eigene vollständige Pflichtauswahl plus fälliger
N=3-Gruppe und ihr Gate vor dem Commit. Die Stage-Zielzähler werden erst dann
wirksam. Gegenüber dem Vorbericht ist nun der fehlgeschlagene Apply von 800
belegt; die beiden beschriebenen Korrekturen sind noch keine erfolgreiche
Verhaltensabnahme.

**Messgrenze:** Der dritte Fehler betrifft den fehlenden echten Messnachweis
für den aktuellen Analyzer-Build. Dieser Test bleibt bytegleich, verpflichtend
und ohne Skip oder Ersatzbeleg. Es wurden weder Messungen noch Verhaltenstests
in Dev ausgeführt. Collection, Syntaxprüfung und native Paketvalidierung
ersetzen kein Apply-Ergebnis. Ob anschließend nur dieser Messfehler verbleibt,
muss das nächste native Result zeigen; R/C sind ebenfalls noch nicht abgenommen.
