# IMPLEMENTATION-PLANS-791 — vollständiges Planfeature und technischer Rest

22. November 2026. **Ausdrücklicher Nutzerauftrag**, keine eigenmächtige
optionale Detailklärung: Spezifikation und Restplan aus den konsolidierten
E-Mail-/Gesprächsentscheidungen in Dev1 überarbeiten, als ein Bundle an Apply1
übergeben, Control ausgeschaltet lassen und nach der Übergabe den Turn beenden.

## Maßgebliche Entscheidungen

Ein vollständiger Implementierungsplan pro Markdown-Datei ist die einzige
Planquelle. Stabile ID und sichtbare Kennung sind getrennt; jeder Eintrag hat
Titel, Commit-Titel gehen in die bereitgestellte Commitmessage ein. Checkboxen
werden von der Umsetzung/manueller Bearbeitung gepflegt; der ältere Git-Log-
Statusabgleich ist ausdrücklich gestrichen. Beliebige Requirement-Teilmengen,
mehrere Pläne, explizite Listen planübergreifender Voraussetzungen, optionale
Task-Viele-zu-viele-Bezüge und durchgehende Traceability gehören zum Umfang.

Spec-only, Plan-only und gemeinsame Proposals sind erlaubt. Nur eindeutige
Mindestkonsistenz wird als solche geprüft. Planimpact einschließlich erledigter
Einträge erscheint in Vorschau und tatsächlichem Ergebnis, Text und JSON.
Semantischer Merge und Abdeckungsdetails wurden zur eigenen Empfehlung
freigegeben. Die zwölf Merge-Regeln und die getrennten Scope-/Teil-/Voll-
Abdeckungsregeln stehen vollständig in Anhang X der Spezifikation.

Der endgültige Analyzerentscheid beschränkt diese Erweiterung ausdrücklich
auf bestehende Spracherkennung. Die zwischenzeitlich erwogene Grammatik-/
Satzvollständigkeitsprüfung ist verworfen. Keine neue Sprachbibliothek oder
LLM-Ausführung. Jede bestehende/neue CLI-Funktion erhält Text/JSON aus denselben
Ergebnisdaten. Allgemeines explizites Force übersteuert SpecRoad-Produktgates,
erfindet aber weder Ausführung noch Freigaben/Evidence oder fehlende Eingaben.
Es erteilt keine Übersteuerungsbefugnis für die Entwicklungs-/Apply-Steuerung.

## Ausgearbeitete technische Verträge

Anhang X schließt die notwendige Grammatik-/Speicherentscheidung: normatives
Markdown mit passiven JSON-Metadaten, verlustarme Textspannen, zwei neue
Artefakttypen, gemeinsame Graphprojektion, kein zweites JSON-Planmodell.
Projekt-/Planschema 0.3.0, plan-markdown-v1, Change-Plan 1.3.0 und Envelope
2.1.0 werden getrennt versioniert. Alte Reader und Originalbelege bleiben
erhalten. Hierarchien verwenden Überschriften und strukturierte verschachtelte
Listen; ID/Display/Checkbox stehen eindeutig an ihrer einzigen Quelle.
Die Alternative eines separaten Plan-JSON als Autorität widerspräche der
expliziten Editieranforderung. Eine ungeprüfte Textdiff-/Checkbox-OR-Mergeheuristik
widerspräche den angenommenen Mergeempfehlungen. Beide werden verworfen.

## Bestätigte Basis und vollständiger Rest

Das erfolgreiche native Result
`0eeb7eb12c5dae70a26bcdb3b4f909519b909edbff66cd5a7132d957ed76bfa0`
bestätigt Bundle 790, 20.h.C, Commit
`098d2f3170ebd3a360145c00695673bf5e5eb85d`, 13.121 bestandene Tests und
sauberen Abschluss. **888 der bisherigen 918 Produktpositionen** sind damit
bestätigt. Kein alter erfolgreicher Commit wird wiederholt oder zurückgesetzt.

