# Bundle 690 — unabhängige Live-Teststeuerung

Technische Basis: Result-SHA-256
`98abddbf80f5c146122109e6c422ef1f4c9eb31b9884bfae78f935a2814df428`,
HEAD `6108db301ee1085a32410fb6f176dcf0fb07b06a`, sauberer Arbeitsbaum.
Bundle 689 hat CONFIG.W/R/C vollständig erfolgreich übernommen: 8213, 8327
und 8282 bestandene Tests in den drei getrennten Gates. Kein offener Rest.

Die bestätigte Spezifikation 2.4.3.7 und der START/CONFIG/LIVE/MOVE-Plan decken
LIVE vollständig ab; es gibt keinen neuen Klärungspräfix. Dieses Bundle
liefert die vollständige LIVE-Gruppe. MOVE bleibt eine separate geplante
Gruppe mit eigenem Versuchslifecycle und Abbruchbestätigung. Produktposition
18.s.W und die Produktzähler bleiben unverändert.

- LIVE.W: unabhängige CLI, persistente Vorgaben, Aufruf-Overrides, per Apply
  gebundene laufende Sollzahlen, dynamische Worker, Drain und vollständige
  Pause; gemeinsame atomare Hostslots, unveränderte Auswahl und Messungen,
  lesende Hostanzeige sowie lokale und Proxy-Integration.
- LIVE.R: Konkurrenz, ungültige/private Eingaben, Wiederanlauf, geänderte
  Umgebung, Worker-/Verbindungsverlust, mehrere Applies und strenge dynamische
  Nachweise ohne verlorene Tests oder Überbuchung.
- LIVE.C: getrennte Steuerdaten, Scheduler-/Transportadapter und lesendes
  Statusmodell; unveränderte Zuteilung, Fehler und Messung.

Dev führt ausschließlich Syntax, Collection und native Paket-/Snapshotprüfung
aus; das ist kein Verhaltenserfolg. Jede Stage bindet alle neuen/geänderten
Testdateien sowie die Host-, Scheduler-, Phasen-, Gate- und Monitorregressionen
als Pflichtauswahl. Apply führt jeweils genau die fällige gefilterte N=3-Gruppe
plus Pflichtauswahl aus und committet erst danach. Keine Betriebsdaten,
Dienststarts, Installation oder Budgetänderung in dieser Übergabe.
