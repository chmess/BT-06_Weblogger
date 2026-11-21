# Änderungen

## 0.1.0 · 2026-11-21

- Portable Linux-Grundversion, Standardbibliotheks-HTTP-Server, Prozesssperre, Start/Stop/Status/Install/Update.
- Lokale responsive Weboberfläche mit eigenem SVG-/ICO-Favicon, ECharts 6.0.0, optionalem `/klima`-Basispfad und Proxy-Origin.
- Validierte Programmeinstellungen mit Save Settings / Load Settings. Keine gesonderte Backupfunktion; Windows zurückgestellt.
- Getrennte synthetische Testdaten, Seed, Szenarien, Monats-CSV, Originalexport und Min/Max-erhaltende Grafikverdichtung.
- Private ioBroker-Vorlagen über bewusst gestartetes lesendes CLI-Werkzeug; keine Gerätekennungen oder echten Vorlagen im Git-Bestand.
- Explizite BLE-Suche und GATT-Inventar als CLI und Webauftrag. Optionale Betriebssystem-Kopplung; kein automatischer Verbindungsaufbau oder Logger-Schreibbefehl.
- Automatisierte Tests für Einstellungen, Dateifehler, CSV, Reproduzierbarkeit, Zeitumstellung, Lücken, Einzelinstanz, HTTP, CSRF und Datenisolation.
- Grenzen: echte BT06-Kommunikation und SMApi-Betrieb noch nicht geprüft; keine produktive Historie, Klimarisikobewertung oder Windows-Version.

Nächster fachlicher Schritt: konkretes BT06-Modell/Firmware identifizieren und Advertising-/GATT-Belege prüfen; daraus Messwertparser und Historienprotokoll ableiten.
