# Regeln für SpecRoad-Projektdokumente

Lies zuerst [DEVELOPMENT.md](../DEVELOPMENT.md) und die Anweisungen am jeweiligen
Arbeitsort. Diese Datei enthält portable Dokumentationsregeln, keine lokalen
Betriebskonfigurationen und keine Dienst-/Teststartfreigabe.

- Die normative Spezifikation beschreibt das Produkt; der Implementierungsplan
  konkretisiert Scope und Abnahmen; Ausführungsberichte belegen einen gebundenen
  damaligen Zustand. Diese Aussagen nicht miteinander verwechseln.
- Eine fachliche Regel hat eine maßgebliche Stelle. Andere Dokumente verweisen
  darauf. Wiederkehrende Prozessregeln nicht in jeden Planschritt kopieren.
- Reine Umstrukturierung erhält Anforderungen, Abnahmen, Kennungen, Entscheidungen
  und Belege. Geänderte relative Links und bestehende Sprungmarken berücksichtigen.
- Planstatus nur anhand tatsächlicher Apply-Ergebnisse fortschreiben. Vorbereitete
  Zielzustände, Collection und Paketvalidierung sind keine bestandenen Tests.
- Historische Logs, Konfigurationen, Zugangsdaten und Session-/Threadkennungen
  nicht als neue Dokumentation kopieren. Benötigte Result-Nachweise mit ihren
  vollständigen Hashes referenzieren, ohne lokale Geheimnisse aufzunehmen.
- Keine Dokumentations-, Markdown-, Linkchecker- oder Darstellungstests in die
  Produktsuite aufnehmen. Die einmalige statische Prüfung einer beauftragten
  Verschiebung ist eine Vorbereitungsprüfung, kein neuer Produkt-Testvertrag.

Für den Plan gilt zusätzlich [implementation/AGENTS.md](implementation/AGENTS.md).
