# BT-06_Weblogger – vollständige Projektspezifikation

## 1. Ziel und Plattform
Portable lokale Langzeitüberwachung schimmelgefährdeter Stellen: Temperatur, relative Feuchte, Taupunkt, absolute Feuchte, Oberflächenfeuchte, Kondensationsgefahr, kritische Feuchteperioden, Statistik und Berichte. BT06 vollständig konfigurieren und Historie auslesen. Keine Cloud, KI, Telemetrie oder Internetabhängigkeit im Betrieb.
Linux als führende Version (Linux-PC, Server, Raspberry Pi, ARM32/ARM64/x86-64 soweit möglich). Python, BlueZ, Bleak, FastAPI oder schlanker HTTP-Server, HTML/CSS/JS, lokal gebündeltes Apache ECharts. Später Windows-PowerShell-Version mit Windows Runtime BLE und bei Bedarf lokalem .NET-Hilfsmodul, ohne zwingendes Python. Machbarkeit früh untersuchen. Gemeinsame API, Frontend, Datenformate, Berechnungen und Tests. Priorisierung siehe ROADMAP.md.

## 2. Hardware und Protokoll
BT06 BLE Temp & RH Data Logger, vermutlich TZONE, LCD, Start/Stop, Batterie, eigener Speicher vermutlich bis 32.000 Messungen. Referenz: https://github.com/TZONE-Team/BTLogger-Android. Herstellerunterlagen, Lizenz, tatsächliche Firmware und Protokoll prüfen. Keine unbestätigten Befehle oder Grenzwerte als Tatsachen behandeln. Lesendes Diagnosewerkzeug für Advertising, GATT-Services, Characteristics, UUIDs, Notifications und Rohdaten entwickeln; Protokoll dokumentieren.

## 3. Portabilität und Betrieb
Alle programmbezogenen Dateien relativ zum Programmordner; bei beendetem Programm kopierbar. OS-Abhängigkeiten dokumentieren, möglichst lokal bündeln. Kein Root/Admin im Normalbetrieb. Linux start.sh, stop.sh, status.sh, install.sh, update.sh; optional systemd-Dienst mit Wiederanlauf, kein unnötiger Hilfsdaemon. Später start.ps1/stop.ps1, optional Windows-Hintergrundbetrieb.
Verzeichnisse: config/settings.json, config/devices.json, config/profiles/, backend/common/, backend/linux/, später backend/windows/, web/index.html, web/css/, web/js/, web/assets/, data/<logger-id>/<jahr>/<jahr-monat>.csv, events/, statistics/, backup/, export/, logs/, tools/, tests/, docs/.
Modi: portabel (auslesen, analysieren, konfigurieren, beenden), Dauerbetrieb, LAN-Server, Offline-Auswertung ohne Logger, Konfiguration, Diagnose, Simulation. Simulationsdaten klar kennzeichnen und getrennt speichern. Keine realen Nutzerdaten im öffentlichen Repo.

## 4. BLE-Kommunikation und Aufzeichnung
Automatische Suche, manuelle Auswahl, Geräte-ID, Firmware, Adresse/Kennung, RSSI, Batterie, Live-Temperatur/Feuchte, Geräte-/Aufzeichnungsstatus, Konfiguration und Speicherbelegung sofern unterstützt. Gesamte Historie auslesen, fehlende Daten nachladen, automatische Synchronisierung und Wiederverbindung. Mehrere Logger vorbereiten, paralleler Betrieb P1.
Logger zeichnet autonom auf, auch ohne Host. Historie beim erneuten Verbinden nachladen, soweit noch verfügbar. Logger-Originalmessung als bevorzugte Langzeitquelle. Historische, Live-, importierte, simulierte und externe Messungen unterscheiden. Deduplizierung zwischen Live und Historie, Konflikte sichtbar behandeln. Datenlücken nie erfinden oder verdecken.

