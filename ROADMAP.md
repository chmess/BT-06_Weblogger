# Roadmap und Prioritäten

P0 = Muss für Linux V1.0. P1 = Wunsch nach stabiler Grundversion. P2 = spätere Erweiterung. Diese Priorisierung hat Vorrang bei terminlichen oder funktionalen Konflikten mit der Projektbeschreibung. Technisch nicht unterstützte Hardwarefunktionen dokumentieren.

## Bestätigte Änderungen / aktueller Stand
- Windows einschließlich früher Machbarkeitsprüfung zurückgestellt, bis Linux funktioniert.
- Keine gesonderte Backup-/Restore-Funktion. Save Settings / Load Settings für Programmeinstellungen genügen. Vor destruktiven Geräteaktionen reguläre Historie vollständig auslesen und Nutzerbestätigung verlangen.
- V0.1.0 umgesetzt: Offline-Weboberfläche, Save/Load Settings, getrennte synthetische CSV-Testläufe, lokaler ECharts-Verlauf, Roh-CSV-Export, Diagnosewerkzeuge und explizite BLE-Suche/GATT-Verbindungsprüfung mit optionaler Betriebssystem-Kopplung.
- V0.2.0 installiert und getestet: lesender Advertising-Empfang des belegten BT06-2.05-Formats, getrennte echte CSV-Datenquelle, Start/Pause, Datenalter und Export. Realer Empfang und wiederholte CSV-Speicherung im installierten Dienst erfolgreich; tatsächliche Browseransicht einschließlich CSV-Export geprüft.
- Private Zigbee-Vorlagen lokal möglich, keine persönlichen Gerätekennungen im Repository.
- V0.3.0-dev installiert: GATT ohne Pairing und vollständige Historienübertragung am realen BT06 erfolgreich. Sicherer Monats-CSV-Import, identische Wiederholungen ohne Kopie, getrennte Historienstände, Gerätezeit-Verlauf und Originalexport implementiert und geprüft. Manuelle BLE-/API-Strecke automatisiert und anschließend im installierten Dienst am realen BT06 geprüft; CSV-Integrität, Originalexport, unveränderter vorheriger Datenbestand und Wiederaufnahme mit frischem Liveempfang erfolgreich. Die Erweiterung V0.3.1-dev ergänzt geprüftes bereichsweises Nachladen mit 16 Vergleichswerten und einen gemeinsamen Verlauf für exakt fortgesetzte Reihen. Neuer Treiber am Gerät erfolgreich; Historien-/Nachladefunktionen inzwischen im installierten Dienst verfügbar. V0.3.2-dev ergänzt eine standardmäßig ausgeschaltete, gerätegebundene Automatik mit Fehlerwartezeiten und platzsparender Ablage. Ablauf synthetisch geprüft; realer Versuch ohne Tastendruck endete im aktuellen Modus im Timeout. Nutzer bestätigt Europe/Berlin für den bisherigen Datenstand; davon abgeleitete Kalenderzeiten sind separat exportierbar, tatsächliches Gerätedatum bleibt ungeprüft. Unbeaufsichtigter Zugriff im geeigneten Gerätemodus, tatsächliche Zeitkorrelation und verschobene/uneindeutige Reihen bleiben offen. März-Historie laut Nutzer mit erster Inbetriebnahme plausibel; keine automatische Zeitkorrektur.
- V0.4.0-dev teilweise installiert: belegte Geräteeinstellungen rein lesend am BT06 geprüft; integrierter Leseweg im laufenden Dienst mit acht Abfragen, neuem geprüften Stand und wiederaufgenommenem Liveempfang bestätigt. Sichere Rohbeleg-/Zusammenfassungsablage und Anzeige implementiert. Änderungsvorschau für Name/Sendeintervall/Sendeleistung vorbereitet, noch durch Dienstneustart zu aktivieren: Alt-/Neuwerte, Erhalt ungespeicherter Entwürfe, Sperre bei ersetztem Einstellungsbeleg, Hinweis auf vollständige Auslesung und ausdrückliche Bestätigung vor späterem Schreiben. Kein Geräteschreibpfad. Funkmoduscode noch nicht als Long Range zugeordnet; unbekannte SDK-Standardfelder werden nicht übernommen. BlueZ-Cacheverlust wird durch Identitäts-/Firmware-geprüfte Suche behandelt, automatische Verbindung berücksichtigt das langsame Advertising. Ohne Tastenaktion weiterhin Timeout; geeigneter unbeaufsichtigter Zugriff bleibt offen.
- V0.4.1-dev vorbereitet: gezielter Schreibpfad für Name, Sendeparameter und Aufzeichnungsintervall, noch nicht am realen Gerät getestet. Zweistufige Vorbereitung/Bestätigung mit Einmaltoken; gesamte aktuelle Historie vor Stop sowie danach nochmals dauerhaft lesen, ausschließlich belegte Parameter, Zwischenprüfung vor Save/Abschluss und finales Rücklesen. Unklare Antworten ohne Wiederholung/Rollback; Aufzeichnung bleibt gestoppt. Keine Reset-/Start-/Unlock-/Uhrfunktion. 99 Tests und synthetische Browserprüfung erfolgreich. Aktivierung und erster realer Test stehen aus.
- V0.4.2-dev Korrektur vorbereitet: V0.4.1 ist aktiviert; integrierte Vorbereitung und volle Historienprüfung real erfolgreich. Nach konkreter Freigabe Stopp und Parameterbefehl bestätigt, jedoch vor Save wegen Zwischenvergleich abgebrochen. Nachlesung: alter Intervallwert, App-Stopp, keine Historienlöschung. Vor-Commit-Prüfung akzeptiert künftig nur Ausgangs- oder Zielblock bei konkret geändertem Feld; finale Prüfung bleibt streng. Zwischenbelege auch bei Abweichung dauerhaft, bereits gestopptes Gerät ohne erneuten Stop. 103 Tests und Browserprüfung; korrigierter realer Save-/Abschlusstest nach Dienstaktualisierung ausstehend.
- V0.4.3-dev installiert und geprüft: gezielter Aufzeichnungs-Setter, Save und Abschluss real erfolgreich; Zielwert über neue reine Leseverbindung bestätigt, übrige Parameter unverändert. Nach Save liefert Status acht Nullbytes ohne Aufzeichnungsdetails; Advertising meldet Initialzustand. Parametererfolg wird getrennt vom Aufnahmezustand bewertet. Rein lesende Nachprüfung vollständiger ACK-/Historienbelege und strikt passender Werte, gegebenenfalls aus Originalantwort nach Commit ganz ohne zusätzliche BLE-Anfrage. 110 Tests und Browserprüfung; aktivierte Nachprüfung anhand echter Originalbelege bestätigt, ohne zusätzliche BLE-Anfrage oder geänderte Schreib-CSV. Originalhistorie erhalten, Hostempfang frisch. Kein Start und kein Reset.
- Hardwarestand: BT06 anhand Foto/Advertising zugeordnet, Firmwareformat 2.05, Livewerte und GATT-Service geprüft. Mit dokumentierten kurzen Tastenaktionen erfolgreich; eine weitere Verbindung gelang mit nur kurzem STOP. Unbeaufsichtigte Verbindung auch mit längerem Zeitfenster nicht erfolgreich; genaue Ursache/Funkmoduszuordnung noch offen.

