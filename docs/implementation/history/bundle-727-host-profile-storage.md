# Bundle 727 — Hostprofilgrenze und vollständiger offener Rest

## Belegter Ausgang

Das native Fehler-Result von Bundle 726 bestätigt ausschließlich
`AUTHORING-PROPOSAL-726`. Der Klärungscommit bleibt erhalten und wird nicht
wiederholt. Produktfortschritt bleibt bis zur nächsten erfolgreichen Abnahme
780/918, letzter Produktcommit `18.x.C`. `18.l.W` wurde ausgebracht, aber
nicht committed: Der Runner lehnte vor dem Workerstart das Hostprofil mit
`Unsafe or oversized host input` ab. Das Profil enthielt 14.451 ausgewählte
Tests und 46 vorbereitete Worker und war 16.374.325 Byte groß. Dies ist kein
fehlgeschlagener Testkörper und kein bestandener W-Nachweis.

## Gezielte Korrektur

Die bisherige Projektion auf ausgewählte Tests und aktive Hosts bleibt
vollständig erhalten. Hier überschreitet bereits diese relevante Auswahl die
unveränderte Eingabegrenze von 16.000.000 Byte. Eine reine Entfernung von
JSON-Leerzeichen genügt nicht. Tests, Hostprognosen oder Worker wegzulassen
würde dagegen das gebundene Verhalten verändern.

Die interne Dateidarstellung verwendet deshalb nur für übergroße Profile
`storage_encoding=selected-key-alias-v1`: Bei identischem Node und stabiler
Test-ID ersetzt `null` den wiederholten Wert. Der Leser verwendet dasselbe
bereits gelesene Schlüsselobjekt; keine rekursiven Verweise oder Dateizugriffe.
Abweichende IDs und sämtliche Prognosen, Baselines, Worker-, Quellen- und
Umgebungsbindungen bleiben exakt erhalten. Kleine und historische Profile
behalten ihre bisherige Darstellung. Der geschlossene Profilvalidator prüft
das rekonstruierte Profil. Die gemeinsame Dateigrenze, Symlinkabwehr und
Doppelkeyprüfung sowie striktes UTF-8 und die Ablehnung nichtendlicher
JSON-Konstanten bleiben aktiv. Auch nach der Kompaktierung übergroße Profile
werden vor der Veröffentlichung der Laufdatei abgelehnt.

Pytest-Konfiguration, Nachprüfung des Runner-Ergebnisses und native
Commit-Gate-Nachprüfung verwenden denselben Leser. Dies ändert weder den
fachlichen Hostpoolvertrag noch einen Spec-, Rollen- oder Budgetvertrag.
Es ist keine neue Detailklärung und keine Installations-/Dienstaktion.

## Vollständige Fortsetzung und Abnahmen

Die offenen IDs und implementation-Rollen bleiben in dieser Reihenfolge:
`18.l.W`, `18.l.R`, `18.l.C`, `18.m.W`, `18.m.R`, `18.m.C`.
Alle ursprünglichen Fachumfänge, exakten Commitnachrichten, Pflichtdateien
und W/R/C-Abnahmen aus [Bundle 726](bundle-726-authoring-agents.md) bleiben
verbindlich. Der Reparaturstand gilt in allen sechs Zwischenständen; vor
jedem echten Commit steht weiterhin sein eigenes Apply-Gate. Kein Endstand
wird vorab ausgebracht. Produktzähler in den Zielständen gelten nur nach
deren eigenem erfolgreichem Gate.

Zusätzliche Pflichtregressionen prüfen einen tatsächlich über 16 MB großen
vollständig relevanten Run über die echte Profilvorbereitung, verlustfreie
IDs/Prognosen/Quellenbelege, alte Profile, unbekannte Kodierung, ungültige
Auswahl, doppelte IDs/JSON-Schlüssel, fremde Felder/Worker/Quellen sowie
Symlinks und unverändert übergroße Eingaben. Ein echter isolierter
execnet-Proxy-/Workerlauf und die vorhandene native Apply-Gate-Integration
prüfen das kompakte Profil einschließlich unveränderter Bindungskontrollen.
Die vorhandenen Host-, Auswahl-, Live-, MOVE-, SPECULATE- und
Commit-Gate-Regressionen gehören ebenfalls zur Pflichtauswahl.

In Dev wurden keine Testkörper oder Fixtures ausgeführt. Reine Collection,
Syntax-, statische und native Paketprüfung sind keine Verhaltensabnahme.
Die noch ausstehende Ausführung und Commitbestätigung liefert ausschließlich
Apply. Lokale Hostdaten und Betriebsnachweise gehören nicht zur Payload.
