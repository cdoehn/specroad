# PROPOSAL-DIALOG-738 — 18. November 2026

Autorität: delegiert gemäß SPECROAD-DECISION-1, Vertrag 4, explizit freigegebene
optionale Klärung. Das maßgebliche erfolgreiche Result mit SHA-256
`1f311874cefe4e8536dab6e0aadc14964fca8a17f590420535a923561cd14314`
bestätigt 18.o.C und 792/918. Kein offener Korrektur- oder Klärungsrest.

18.p verlangt den echten vollständigen öffentlichen Änderungsdialog. Die
vorhandene `ProposalEdit`-API liefert nur geprüfte Vorher-/Nachherwerte;
die native Publikation kennt bislang Create, Review und Apply. Eine weitere
direkte Testdateischreibung würde diesen fehlenden Integrationsweg verdecken.
Die fachlichen Edit-/Reviewregeln sind vorhanden, die geschlossene äußere
Writeroperation und ihre Bindung waren noch nicht festgelegt.

Alternativen: Generische Recordpatches würden die bestehende Kontrollgrenze
aufweichen. Ein zweiter Writer würde Sperren, Receipts und Fehlerzustände
duplizieren. Die gewählte konservative Ergänzung verwendet eine einzelne
geschlossene `proposal_change`-Operation und den vorhandenen nativen Writer.
Der vollständige gebundene Nachherrecord erhält bereits vergebene Change-IDs;
erneute Entropie bei der Add-Reduktion würde identische Gates nondeterministisch
machen. Ein reiner Nachherhash wäre ohne vollständige Originalbytes unzureichend.

Normativ ist Spezifikation 11.10.3, Fassung 0.2.94. Die Änderung ist additiv,
lokal rücknehmbar und bleibt in 18.p. Keine Datenlöschung, automatische
Umbindung, Scopeerweiterung, neue Reviewerautorität oder Änderung bestehender
CLI-/Receiptverträge. Alte Dokumente, Reviews und Belege bleiben bytegleich.
Produktfreigabe und reale menschliche Entscheidungen werden nicht ersetzt.
Alle Abnahmen benötigen ihre tatsächlichen Apply-Gates.

W: vollständiger nativer Dialog inklusive Überarbeitung, neuer Inhaltsbindung,
unwirksamer alter Reviews, erneuter echter synthetischer Freigabe und exaktem
Fachziel. R: Rejection, stale Basis/Preimages, Scope-/Kontrollangriffe,
Requestkonflikte/Replay, No-op/Dry-run, Provenienz-/Autoritätsverlust und reale
Unterbrechung ohne Datenverwerfung. C: gemeinsame reine Ablauf-/Ergebnishelfer
bündeln, Testoracles und Freigabebindungen unverändert lassen.

Die aktive Katalogbindung wird vollständig aktualisiert; diese Klärung
ändert keinen Produktzähler und behauptet keinen Test- oder Apply-Erfolg.