## 5. Vollständige BT06-Konfiguration
Alle nachweislich unterstützten Einstellungen lesen und schreiben: Name, Beschreibung, Celsius/Fahrenheit, Aufzeichnungsintervall, BLE-Sendeintervall, Sendeleistung, Long Range, Temperatur- und Feuchte-Min/Max-Alarme, Alarmaktivierung, Zugangsschlüssel, Datum/Uhrzeit, Startverzögerung, Verhalten bei vollem Speicher und weitere dokumentierte Funktionen.
Vermutete Grenzen (verifizieren): Aufzeichnung 10 s–18 h, Advertising 0,5–30 s, Leistung -20 bis +8 dBm.
Start/Stop, Historie, Speicheranzeige, Geräteinformationen; Profile, Konfigurationsvergleich, Wiederherstellung und verbleibende Dauer nach Priorität. Nicht unterstützte Funktionen ausblenden/kennzeichnen. Tatsächliche Einstellungen beim Verbinden auslesen, nie ungefragt Defaults schreiben. Speichern nur bewusst, Dirty-Status/Speicherbutton bei Änderungen; Rücklesen zur Verifikation.
Hardware-Alarme getrennt von Softwarewarnungen.

## 6. Schutz der Loggerdaten
Konfiguration kann möglicherweise Historie löschen. Vor potenziell destruktivem Vorgang: Zustand feststellen, vollständigen Speicher auslesen, dauerhaft lokal speichern, Vollständigkeit verifizieren, Aufzeichnungsstatus dokumentieren, Folgen anzeigen, explizite Bestätigung, nötigenfalls Aufzeichnung stoppen, schreiben, rücklesen/verifizieren, ggf. erneut starten, Änderung und Lücke protokollieren. Bei fehlgeschlagenem Backup blockieren. Nie automatische Speicherlöschung oder Werksreset. Schreibbefehle nur dokumentiert/verifiziert und serialisiert. Entwicklungsdiagnose zunächst ausschließlich lesend.

## 7. Native CSV-Datenhaltung
Keine SQLite oder andere Datenbank. CSV ist Originalspeicherformat: UTF-8, Semikolon, Dezimalkomma, ISO-8601 mit Offset, identisches Format auf beiden Plattformen, Excel-kompatibel, monatliche Dateien pro Logger, automatisch erzeugte Pfade, chronologisch, unbegrenzt erhalten. Fehlendes Feld leer statt Null. Beispiel:
```csv
Zeitstempel;Temperatur;Feuchte;Batterie;RSSI;Quelle;Messstelle;Qualitaet
2026-11-21T08:00:00+01:00;18,1;74,2;85;-62;Logger;Aussenwand;OK
2026-11-21T08:05:00+01:00;18,2;73,8;;;Logger;Aussenwand;OK
```
Weitere Spalten für robuste Identifikation nach Protokollanalyse definieren. Nicht lokale Uhrzeit allein als Schlüssel; UTC/Offset, DST, Loggeruhränderung, Neustart und Aufnahmeperioden berücksichtigen. Historische Batterie/RSSI nur bei tatsächlich verfügbaren Werten. Messstelle mit stabiler ID/historischer Zuordnung. Einheiten und Schema dokumentieren. CSV-Bibliothek modular. Klimawerte dynamisch berechnen.
Separate CSV für Ereignisse, Warnungen, kritische Perioden, Konfigurationsänderungen, Messstellenhistorie, optionale Wandtemperaturen, regenerierbare Tages-/Monatsstatistiken. Einstellungen/Profile JSON.

## 8. Datensicherheit
Unmittelbar dauerhaft speichern, Erfolg erst nach erfolgreichem Schreibabschluss, einzelner koordinierter Schreiber/Dateisperren, unvollständige Zeilen nach Absturz erkennen und sichern. Atomare Ersetzung bei größeren Änderungen, Backup vor umfangreicher Änderung, Historienimport ausfallsicher und wiederaufnehmbar. Schreibfehler anzeigen. Keine Daten-/Einstellungslöschung bei Update. Automatische/manuelle konsistente Backups auch bei Dauerbetrieb; Restore. Nach Neustart/Abbruch weiterarbeiten. Originaldaten nie durch statistische Verdichtung ersetzen.

