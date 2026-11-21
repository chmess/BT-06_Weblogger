# Änderungen

## 0.4.2-dev · 2026-11-21

- Erste integrierte Gerätevorbereitung erfolgreich: vollständige Historie und alle acht unterstützten Einstellungsabfragen dauerhaft geprüft gespeichert, Hostempfang wieder aufgenommen. Nach konkreter Nutzerbestätigung bestätigte der BT06 App-Stopp und Aufzeichnungs-Setter. Zweite vollständige Historie nach Stopp ebenfalls gesichert. Zwischenprüfung brach anschließend vor Save/Abschluss ab. Erneutes reines Auslesen: bisheriger Intervallwert, App-Stopp, keine Historienlöschung.
- Die Vor-Save-Prüfung verlangte bereits den endgültigen Zielwert. Korrigiert: nur bei konkret geänderten Blöcken sind vor Commit exakt Ausgangs- oder Zielblock erlaubt; jeder dritte Wert und jede Abweichung ungeänderter Felder blockieren Save. Nach Commit bleibt ausschließlich der Zielwert zulässig. Getrennte Protokollierung der Sichtbarkeit vor Commit; Zwischenbeleg auch bei Abweichung dauerhaft erhalten, ebenso Stoppbeleg vor zweiter Vollauslesung.
- 103 Python-Tests einschließlich verzögert sichtbarer Setter, unverändertem Wert trotz Save-ACK, unzulässigem Zwischenwert und bereits gestopptem Gerät; Browserprüfung. Korrigierter Save-Ablauf noch nicht am realen Gerät abgenommen. Keine automatische Wiederholung, kein Start und kein Reset. Aktivierung der Korrektur erfordert Dienstneustart.

## 0.4.1-dev · 2026-11-21

- Kontrollierter, expliziter Schreibablauf für Name, gemeinsame Funkparameter und Aufzeichnungsintervall vorbereitet. Getrennte Geräte-/Historienvorbereitung und Bestätigung; einmalige, zehn Minuten gültige Vorbereitung an Identität/Firmware/Adapter und aktuellen Einstellungsbeleg gebunden. Keine generische Byte-, Reset-, Unlock-, Uhr- oder Start-Route.
- Vor jedem Schreibauftrag aktuelle Einstellungen vergleichen und gesamte Historie dauerhaft prüfen/speichern. Bei laufender Aufzeichnung erst danach explizit bestätigter Stopp; anschließend nochmals gesamte Historie sichern. Unbekannte Nichtnullfelder im Aufzeichnungsblock sperren Änderungen; keine SDK-Null-Defaults. Zwischenprüfung vor Commit, danach Rücklesen aller Einstellungen und Prüfung unveränderter Gegenwerte. Aufzeichnung bleibt gestoppt.
- Herstellerreferenz auf verketteten Abschluss nach Save geprüft; Stop-, Set-, Save- und Abschlusssequenzen unabhängig implementiert. Dauerhafter CSV-/JSON-Auftragsbeleg vor jedem möglicherweise wirksamen Befehl; unklare Ergebnisse ohne automatische Wiederholung oder Rollback. Vorbereitungen werden nach Neustart nicht wiederaufgenommen. Gemeinsame BLE-Sperre, bisheriger Hostempfang nach jedem Ausgang wiederhergestellt.
- 99 Python-Tests und Browserprüfung bestanden: simulierter vollständiger Ablauf, Fehler vor/nach Stopp, negative/unklare Antworten, Schreib-/Rücklesefehler, einmalige Bestätigung, Ablauf/Ersetzung/Neustart, CSRF/Sperre, zwei Bestätigungen und Entwurfsänderung. **Noch kein realer Geräteschreibtest**, Dienstaktivierung erforderlich. Vollständige V0.4-Konfiguration und unbeaufsichtigter Zugriff weiterhin offen.

## 0.4.0-dev · 2026-11-21

- Änderungsvorschau für Gerätename, Sendeintervall und Sendeleistung mit strengem Wertevergleich und Bezug auf den aktuellen Originalbeleg. Erhält ungespeicherte Eingaben bei neuer Auslesung; veraltete Entwürfe und unbekannte Funk-Gegenwerte blockiert. Keine Gerätebefehle, keine Schreibfreigabe; Warnung vor möglichem Historienverlust und notwendige Vollauslesung/Bestätigung/Rücklesen sichtbar. 88 Python-Tests bestanden.
- Fortschritt, Tastensignal und Fehler eines Einstellungs-Leseauftrags direkt bei den Geräteeinstellungen angezeigt. Fehlgeschlagene Aufträge ausdrücklich ohne neuen Stand; bisherige Werte bleiben sichtbar. Installierter Leseweg mit acht erfolgreichen Geräteabfragen und neuem dauerhaftem Stand geprüft.
- Erste lesende Geräteeinstellungsansicht: belegte Name-/Zeit-/Status-/Aufzeichnungs-/Funk-/Alarmabfragen, neue Anzeige, verifizierter CSV-Rohbeleg und JSON-Zusammenfassung. Kein Setter, Speichern am Logger, Start/Stop oder Uhränderung.
- Neue Abfragen am realen BT06 erfolgreich; unbekannter Funkmoduscode wird ausdrücklich nicht als Long-Range-Zustand interpretiert. Weitere SDK-Parameter bleiben unbekannt statt auf Standardwerte gesetzt.
- BlueZ-Cacheverlust nach Stop der Suche durch erneute Auswahl mit Adresse, Gerätekennung und Firmware abgedeckt. Automatisches Verbindungsfenster für vorhandene Einträge auf 35 Sekunden erweitert, um ein 30-Sekunden-Sendeintervall zu berücksichtigen; nach frischer Suche kurzes Fenster.
- Verbindung mit nur kurzem STOP erfolgreich. Längerer Versuch ganz ohne Tastenaktion weiterhin Timeout; Automatik bleibt aus und wird nicht als zuverlässig abgenommen dargestellt.
- 82 automatisierte Tests und synthetische Browserprüfung erfolgreich; gespeicherte Originale zusätzlich nur lesend geprüft. Lese-UI/API im installierten Dienst bestätigt; die verbesserte lokale Fehler-/Fortschrittsanzeige erfordert einen weiteren Dienstneustart. Kontrollierte Schreibfunktionen bleiben offen.

