# Roadmap und Prioritäten

P0 = Muss für Linux V1.0. P1 = Wunsch nach stabiler Grundversion. P2 = spätere Erweiterung. Diese Priorisierung hat Vorrang bei terminlichen oder funktionalen Konflikten mit der Projektbeschreibung. Technisch nicht unterstützte Hardwarefunktionen dokumentieren.

## Bestätigte Änderungen / aktueller Stand
- Windows einschließlich früher Machbarkeitsprüfung zurückgestellt, bis Linux funktioniert.
- Keine gesonderte Backup-/Restore-Funktion. Save Settings / Load Settings für Programmeinstellungen genügen. Vor destruktiven Geräteaktionen reguläre Historie vollständig auslesen und Nutzerbestätigung verlangen.
- V0.1.0 umgesetzt: Offline-Weboberfläche, Save/Load Settings, getrennte synthetische CSV-Testläufe, lokaler ECharts-Verlauf, Roh-CSV-Export, Diagnosewerkzeuge und explizite BLE-Suche/GATT-Verbindungsprüfung mit optionaler Betriebssystem-Kopplung.
- V0.2.0 installiert und getestet: lesender Advertising-Empfang des belegten BT06-2.05-Formats, getrennte echte CSV-Datenquelle, Start/Pause, Datenalter und Export. Realer Empfang und wiederholte CSV-Speicherung im installierten Dienst erfolgreich; tatsächliche Browseransicht einschließlich CSV-Export geprüft.
- Private Zigbee-Vorlagen lokal möglich, keine persönlichen Gerätekennungen im Repository.
- V0.3.0-dev vorbereitet: GATT ohne Pairing und vollständige Historienübertragung am realen BT06 erfolgreich. Sicherer Monats-CSV-Import, identische Wiederholungen ohne Kopie, getrennte Historienstände, Gerätezeit-Verlauf und Originalexport implementiert und geprüft. Manuelle BLE-/API-Strecke automatisiert geprüft; Geräteabnahme nach Dienstneustart steht aus. Verifizierter UTC-Offset, zusammengeführte Langzeithistorie, inkrementelles Nachladen und automatischer Sync bleiben offen. März-Historie laut Nutzer mit erster Inbetriebnahme plausibel; keine automatische Zeitkorrektur.
- Hardwarestand: BT06 anhand Foto/Advertising zugeordnet, Firmwareformat 2.05, Livewerte und GATT-Service geprüft. Kurzes Standard-BLE-Fenster per dokumentierter Tastenaktion erforderlich; unbeaufsichtigte Wiederverbindung noch nicht verifiziert.

## P0 – Muss
- Portable Linux-Anwendung nach ESPA-Monitor-Konzept; Start/Stop/Status, optional systemd; PC/Server/Pi, lokale responsive Weboberfläche, offline, gemeinsame API und Windows-kompatible Datenformate. Keine Datenbank.
- BLE-Suche, Auswahl, Identifikation, Live-Temperatur und Feuchte, Batterie/RSSI/Firmware/Status soweit verfügbar, Wiederverbindung, Fehlererkennung, komplette Historie, automatische Synchronisation/Nachladen, Speicherbelegung.
- Alle nachweislich unterstützten BT06-Einstellungen lesbar und schreibbar, insbesondere Name/Beschreibung, Temperatur-Einheit, Aufzeichnungs- und Sendeintervall, Sendeleistung, Long Range, Temperatur-/Feuchtealarme, Zugangsschlüssel, Gerätezeit, Startverzögerung, Speicherverhalten, Start/Stop. Vor potenziell destruktiver Änderung vollständiges Historienauslesen verifizieren, Zustimmung, Rücklesen.
- CSV nativ: UTF-8, Semikolon, Dezimalkomma, ISO-8601 mit Offset, pro Logger/Monat, unbegrenzte Speicherung, Dedupe, chronologische Historie, Datenlücken, Zeitumstellung, robuste Schreibvorgänge, beschädigte Zeilen erkennen. JSON-Konfiguration mit Save Settings / Load Settings, historische Messstellenzuordnung.
- Deutsche kompakte responsive UI, Maus/Touch, hell/dunkel, einklappbare Expertenoptionen, dynamische Verfügbarkeit, lokal gebündelte Assets. Seiten Übersicht, Verlauf, Schimmelrisiko, Statistik, Ereignisse, Logger, Messstellen, Export, Einstellungen, Diagnose.
- Übersicht: Temperatur, rF, Taupunkt, absolute Feuchte, Klimastatus, Dauer kritischer Bedingungen, Batterie, RSSI, Verbindung, Speicher, Aufnahme, letzte Messung/Sync, Diagramm, Warnungen, Export; alte Werte kennzeichnen.
- Interaktive Charts: Mouseover, Fadenkreuz, Datum/Uhrzeit, aktive Werte, Mausrad/Touchzoom, Verschieben, Kurven einzeln an/aus, Navigator, freie Zeitraumwahl, Presets (1/6/12/24/48 h, 7/14/30 d, 3/6 Monate, Jahr, alles), vorher/nachher, Vollbild, automatische/manuelle Achsen, Reset, Live, Grenzen/Warnflächen, Datenlücken, persistente Einstellungen und Export. Liveupdates erhalten manuellen Zoom und Auswahl. Flüssige Langzeitdarstellung, Min/Max erhaltende Verdichtung.
- Klimaberechnungen: Taupunkt, absolute Feuchte, Sättigungs-/Partialdruck, kritische Wandtemperaturen bei 70/80 % Oberflächen-rF, Oberflächenfeuchte und Taupunktabstand bei gemessener/angenommener Wandtemperatur. Berechnungen und Annahmen kennzeichnen.
- Zeitabhängige Schimmelrisikowarnungen: individuell konfigurierbare Luft-/Oberflächengrenzen, Mindestdauer/Hysterese, Feuchtestunden, zusammenhängende Phasen, Kondensation, Begründung, unzureichende Daten, manuelle Wandtemperatur oder Differenz, interaktiver Rechner. Keine Schimmelwahrscheinlichkeit.
- Grundstatistik über frei wählbare Zeiträume: Min/Max/Mittel, Feuchtestunden, längste kritische Phase, Ereignisanzahl, Datenabdeckung/Lücken; keine falsche Wertung fehlender Daten.
- Ereignis-CSV und Filter: Klima-/Kondensationswarnungen, Verbindungsverlust/-aufbau, Sync-Fehler, Batterie/Speicher, Start/Stop, Konfiguration, Schreibfehler.
- CSV-Exportbutton Übersicht/Verlauf/Statistik: Messstelle/Logger, Beginn/Ende inkl. Uhrzeit, Presets, aktueller Chartbereich, Feldauswahl, berechnete Werte optional, Originalauflösung, automatische Dateinamen, Browserdownload, ohne verbundenen Logger.
- Messstellen anlegen/benennen/beschreiben, eigene Grenzen, Loggerzuordnung mit Historie; keine falsche Zuordnung beim Wechsel.
- Sicherheit/Stabilität: keine unnötigen Root-Rechte, localhost standardmäßig, abgesicherter optionaler LAN-Zugriff, kontrollierte Geräteschreibbefehle, Neustart/Abbruch-Recovery, BLE-/CSV-Diagnose, Fehleranzeige, Datensicherung, automatisierte Tests, reproduzierbare Skripte, technische Dokumentation.