## 9. UI und Navigation
Deutsch, kompakt, einheitlich, hell/dunkel, responsive, Maus/Touch, einheitliche Farben, Tooltips, einklappbare Expertenblöcke, dynamisch relevante Optionen, keine externen Fonts/CDNs. An ESPA-Monitor und kompakter Growbox-Weboberfläche orientieren sofern verfügbar. Identische Webdateien Linux/Windows. Kleines Display: einklappbares Menü.
Menü: Übersicht, Klimaverlauf, Schimmelrisiko, Klimakalender (P1), Statistik, Ereignisse, Messstellen, Logger, Datenexport, Einstellungen, Diagnose.
Übersicht: Temperatur, rF, Taupunkt, absolute Feuchte, optionale Wandtemperatur/Oberflächenfeuchte, Klimastatus, Risikobewertung, Dauer kritischer Bedingungen, Feuchtestunden, letzte Messung/Synchronisierung, Verbindung, RSSI, Batterie, Aufzeichnung, Speicher, verbleibende Dauer (P1), kompaktes Diagramm, Warnungen, Exportbutton. Alte Werte nicht als live darstellen.

## 10. Interaktive Diagramme
Apache ECharts lokal bündeln, identisch auf beiden Plattformen. Mouseover-Tooltip mit Datum/Uhrzeit und allen aktiven Kurven, Fadenkreuz, Mausrad-/Touchzoom, Verschieben, Navigator und grafische Zeitraumwahl, Legendenklick zum Ein-/Ausblenden, Doppelklick/Reset, Vollbild, automatische/manuelle Y-Achsen, vorheriger/nächster Zeitraum, Live-Modus, Updates ohne Reload. Grenzlinien und transparente Warnbereiche, Datenlücken sichtbar. Zoom, Zeitraum, Kurvenauswahl nicht bei Aktualisierung, Größenänderung oder Displaydrehung zurücksetzen; Einstellungen persistieren. Direkter Export.
Zeiträume: 1, 6, 12, 24, 48 h; 7, 14, 30 Tage; 3, 6 Monate; 1 Jahr; alles; freie Start-/Endzeit einschließlich Uhrzeit.
Kurven: Temperatur orange, relative Feuchte blau, Taupunkt türkis, absolute Feuchte grün, Wandtemperatur violett, Oberflächenfeuchte rot, kritische Oberflächentemperatur, Taupunktabstand, Batterie und optionale Sensoren. Fehlende Kurven deaktivieren/ausblenden. Geeignete Achsen je Einheit.
P1: PNG, Min/Max/Mittel-Linien, Tag/Nacht, Vergleichszeitraum, synchronisierte Diagramme, eigene Farben/Profile, manuelle Markierungen. Ereignisse, Lüftung und Kondensationsbereiche nach verfügbaren Funktionen markieren.
Performance: Millionen Messwerte, relevante Monatsdateien laden, zeitbereichsabhängige Min/Max-erhaltende Verdichtung, beim Zoom Details nachladen. Statistik und Rohdatenexport basieren nicht auf verdichteten Grafikdaten.

## 11. Klimaberechnung
Taupunkt, absolute Feuchte g/m³, Sättigungsdampfdruck, Wasserdampfpartialdruck, Temperatur-/Feuchteänderungsraten, kritische Oberflächentemperatur für 70/80 % rF, Taupunktabstand zur Wand, geschätzte Oberflächenfeuchte. Dokumentierte Magnus- oder vergleichbare Formeln, Gültigkeitsbereiche und Unsicherheiten, Referenztests. Gemessen/berechnet/angenommen klar unterscheiden.

