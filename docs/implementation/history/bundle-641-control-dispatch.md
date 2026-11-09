# Korrekturbundle 641 — Control-Start nach langer Nachweisprüfung

Quelle: erfolgreiches sauberes Result
`72793da1df2bcd3478ab55b1a6de16c2dd1722d122930b24fcce200ab8a5d9c2`,
HEAD `fafd596cf78b0a83427faa0cfe5a7d7f02a3ce2d`. Manueller Reparaturauftrag
vom 9. November 2026. Ein vollständiger OFF-PLAN-Korrekturcommit
`CONTROL-DISPATCH-FIX`; kein neuer Produktscope und keine Detailklärung.
Produktfortschritt bleibt 729/900, nächste Position 18.a.W.

Der vorhandene Transport prüfte den Chat vor längeren Apply-Nachweisen.
Eine zwischenzeitliche Nutzeraktivität konnte deshalb erst beim eigentlichen
Start auffallen; der dauerhafte Auftragsclaim war dann bereits gesetzt.
Die konkrete Serverfehlermeldung des beobachteten Abbruchs fehlt im alten
Protokoll. Die veraltete Vorprüfung ist unabhängig davon im Code belegt.

Die Korrektur prüft Identität, Verzeichnis und Aktivität erneut nach den
vollständigen Nachweisen und vor dem Claim. Nur nachweislich aktive Chats
vor einem Claim führen zum Warten im bestehenden Control-Eventloop. Unbekannte
Zustände und Fehler nach dem Claim bleiben gesperrt; kein blindes Wiederholen,
kein Überschreiben alter Versuche und keine Budgetänderung. Die Prüfung liegt
außerhalb des Pause-Mutex, danach werden Gate und Originalauftrag erneut geprüft.
Die doppelte Vollprüfung desselben Apply-Belegs entfällt; die abschließende
Prüfung und die unveränderten Original-/Konfigurationsbindungen bleiben.
Bei RPC-Ablehnung werden Methode und numerischer Fehlercode aufgezeichnet,
keine Serverprosa, Prompts oder Zugangsdaten.

Pflichtauswahl: vollständige Control-Regressionssuite einschließlich echter
isolierter Unix-Socket-/Exec-Startgrenzen, später Chatbelegung, unverändertem
Versuch, einmaliger Ausgabe nach Idle, unbekannter Aktivität, falschem cwd,
geändertem Apply-Nachweis, Pause und Erhaltung eines bereits gesetzten Claims.
Hinzu kommt die fällige gefilterte N=3-Gruppe. Dev führt keine Verhaltenstests aus.
Collection, Syntax und Paketprüfung sind keine Apply-Abnahme. Erst das native
Result belegt Tests und Commit; lokale Installation und Wiederaufnahme sind
anschließende gesonderte Bedienaktionen aus dem aktuellen Nutzerauftrag.