## P1 – Wunsch
- Diagramme: Min/Max/Mittel-Linien, Tag/Nacht, Vergleichsperioden, synchronisierte Diagramme, eigene Farben, PNG, manuelle Ereignisse, Profile.
- Statistik: Median, Verteilungen, Tag/Nacht/Woche/Monat/Jahr, Messstellenvergleich, regenerierbare Caches.
- Klimakalender: farbige Tagesbewertung, Monats-/Jahresansicht, Tagesdiagramme und Statistik, Ereignisse, Notizen.
- Vermutete Lüftung: Beginn/Ende, Dauer, Temperatur-/absolute Feuchteänderung, mögliche Wirkung, Chartmarkierungen.
- Export: XLSX/PDF, Minuten-/Stunden-/Tagesaggregate, mehrere Messstellen, Anzahlvorschau, automatische Berichte. PDF mit Messstelle/Foto, Diagrammen/Statistik, Feuchtestunden, kritischen Phasen, Kondensation, Kalender, Lücken, Notizen, Annahmen.
- Gleichzeitiger Betrieb mehrerer BT06, Konfigurationsprofile, Vergleich/Restore früherer Einstellungen, Restaufzeichnungsdauer, erweiterte BLE-Protokollanalyse.
- Komfort: individuelle Startseite, Darstellungsoptionen, Fotos, Tagesnotizen, eigene Ereigniskategorien, lokale OS-Benachrichtigungen, Diagnoseexport.

## P2 – Später
- Windows-Portierung erst nach funktionierender Linux-Version konkret planen. Gemeinsame UI/API/CSV/JSON anstreben; derzeit keine Windows-Arbeiten oder frühe Machbarkeitsprüfung.
- Weitere BLE-Sensortypen, ESP32, DS18B20-Wandtemperatur, Außenklima, gemeinsame Auswertung.
- Innen-/Außenvergleich, fundiertere Lüftungsempfehlungen, Wärmebrückenanalyse, Feuchteprognosen und nachvollziehbare Schimmelmodelle.
- MQTT, Home Assistant, E-Mail und weitere Alarmschnittstellen.

## Versionen
| Version | Schwerpunkt | Priorität |
|---|---|---|
| V0.1 | Architektur, BLE-Protokoll, Diagnose | P0 |
| V0.2 | Live, Geräteinformationen, CSV | P0 |
| V0.3 | Historie, Sync, Datensicherheit | P0 |
| V0.4 | Vollständige BT06-Konfiguration | P0 |
| V0.5 | UI, interaktive Diagramme | P0 |
| V0.6 | Klimaberechnung, Schimmelrisiko | P0 |
| V0.7 | Grundstatistik, Ereignisse, CSV-Export | P0 |
| V0.8 | Messstellen, Einstellungen speichern/laden, Diagnose | P0 |
| V0.9 | Dauerbetrieb, Stabilität, portable Skripte | P0 |
| V1.0 | Linux-Grundversion abnehmen | P0 |
| V1.1 | Erweiterte Statistik, Klimakalender | P1 |
| V1.2 | XLSX, PDF, erweiterter Export | P1 |
| V1.3 | Lüftungserkennung, Komfort | P1 |
| V1.4 | Erweiterte Loggerverwaltung | P1 |
| V2.0 | Portable Windows-PowerShell-Version | P2 |
| V2.x | Weitere Sensoren und Schnittstellen | P2 |

## Freigaberegeln
Stabilität und Datensicherheit zuerst; P1 darf P0 nicht verzögern. Spätere Erweiterbarkeit im Fundament beachten, keine unnötigen Platzhalter. Jede Version testen und dokumentieren. Prioritätsänderungen abstimmen. V1.0 erst nach verifizierter Erfüllung der hardwareseitig realisierbaren P0-Anforderungen freigeben. Linux bleibt führend.
