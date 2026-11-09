# Korrektur 642 — vollständiger offener Control-Start-Fix

Bundle 641 wurde vor dem ersten Test während der Hostpool-Vorbereitung
abgebrochen; kein Commit entstand. Native Quelle:
`7653b8308b2bae6e5356a4f5a686cd6e774bbe6ae7af07cf8e5ade18c26e447d`.
Der anschließende native Umgebungscheck bestätigt Laptop und ThinkPad;
Hetzner verweigert die SSH-Anmeldung. Die Entsperrung des bestehenden
Schlüssels ist eine lokale Bedienaktion, keine Produkt-Payload.

Der vollständige noch offene Commit `CONTROL-DISPATCH-FIX`, Rolle `correction`,
wird mit allen bereits eingebrachten Dateien und unveränderter Pflichtauswahl
an die tatsächlichen Vorherbytes des Fehler-Results gebunden. Keine alte Stage
wird zurückgesetzt oder als bestanden ausgegeben. Produktcode und zehn neue
Regressionen bleiben bytegleich zu Bundle 641. Nur Bundlezählung und dieser
Nachweis ändern sich zusätzlich. Produktfortschritt bleibt 729/900, 18.a.W offen.

Erneute Übergabe erst nach erfolgreichem lokalen Hostcheck. Die vollständige
Control-Suite und die fällige N=3-Gruppe müssen weiterhin im Apply bestehen,
bevor der Commit und eine anschließende Control-Installation zulässig sind.
Keine Verhaltenstests in Dev, kein neuer fachlicher Scope, keine Klärung.