- V0.4.4-dev installiert: kontrollierter Aufzeichnungsstart mit Vollhistorien-/Leerstandsbeleg, Bestätigung und lesender Zustandsprüfung. 119 Tests und Browserprüfung bestanden. Reale Leseverbindung erfolgreich, Historienumfang mit Status 3 abgewiesen; Bedeutung unbekannt, kein Leerstand behauptet, Start gesperrt. Kein Startbefehl gesendet.

- Aktuell: V0.4.5 installiert; originale SDK-Abfragereihenfolge real geprüft, weiterhin Status 3 ohne Zähler. Rohbeleg gespeichert. Nutzer autorisiert ausdrücklich Werksreset; geprüfte Herstellerunterlagen und aktuelle offizielle App liefern dafür keine bestätigte Prozedur (BT06-ClearFlash leer). Kein Reset/Start gesendet. Herstelleranleitung für Werksreset erforderlich. Nutzer hat anschließend Fortfahren ohne Werksreset und einmaligen Start trotz unbekanntem Bestand freigegeben. V0.4.6 vorbereitet: eng begrenzte Ausnahme mit Zusatzbestätigung und geprüfter Alt-CSV sowie rechnerische Speicherdauer. V0.4.6 läuft: genau ein Start positiv bestätigt und aktive Aufzeichnung anschließend per GATT-Status 16 nachgewiesen; gewähltes Intervall unverändert, Originalhistorie erhalten. Uhrkorrektur weiterhin offen.

- V0.4.7 vorbereitet: belegte Temperatureinheit °C/°F im geschützten Einstellungsablauf. Intervall und übrige Rohfelder bleiben erhalten; Altgeschichte wird vor Einheitenwechsel in bisheriger Einheit gesichert. Keine reale Änderung ausgeführt. Geräteuhr, Funkmoduszuordnung und übrige unbestätigte Felder bleiben offen.

- V0.4.7 im Dienst aktiviert. V0.4.8 vorbereitet: Temperatur-/Feuchtealarmgrenzen und Aktivierung im geschützten Einstellungsablauf; Originaltypen und Verzögerungen erhalten. Temperaturbearbeitung nur bei unverändertem °C-Modus. Hardwareänderung nicht ausgeführt; Uhr, Funkmoduszuordnung und weitere unbestätigte Felder weiterhin offen.

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