M21 ergänzt 26 vollständige W/R/C-Gruppen, 78 neue offene Positionen. Gesamt:
996 Positionen, 888 abgeschlossen, **108 offen**. Davon 87 technische Commits
vor den verbleibenden 21 Commits des menschlich abhängigen Abschlussblocks.
Das zählt Planpositionen, keine Arbeitszeit und keine erfüllten Requirements.
Die tatsächliche Folgereihenfolge steht nur im zentralen Fortschrittsblock.

Die 30 vorher offenen M19/M20-Commits bleiben vollständig erhalten. 20.i/j/m
folgen nach der neuen technischen Implementierung; dadurch messen und verpacken
sie das erweiterte Produkt. 19.t/y und 20.b/d/k/l/n bleiben abschließend,
einschließlich echter Korpus-/Herkunfts-/Nutzungsreviews, abhängiger realer
Adapterabnahme, Bedienungsdurchsicht und ausdrücklicher Benutzungsfreigabe.
Die 226 vorhandenen Korpusreviewpunkte bleiben unverändert und offen soweit
kein tatsächlicher Beitrag vorliegt. Neue technische Reviewpakete entstehen
in 21.z; menschliche Zustimmung wird dort nicht vorausgesetzt oder erzeugt.

## Alte offene Nachweise und Automatisierung

Die [vollständige Restzuordnung](../matrices/Uebergabe.md#restinventar-791)
erfasst alle 742 alten Requirementfälle einzeln mit ihrem gebundenen
Katalogstatus und verantwortlichem Restschritt. Die Basis enthält vier
implemented-, 680 partial- und 58 open-Einträge; ein partial ist nicht
automatisch eine ungeschriebene Funktion, aber auch keine Gesamtabnahme.
Historische prepared-/Phase-offen-Texte werden nur anhand tatsächlicher
Originalresults in 21.v bereinigt. Echte fehlende Funktion/Verhaltensabnahme
gehört in den zugeordneten Fachschritt, kein stilles Streichen und kein
Zusammenzählen alter Teiltests zu einem aktuellen Full-Pass.

Die zurückgestellte Vorher-/Nachherauswertung der Testoptimierungen bleibt
in 21.y sichtbar; Messplätze kommen früh, reale Schlussmessungen in 20.i/j.
Bestehende Auditentscheidungen bleiben geschlossen, soweit belegt; neue
Feature-Nachweise sind eigene offene Arbeit, keine erfundene Wiederöffnung.

Jeder neue Schritt hat vollständigen Scope, Voraussetzungen, exakte W/R/C-
Messages und beobachtbare Abnahmen. Die fachliche Umsetzung braucht keine
wiederholte Grundsatzentscheidung zu bereits freigegebenen Details.
Echte externe Runtime-/Messplatzfehler bleiben konkrete Blocker. Control kann
später auf ausdrücklichen Startauftrag der Folge folgen; dieses Bundle
installiert, startet oder resumed keinen Dienst und setzt kein Budget zurück.

## Dieser Dokumentcommit

`IMPLEMENTATION-PLANS-791 docs(spec): Implementierungsplaene und automatisierbaren Restplan festlegen`

Ein vollständiger OFF-PLAN-Commit, Rolle implementation, handoff_kind
patch_ready. Spezifikation, detaillierter Plan, Matrizen und aktive
Katalogbindungen werden gemeinsam geändert; Produktcode, Testcode, alte
Testnummern, ursprüngliche Messbelege und historische Reviewbeiträge bleiben
unverändert. Keine Alibi-W/R/C-Aufteilung dieses reinen Planungsauftrags.
Dev prüft nur statisch, per Collection und nativem Paketvalidator. Das
Apply-Gate ist notwendig, aber kein Nachweis der noch nicht implementierten
48 neuen Anforderungen. Die bisherige ausdrückliche Nichtbenutzung bis zur
gesonderten Nutzerfreigabe bleibt bestehen.
