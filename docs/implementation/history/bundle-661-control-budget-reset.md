# OFF-PLAN CONTROL-BUDGET-RESET-661

Der ausdrückliche Nutzerauftrag vom 10. November 2026 erlaubt Detailklärung 18.h,
ein erneuertes Budget von drei Plätzen und das Fortsetzen von Control.
Die bisherige CLI kann eine bereits übernommene Quelle nicht erneut freigeben
und besitzt keinen expliziten Budgetreset. [Entscheidung und Abnahmen](../decisions/control-budget-reset-661.md).

Dieses Bundle ergänzt `accept-current --clarification --reset-budget --reason ...`.
Der neue Beleg enthält den ursprünglichen Vertrag und die neue ausdrückliche
Freigabe. Vorherige Aufträge, Versuche und Budgets bleiben erhalten. Ein erfolgreicher,
sauberer, aktueller Apply mit vollständig belegten Stages und passender Fähigkeit
ist weiterhin Voraussetzung. Ohne neue ausdrückliche Bedienaktion gilt die bisherige
Budgetberechnung einschließlich einmaliger Belastung pro Mischübergabe.

- **W:** Bedienoption, versionierter Beleg, native Bindungsprüfung und positive Tests.
- **R:** Grenzen, Wiederholung, manipulierte Belege, konkurrierende Arbeit und CLI-Fehler.
- **C:** Reine Vertragsauswahl und typisierte Fähigkeitsprüfung in einem gemeinsamen Modul.

Jede Stage besitzt ihr eigenes N=3-plus-Pflichtauswahl-Gate vor dem Commit.
Dev führt ausschließlich AST-, Collection-, Katalog- und native Paketprüfungen aus.
Diese Datei behauptet keinen bereits absolvierten Testlauf; dessen Nachweis ist das
zugehörige native Apply-Result. Installation, Budgetfreigabe und Start sind getrennte
Bedienaktionen nach erfolgreichem Apply und werden nicht durch die Payload ausgeführt.

Der Produktplan bleibt bei 750 von 900 Positionen; 18.h.W ist weiterhin offen.
Dieses Bundle definiert keine neue normative Detailentscheidung für 18.h.