## 12. Schimmelrisiko und Wärmebrücke
Zeitabhängige orientierende Bewertung anhand Luftfeuchte, Temperatur, geschätzter Oberflächenfeuchte, Dauer und Wiederkehr kritischer Perioden, kumulierter Feuchtestunden, Kondensation, Abtrocknung, Unsicherheit und Datenlücken. Einstellbare Schwellen, Mindestdauer, Hysterese; beispielhaft 60/70/80/90 % rF, Luft/Oberfläche getrennt. Status unauffällig, erhöht, kritisch, länger kritisch, Kondensationsgefahr, unzureichende Datenbasis. Gründe transparent. Keine erfundene Schimmelwahrscheinlichkeit, kein Nachweis/Ausschluss tatsächlichen Befalls.
BT06 misst Luft, nicht Wand. Manuelle Wandtemperatur, angenommene Luft-Wand-Differenz, zeitlich begrenzte Messungen, Vergleich angenommener Temperaturen, kritische Wandtemperatur und Taupunktabstand. Interaktiver Rechner mit Reglern für Lufttemperatur, rF und Wandtemperatur. Keine Oberflächenfeuchte ohne Wandtemperatur/Annahme; niemals berechnete Werte als gemessen ausgeben. Externe ESP32/DS18B20-Sensoren später.

## 13. Statistik, Kalender, Lüftung
P0: frei wählbarer Zeitraum, Min/Max/Mittel, Feuchtestunden, längste kritische Phase, Zahl Ereignisse, Datenabdeckung/Lücken. Zeitgewichtung bei unregelmäßigen Intervallen, Lücken nicht als kritische oder unkritische Zeit zählen.
P1: Median, Verteilungen, Tag/Nacht/Woche/Monat/Jahr und Messstellenvergleich, Cache, Kondensationsdauer. Kalender mit grün unauffällig, gelb erhöht, orange länger erhöht, rot kritisch, violett mögliche Kondensation, grau unzureichende Daten; Tagesdetails, Diagramm, Statistik, Ereignisse, Lücken, Notizen, Monats-/Jahresnavigation.
P1: vermuteten Lüftungsbeginn/-ende, Dauer, Temperaturänderung und Änderung absoluter Feuchte erfassen. Mit einem Innensensor nur vermutet, keine sicheren Empfehlungen aus Innen-rF allein. Außensensor später.

## 14. Ereignisse, Warnungen und Messstellen
CSV-Ereignisse: Temperatur hoch/niedrig, erhöhte/kritische Luft-/Oberflächenfeuchte, Kondensation, Ende kritischer Phase, Verbindung weg/wieder da, Synchronisierung Start/Ende/Fehler, Batterie/Speicher, Aufzeichnung Start/Stop, Konfiguration/Uhrzeit, Import, Backup, Schreibfehler; Lüftung und manuelle Ereignisse nach Priorität. Filter Zeitraum, Logger, Messstelle, Typ, Schweregrad. Zusammenhängende Ereignisse statt Meldungsflut. Warnungen bei fehlenden Daten, langer Trennung, Speicher-/Sync-Fehlern; in UI und Ereignislog. Lokale OS-Benachrichtigung P1, MQTT/E-Mail/HA P2.
Messstelle: stabile ID, Name, Raum, Beschreibung, Logger, Zeit der Zuordnung, individuelle Grenzwerte, optionale Wandtemperatur/Außenbezug, Notizen, Foto P1. Loggerwechsel erhält alte Messstellenzuordnung. Mehrere Messstellen und spätere gemeinsame Darstellung. Beispiele Außenwand, Fensternische, hinter Schrank, Bad, Keller, Ecke, Raummitte.

## 15. Export
P0 sichtbarer Button Übersicht, Klimaverlauf und Statistik sowie eigene Exportseite. Messstelle/Logger, freie Start-/Endzeit (Datum/Uhrzeit), Presets, alles, aktueller Diagrammzeitraum als Vorschlag, einzelne Messwerte und optionale berechnete Werte wählbar. CSV in Originalauflösung standardmäßig, Browserdownload oder export/-Ordner; automatische Dateinamen (Aussenwand_2026-11-01_bis_2026-11-30.csv). Auch offline ohne BT06. P1: mehrere Messstellen gemeinsam, Anzahl Vorschau, Minuten-/Stunden-/Tagesaggregate mit dokumentierter Auflösung, XLSX, PDF, Kalender-Exportbutton, PNG.
PDF: druckbarer Klimabericht mit Messstelle, Beschreibung/Foto, Gerät, ID, Zeitraum/Intervall, Diagrammen, Temperatur/Feuchte/Taupunktstatistik, Feuchtestunden, kritischen Phasen, Kondensation, Kalender, Datenlücken, Schwellen, Wandtemperaturannahmen, Zusammenfassung und Notizen. Für Dokumentation gegenüber Vermieter/Eigentümer; keine unbelegten Aussagen über Befall oder Verursacher.

