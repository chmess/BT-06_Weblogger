# Änderungen

## 0.3.0-dev · 2026-11-21

- Vollständige Historien als unveränderliche Monats-CSV-Stände; Veröffentlichung erst nach CSV-/Manifest-fsync und atomarer Umbenennung. Inhaltskennung verhindert identische Kopien auch nach Neustart. Veränderte/überlappende Stände bleiben ausdrücklich getrennt; keine geratenen stabilen Geräteindizes.
- Manuelles lesendes GATT-Sync mit Fortschritt, begrenztem Empfang, gemeinsamer Adaptersperre, Abbruch beim Beenden und Wiederaufnahme des vorher aktivierten Hostempfangs. Keine automatische Kopplung oder Loggeränderung.
- Datenquelle Loggerhistorie mit Gerätezeitachse, freier Kalenderauswahl, Historienstandwahl und Original-CSV. UTC-Zeitstempel bleiben bei ungeprüfter Zeitbasis leer; Original-Gerätesekunden bleiben erhalten. Rückwärts laufende Gerätezeit blockiert eine irreführende Kurve, Originalexport bleibt möglich.
- Offline-Capture-Import und reproduzierbarer Historien-Performancecheck. Original-Capture erfolgreich importiert und wiederholt ohne Kopie geprüft; echte Historienansicht nur lesend geprüft.
- 49 automatisierte Tests bestanden; synthetische Browserprüfung einschließlich Historie, Export und mobiler Ansicht erfolgreich. Neue integrierte BLE-Strecke noch nicht im Dienst mit Hardware abgenommen; bestehender Dienst bleibt bis Neustart V0.2. Automatischer Sync, inkrementelles Nachladen und UTC-Zuordnung noch offen.

### Vorangegangene Protokollprüfung

- Reale GATT-Verbindung ohne Pairing, reine Geräte-/Uhrzeit-/Statusabfragen und vollständiger Historientransfer geprüft. Private Roh- und dekodierte CSV bleiben außerhalb des Repositorys. Noch kein produktiver Historienimport oder automatischer Sync.
- Unabhängiger, begrenzter Historienparser für Rahmenfragmentierung, vollständige und kompakte Messwerte, Anzahl-/Ende-/Rahmenzählerprüfung. Fehler sperren die Vollständigkeitsbestätigung; Gerätezeiten erhalten keinen erfundenen UTC-Offset. Jahresbasis der Kalenderantwort muss ausdrücklich festgelegt werden.
- BlueZ-Scans fordern wiederholte identische Advertising-Meldungen an, damit unveränderte Messwerte nicht durch Bleaks Duplicate-Filter als ausgefallener Empfang erscheinen. CSV-Speicherabstand bleibt bestehen. Laufender V0.2-Dienst noch nicht aktualisiert.
- 37 automatisierte Tests bestanden, einschließlich abgeschnittener/fehlerhafter Historien, Zeitkontext, Überlauf, wiederholter Zeitstempel und abgewiesener Leseantworten.

## 0.2.0 · 2026-11-21

- Auf dem headless DeskPi aktiviert: realer BT06-Empfang und wiederholte CSV-Speicherung im Dienst, tatsächliche Browseransicht samt Verlauf/Export geprüft. 28 automatisierte Tests bestanden.

- Lesender BT06-Advertising-Decoder für das belegte Firmwareformat 2.05; Temperatur, Feuchte, Spannung, RSSI und Status. Keine Gerätebefehle oder Kopplung für den Liveempfang.
- Eigene Datenquelle für echte Empfänge, monatliche CSV-Dateien mit Host-Zeitbasis, wählbarer Speicherabstand, sichtbare Datenalter-/Schreibfehler, Start/Pause und Wiederaufnahme nach Neustart.
- Gemeinsame Adaptersperre verhindert parallelen Liveempfang und Diagnose. Unbekannte Firmware/Identitäten werden abgewiesen.
- Diagramme/Export wechseln zwischen echten Empfängen und Simulation; manueller Zoom pausiert die Liveaktualisierung. UI und API bleiben während Updates bis zum Prozessneustart zusammen.
- Taupunkt und Klimaberechnungen bleiben gemäß Benutzerkorrektur bei V0.6. Historienimport bleibt V0.3 und benötigt eine funktionierende GATT-Verbindung.

## 0.1.0 · 2026-11-21

- Headless-Betrieb: mehrere ausdrücklich freigegebene Proxy-Adressen und systemd-Beispiel. Auf dem DeskPi unter `/klima/` hinter dem vorhandenen Login mit Dashboard-Kachel eingerichtet; Start nach Neustart als normaler Benutzer. Host- und Sandbox-Mountansichten müssen bei der Installation unterschieden werden.

- Portable Linux-Grundversion, Standardbibliotheks-HTTP-Server, Prozesssperre, Start/Stop/Status/Install/Update.
- Lokale responsive Weboberfläche mit eigenem SVG-/ICO-Favicon, ECharts 6.0.0, optionalem `/klima`-Basispfad und Proxy-Origin.
- Validierte Programmeinstellungen mit Save Settings / Load Settings. Keine gesonderte Backupfunktion; Windows zurückgestellt.
- Getrennte synthetische Testdaten, Seed, Szenarien, Monats-CSV, Originalexport und Min/Max-erhaltende Grafikverdichtung.
- Private ioBroker-Vorlagen über bewusst gestartetes lesendes CLI-Werkzeug; keine Gerätekennungen oder echten Vorlagen im Git-Bestand.
- Explizite BLE-Suche und GATT-Inventar als CLI und Webauftrag. Optionale Betriebssystem-Kopplung; kein automatischer Verbindungsaufbau oder Logger-Schreibbefehl.
- Automatisierte Tests für Einstellungen, Dateifehler, CSV, Reproduzierbarkeit, Zeitumstellung, Lücken, Einzelinstanz, HTTP, CSRF und Datenisolation.
- Grenzen: echte BT06-Kommunikation und SMApi-Betrieb noch nicht geprüft; keine produktive Historie, Klimarisikobewertung oder Windows-Version.

Nächster fachlicher Schritt: konkretes BT06-Modell/Firmware identifizieren und Advertising-/GATT-Belege prüfen; daraus Messwertparser und Historienprotokoll ableiten.