## 0.3.2-dev · 2026-11-21

- Optionale automatische Nachladeversuche innerhalb des bestehenden Prozesses: standardmäßig aus, explizite Gerätebindung, 15–1440 Minuten Intervall, frischer Liveempfang erforderlich, kein automatischer Vollabruf. Begrenzte Verbindungsdauer, längere Wartezeiten bei Fehlern und dauerhafter Versuchszustand.
- Neue Messungen platzsparend als CSV-Fortsetzung gespeichert, vollständiger Zwischenstand spätestens nach 32 Schritten. Manifestversion 2, vorhandene Version 1 weiter lesbar. Keine Änderung alter Originaldateien.
- Ausdrücklich bestätigte historische Zeitzone pro Datenstand; zusätzlicher CSV-Export mit abgeleiteten Kalenderzeiten und Offset, Originalzeitstempel unverändert. Datum bleibt ungeprüft, spätere Werte werden nicht ungefragt zugeordnet; problematische Zeitumstellungsstunden blockiert.
- Gesamte Automatik einschließlich Wiederaufnahme und Speicherschutz synthetisch geprüft. Hardwareversuch ohne Tastendruck im aktuellen BT06-Modus: Timeout, keine Historienänderung, Hostempfang wieder gestartet. Automatik bleibt aus; unbeaufsichtigtes Auslesen nicht als erfolgreich behauptet.
- Neue UI/API erfordert Dienstneustart. Der bestätigte historische Zeitbezug ist separat hinterlegt; tatsächliche Geräteuhrkorrelation und geeigneter Verbindungsmodus bleiben offen.

## 0.3.1-dev · 2026-11-21

- Zeitbereichsabfrage am realen BT06 mit bekannten Rohwerten verifiziert und als begrenzter, reiner Lesepfad implementiert. „Neue Werte nachladen“ prüft 16 gespeicherte Vergleichswerte sowie Zähler und Grenzen, bevor neue Messungen übernommen werden. Keine Loggeränderungen.
- Exakte Rohdatenfortsetzungen werden als gemeinsamer Verlauf angeboten; abweichende Reihen bleiben getrennt, frühere Einzelstände bleiben erreichbar. Regenerierbarer Index im Arbeitsspeicher, keine Datenbank und kein zusätzlicher Dienst.
- Herkunft unterscheidet Vollauslesung und aus Basis plus Bereich fortgesetzten Stand. Ein Nachladebereich gilt ausdrücklich nicht als frischer Vollständigkeitsnachweis des gesamten Gerätespeichers. Gerätezeit bleibt ungeprüft.
- Neuer Nachladepfad mit realem BT06 erfolgreich geprüft: Vergleichswerte stimmen, neue Messungen übernommen, frühere Werte unverändert und Liveempfang wieder gestartet. 56 automatisierte Tests und synthetische Browserprüfung bestanden; fortgesetzter Originalverlauf nur lesend geprüft.
- Aktivierung der neuen UI/API erfordert noch Dienstneustart. Automatischer Sync, tatsächlicher UTC-Offset und uneindeutige/verschobene Historien bleiben offen.

## 0.3.0-dev · 2026-11-21

- Auf DeskPi aktiviert und manuelle integrierte BLE-/API-Strecke am realen BT06 erfolgreich geprüft: erwartete und empfangene Anzahl gleich, CSV-Prüfsummen und Originalexport stimmen; bisherige Werte unverändert enthalten, zusätzliche Messungen im konfigurierten Intervall. Liveempfang anschließend wieder aktuell, kein Sync-/Wiederaufnahmefehler.

- Vollständige Historien als unveränderliche Monats-CSV-Stände; Veröffentlichung erst nach CSV-/Manifest-fsync und atomarer Umbenennung. Inhaltskennung verhindert identische Kopien auch nach Neustart. Veränderte/überlappende Stände bleiben ausdrücklich getrennt; keine geratenen stabilen Geräteindizes.
- Manuelles lesendes GATT-Sync mit Fortschritt, begrenztem Empfang, gemeinsamer Adaptersperre, Abbruch beim Beenden und Wiederaufnahme des vorher aktivierten Hostempfangs. Keine automatische Kopplung oder Loggeränderung.
- Datenquelle Loggerhistorie mit Gerätezeitachse, freier Kalenderauswahl, Historienstandwahl und Original-CSV. UTC-Zeitstempel bleiben bei ungeprüfter Zeitbasis leer; Original-Gerätesekunden bleiben erhalten. Rückwärts laufende Gerätezeit blockiert eine irreführende Kurve, Originalexport bleibt möglich.
- Offline-Capture-Import und reproduzierbarer Historien-Performancecheck. Original-Capture erfolgreich importiert und wiederholt ohne Kopie geprüft; echte Historienansicht nur lesend geprüft.
- 49 automatisierte Tests bestanden; synthetische Browserprüfung einschließlich Historie, Export und mobiler Ansicht erfolgreich. Die anschließende Geräteprüfung im installierten Dienst war erfolgreich (siehe oben). Automatischer Sync, inkrementelles Nachladen und UTC-Zuordnung noch offen.

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
