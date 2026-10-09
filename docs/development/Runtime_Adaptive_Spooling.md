# Gemessene Arbeitsfenster für lebende Spool-Aufträge

`runtime.adaptive_spooling.advance_spool_sort(task, call, max_units=256)` verbindet
einen vorhandenen `DiagnosticSort` oder `PathSort` mit einer aktiven
`InvocationConsumption`. Der Aufrufer erstellt den Task mit ausdrücklich
geschützten Projektwurzeln und einem neuen externen Spoolverzeichnis, verwaltet
seine Lebensdauer und schließt jedes Messfenster mit `call.finish()` ab.

Der Treiber misst vor und nach jeder tatsächlich ausgeführten Sortiereinheit.
Sobald ein weiches Arbeitsziel überschritten ist, endet das Fenster nach
mindestens einer versuchten Einheit. Ein bereits vor der ersten Einheit
überschrittenes Ziel verweigert diesen Fortschrittsversuch nicht. Ohne beobachtete
Überschreitung läuft der Treiber bis zum vollständigen Abschluss oder bis zur
ausdrücklich gewählten positiven Zahl `max_units`. Unbekannte Messwerte werden
nicht als erschöpfte Kapazität interpretiert.

Bei weichem Druck begrenzt er die zukünftige kodierte Charge auf höchstens
64 KiB; bei einer beobachteten Überschreitung des verbuchten Speicherziels auf
einen Record. `DiagnosticSort.reduce_batch_bytes()` verkleinert das Ziel nur.
Bereits gepufferte Records und eine vorausgelesene Eingabe bleiben erhalten,
bis der bestehende Flush sie verarbeitet hat. Ein einzelner großer Record kann
den weichen Bytewert überschreiten. Die Änderung verspricht keine sofortige
Speicherfreigabe, RSS-Obergrenze oder garantierte Hostkapazität.

Der existierende Sortierer liest den Quelliterator einmal, schreibt externe
Läufe und führt sie paarweise zusammen. Ein offener Merge wird am lebenden
Cursor fortgesetzt. Ein kleines Fenster verwirft keine Pflichtdiagnosen,
vorbereiteten Pfade, Duplikate oder deren Reihenfolge. Vollständige Ausgaben
werden weiterhin ausschließlich über `task.result` und dessen Ausgabecursor
zugänglich. `PathSort` verarbeitet vorbereitete Pfade; er berechnet keine neue
Why-Suche.

Die abgelöste Projektion `spool-work-window-v1` nennt tatsächliche Fortschritte,
Cursor, gewählte Anpassung und nächste Operation. `state=active` erfordert
einen weiteren Aufruf desselben lebenden Tasks; `state=completed` bezeichnet den
fertigen Spool. Ein bereits fertiger gültiger Task behauptet keinen zusätzlichen
Fortschritt. Die Projektion ist ausdrücklich an den aktuellen Prozess gebunden,
mit `checkpoint=null` und `durable_checkpoint=false`. Sie ist kein CLI-Resultat
und vergibt keinen Exitcode 8. Persistente Work-Identität und Wiederaufnahme
folgen ab 6.i.

Fehler behalten in W den vorhandenen nativen Ausnahmevertrag. Der Task bewahrt
bereits geschriebene Spooldateien, schließt eigene Handles und zählt eine
fehlgeschlagene Einheit nicht als abgeschlossen. Es gibt keinen automatischen
Retry, keine Löschung von Projekt-/Recoverydaten und keinen Writer-Lock auf
einem geschützten Projekt. R ergänzt die ausführliche maschinenlesbare
Blockerprojektion. Die vorhandenen Schutz- und Eingabeprüfungen bleiben wirksam.

Die Tests verwenden echte externe Spooldateien und ausdrücklich markierte
Zählerfixtures für CPU-/Wall-Ziele. Sie vergleichen vollständige Ergebnisse und
Recordbytes, monotonen Fortschritt, Quellverbrauch, offene Mergecursor sowie
erhaltene Projekt-/Spooldateien bei injizierten Speicher-/Datenträgerfehlern.
Es wird keine allgemeine präemptive Millisekundengarantie behauptet: native
I/O-Aufrufe, Recordverarbeitung und notwendige Hashprüfungen bleiben innerhalb
ihrer bestehenden Einheit unteilbar. Andere Fachalgorithmen, persistente
Checkpoints und die vollständige Runtime-/Plattformabnahme bleiben offen.