## 16. Einstellungen und Diagnose
Allgemein: Sprache, Theme, Startseite, Standardzeitraum, Aktualisierung, Einheiten, Datumsdarstellung. BLE: Geräte, Suche/Wiederverbindung/Sync-Intervall, Timeout, Diagnose. Klima: Schwellen, Mindestdauer, Hysterese, Kondensation, Wandannahme. Diagramme: Zeitraum, sichtbare Kurven, Farben, Achsen, Grenzen, Updates. Speicherung: Pfade, Backup-Intervall, Cache, Verbrauch, Import/Restore. Webserver: Port, Lokal/LAN, Zugangsschutz, Autostart. Expertenblöcke einklappbar; Komfortoptionen gemäß P1.
Diagnose: Version, OS/Architektur, Laufzeit, Adapter, BlueZ, Geräte/GATT/Firmware, RSSI/Batterie, Verbindungsstatistik, Abfragen/Fehler, Sync-Status, Datenanzahl/älteste/neueste, CSV-Status, Speicherverbrauch/freier Platz, letzte Sicherung. Ausführliches BLE-Log und Diagnoseexport nach Priorität. Keine Schlüssel in Logs.

## 17. API und Sicherheit
Dokumentierte gemeinsame HTTP-API: Status, Geräte/Suche/Verbindung, Live/Historie/Sync, Gerätekonfiguration und Aufnahme, Messstellen, Berechnungen, Statistik, Ereignisse/Warnungen, Export, Backup, Einstellungen, Diagnose. Fortschritt für Sync/Export melden. Frontend keine OS-Aufrufe.
Standard bind localhost, LAN ausdrücklich aktivieren und absichern. Zugriffsschutz und Schutz vor unbefugten Schreib-/destruktiven API-Aktionen, sichere Importdateien und Pfade. BLE-Schreiboperationen serialisieren. Keine Cloud, Telemetrie, unnötige Privilegien.

## 18. Automatisierung und Erweiterbarkeit
Wiederverwendbare Skripte: Abhängigkeiten, Installation, Setup, Start/Stop/Restart/Status, BLE-Diagnose/Suche, Logauswertung, Import/Export, Backup/Restore, Updates, Tests, Simulation, portable Releases. Wiederholt sicher ausführbar, Betriebssystemänderungen/Berechtigungen dokumentieren. Keine unnötigen stets laufenden Hilfsdienste.
Treiber, CSV, Berechnungen, API und Frontend modular. Später weitere BT06, andere BLE-Sensoren, ESP32, DS18B20, Außenklima, MQTT/HA, zusätzliche Alarmierungen, Berechnungen und Exporte.

## 19. Tests und Dokumentation
Automatisierte Tests für CSV-Lesen/Schreiben/Import/Export, Verdichtung, Dedupe, Historienimport, beschädigte Zeilen, Schreibfehler, Abstürze, DST, Loggerzeitänderung, Lücken, Klimaformeln, Statistik/Feuchtestunden, Schwellen/Hysterese, API, Konfiguration, Backup/Restore. Hardwaretests, destruktive nur ausdrücklich freigegeben. Später Plattformvergleich, identische Berechnungen und kompatible CSV/JSON.
README, AGENTS, ROADMAP, CHANGELOG, BLE-Protokoll, CSV- und API-Spezifikation, Architektur, Installations-/Bedienungs-/Testdokumentation pflegen. Versionsangaben konsistent; je Version Funktionen, Fixes, Tests, Grenzen, offene Punkte und nächster Schritt. Roadmap ist verbindlich.
