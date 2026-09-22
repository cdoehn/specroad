# SRX-Arithmetik (4.g)

Vier binäre Operatoren add/subtract/multiply/divide verwenden die explizite
Projektpolicy `project.srx_policy` aus dem übergebenen EvaluationContext.
Fehlende Policyfelder erhalten ausschließlich die festgelegten Defaults:
`numeric_policy_version=srx-decimal-v1`, `decimal_precision=34`; erlaubte Präzision
1–1000, kein Boolean. Die unabhängige immutable Policy ist am Kontext lesbar;
Originalkontext und Projektdateien werden nicht normalisiert oder geschrieben.
Die bereits vorhandene semantische Konfigurationsprojektion materialisiert diese
Defaults und bindet Änderungen an die Modellhashes. Keine fünfte JSON-Kontextwurzel.

Operanden werden über die bestehende JCS-Kodierung in exakte Dezimalwerte und
rationale Zwischenwerte überführt. Nicht über `Decimal(float)`, nicht über
Binärfloat-Arithmetik und keine Rundung auf die konfigurierten Stellen. Ein lokal
explizit initialisierter Decimal-Kontext wird nach jeder Operation wieder verlassen.

Endliche Quotienten haben nach Kürzung ausschließlich 2/5-Faktoren im Nenner.
Koeffizientennullen verbrauchen keine zusätzliche Präzision; Null zählt eine Ziffer.
Das Ergebnis muss anschließend denselben Dezimalwert nach JCS/Binary64-Roundtrip
besitzen. Grenzen sind fachlich und kein künstliches Arbeitsbudget.

Numerische Auswertungsfehler sind SRV197: division_by_zero, non_finite,
non_terminating, precision_exceeded, jcs_roundtrip_loss. Typfehler bleiben SRV110;
ungültige explizite Zahlenpolicy liefert Code 2. Ergebnis ist immer ein normaler
JSON Number, keine neue Decimal-/Fraction-Kontextwurzel und kein JSON-String.

Neue Tests und angrenzende SRX-/JCS-/Modellpolicy-Regressionsdateien laufen lokal
gezielt parallel. Die vollständige Suite gehört auf GitHub. Eine erfolgreiche
lokale Teilprüfung ist keine Vollabnahme und keine Releasefreigabe. Kein neuer
CLI-Fachbefehl, keine Host-/Datei-/Netzwerkbeschaffung und keine Transaktion.

R: Numeric errors from raw inputs and immutable JSON snapshots use the same disjoint SRV197 reasons. Structural JSON errors stay SRV110. Modified process and DefaultContext precision, rounding, flags and traps neither change results nor leak changes. Full rule aggregation and resource-resume policies remain later steps.

C: Reduced rational-to-decimal conversion (`_exact_decimal.py`), JSON/JCS transport (`numeric_boundary.py`), explicit policy (`numeric_policy.py`) and error data (`numeric_errors.py`) are separate. The arithmetic entrypoint only orchestrates these contracts. The arithmetic W/R behavior tests remain unchanged.
