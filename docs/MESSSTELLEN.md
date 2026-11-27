# Messstellen V0.8.0

Messstellen sind lokale Metadaten unter `config/sites.json`, keine Geräteeinstellungen. Anlage/Änderung/Zuordnung senden keine BLE-Befehle und ändern keine Geräteuhr. Es werden keine Namen, Räume oder echten Zuordnungen ohne ausdrückliche Eingabe angelegt.

## Bedeutung und Historie

Eine Messstelle besitzt eine stabile `site-<UUID>`-ID, Name, Raum, Beschreibung und validierte Auswertekriterien. Kriterien entsprechen den manuellen Feuchteindikatoren (Luft-/Oberflächenschwelle, Hysterese, Mindestdauer, optionale Oberfläche). Sie lassen sich bewusst in die manuelle Auswertung übernehmen; dadurch werden weder Datenquelle/Zeitraum automatisch passend gewählt noch automatische Warnungen aktiviert.

Je Logger und Messstelle ist höchstens eine aktive Zuordnung erlaubt. Zuordnungen haben Host-UTC-Beginn einschließlich, Ende ausschließlich und einen vollständigen Snapshot damaliger Angaben/Kriterien. Loggerwechsel oder Standortwechsel schließen betroffene alte Intervalle und erzeugen ein neues. Änderungen an einer aktiv zugeordneten Messstelle schließen ebenfalls das frühere Metadatenintervall und beginnen eines mit den neuen Angaben; alte Namen/Kriterien bleiben erhalten. Es gibt keine Lösch- oder Rückdatierungsfunktion.

Neue Host-Empfänge werden anhand ihres Empfangszeitpunkts unter der passenden stabilen Messstellen-ID gespeichert. Bereits vorhandene CSV-Zeilen werden nicht neu geschrieben; unzugeordnete Zeilen behalten ihre bisherige Loggerkennung. Dateipfade bleiben loggerbezogen. Eine ungeprüfte Gerätehistorie wird nicht aus ihrem Gerätekalender einer Hostzeit-Zuordnung zugeordnet. Simulation wird nicht an reale Loggerzuordnungen gebunden.

## Grenzen dieser Ausbaustufe

Diagramme, Statistik und Auswahl-Export wählen weiterhin einen Logger und Zeitraum. Ein solcher Bereich kann mehrere Messstellen umfassen; er wird nicht pauschal mit dem aktuellen Messstellennamen beschriftet. Messstellenfilter und historische Gerätezuordnung benötigen einen weiteren Schritt. Der bisherige Programmeinstellungs-Export umfasst die neue Verwaltung noch nicht; die gemeinsame Save-/Load-Einbindung folgt innerhalb V0.8.

## Integrität

Änderungen brauchen die aktuelle Konfigurationsrevision. Speichern erfolgt nach vollständiger Validierung per atomarem JSON-Ersatz, Datei privat (600). Bei Schreibfehlern wird auch die Arbeitsspeicherkopie nicht geändert. Ungültige bestehende Konfiguration wird nicht automatisch geleert oder repariert. Zeitstempel kommen ausschließlich von der Hostuhr; nicht vorwärts fortgeschrittene Zeit blockiert Zuordnungsänderungen. Die Historie wird nicht zur aktuellen Gerätezeit erklärt.

Gleichzeitige API-Aufträge werden innerhalb des laufenden Prozesses serialisiert; veraltete Revisionen werden abgewiesen. Bis 200 Messstellen und 10.000 Zuordnungsintervalle; Erreichen der Grenze verwirft keine ältere Historie. Die Oberfläche erhält ungespeicherte Entwürfe bei ersetzt vorliegendem Stand und verlangt vor dem Speichern dessen ausdrückliche Übernahme. Zuordnungswechsel zeigen betroffene aktuelle Belegungen vor dem Klick an.

Messstellenaktionen werden im bestehenden privaten Betriebsereignisprotokoll dokumentiert. Kein zusätzlicher Hintergrunddienst, keine Datenbank und kein gesondertes Backup-System.
