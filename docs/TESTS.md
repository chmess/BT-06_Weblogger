# Prüfung · V0.3.0-dev · 21.11.2026

## Automatisiert

```sh
python3 -m unittest discover -s tests -v
node --check web/js/app.js
node tools/browser_smoke.mjs
python3 tools/benchmark.py
```

V0.1-Basis (17 Tests, in der V0.2-Suite enthalten): atomare Settings einschließlich simulierter Schreibfehler, Ablehnung ungültiger Einstellungen, Schutz bestehender Dateien, eindeutige Testläufe, reproduzierbare CSV, Monatsgrenzen, wiederholte DST-Stunde, Offsetpflicht, beschädigte Zeilen, Min/Max/Grafiklücken, vollständiger CSV-Export, exklusive Instanz, API-Routen, Favicon-MIME, Basispfad, mehrere explizite Proxy-Origins, Origin/Host/CSRF und Datenisolation. BLE-Unit-Tests verwenden ausschließlich künstliche Geräte: explizites Pairing, Trennung und serialisierte Aufträge, keine Characteristic-Zugriffe.

Chromium-Prüfung unter `/klima/` bestanden: leere Übersicht, Testgenerator, drei Kacheln, ECharts-Canvas, Zoom bei Größenänderung/Neuzeichnen, Save Settings, Load-Settings-Vorschau ohne sofortige Speicherung, bewusstes Speichern, 390-Pixel-Ansicht ohne Seitenüberlauf, fehlende optionale BLE-Abhängigkeit. Keine JavaScript-Ausnahmen oder externen Netzwerkabrufe. Screenshots und JSON-Bericht liegen lokal in `test-results/`, nicht im Git-Bestand. Das Browserwerkzeug verwendet isolierte temporäre Laufzeitdaten und beendet seine Testprozesse.

## Synthetischer Performancecheck auf dem DeskPi

Linux aarch64, Python 3.13.5. Ein Lauf, lokale Dateien, drei Testprofile, 30 Tage bei einer Minute Abstand:

| Vorgang | Ergebnis |
|---|---|
| 129.603 CSV-Zeilen erzeugen | 8,482 s |
| 43.201 Zeilen einer Messstelle abfragen/verdichten | 1,328 s |
| Ergebnis fürs Diagramm | 1.559 Grafikpunkte |
| Roh-CSV derselben Messstelle erzeugen | 1,492 s, ca. 4,15 MB |
| Maximales RSS des Benchmarkprozesses | 30.096 KiB, ca. 29,4 MiB |

Dies misst weder die RAM-Grundlast des Webservers noch gleichzeitige Browserabfragen, BLE oder SMApi. Zeitwerte sind Einzelmessungen und keine garantierten Latenzen. Der Test ist mit `tools/benchmark.py` reproduzierbar.

## Reale Geräteprüfung / Grenzen

- Gerätefotos gelesen und QR-Code lokal dekodiert. Modellaufschrift BT06; QR verweist auf TZONE-BTLogger.
- Bleak 3.1.0 und dbus-fast 5.2.0 ausschließlich in der lokalen `.venv` installiert. Keine Systempakete oder Bluetooth-Konfiguration geändert.
- Realer BLE-Scan auf dem DeskPi erfolgreich: `TempHumLogger` mit einer zum fotografierten Aufkleber passenden Kennungsfolge im Manufacturer-Payload gefunden. Adressen und Rohdaten bleiben unter `private/`.
- Zwei GATT-Inventarversuche am zugeordneten Gerät: Timeout, auch nach Umstellung auf sofortigen Verbindungsaufbau beim nächsten Advertising. Keine Kopplung versucht, keine Loggerparameter, Uhrzeit, Start/Stop, Notifications oder Speicherbefehle gesendet. Kein erfolgreicher Hardware-Verbindungstest behauptet.
- Private Zigbee-Vorlagen lesend erfasst. Bei zwei Vorlagen dient die siebentägige Historie als Basis; bei einer mangels Historie der aktuelle Zustand. Herkunft/Zustandszeitpunkt lokal dokumentiert. Erzeugte Szenarien bleiben synthetisch.
- Noch offen: GATT-Verbindung, Kopplungsbedarf, Historienprotokoll, SMApi, ARM32 und weitere Linux-Systeme. Keine Tests mit realem Historienimport oder destruktiven Einstellungen ausgeführt.

## Headless-Installation auf dem DeskPi

Unter `/klima/` hinter dem bestehenden nginx-Login eingerichtet; Dashboard-Kachel meldet den Dienst als erreichbar. Backend-Antworten für die ausdrücklich konfigurierten Host-/IP-Aliase: HTTP 200. Ohne Login liefern nginx-Seite, API und Favicon jeweils HTTP 401 mit dem vorhandenen Dashboard-Realm. Der Benutzer-Dienst ist aktiv und für den Start nach einem Neustart aktiviert. Ein echter Neustart wurde nicht durchgeführt. Der bestehende Dashboard-Dienst und nginx sind ebenfalls aktiv. Ein authentifizierter Zugriff vom anderen Endgerät wurde noch nicht geprüft.

Die Mountansichten der Ausführungsumgebung sind von der normalen SSH-/Hostansicht zu unterscheiden. Ein separat angezeigtes `/usr` oder `/etc` in der Sandbox beweist keinen entsprechenden Host-Mount.

## V0.2 – Liveempfang im installierten Dienst

28 Python-Tests bestanden, auch mit der lokal installierten Bleak-Umgebung außerhalb der Sandbox. Neu geprüft: Sign-Magnitude, Celsius/Fahrenheit, unbekannte Firmware, ungültige Sensorwerte, Geräteidentität, Host-Zeitbasis, CSV-Speicherabstand, Schreibfehler, unvollständige Endzeilen, Uhr-Rücksprung, Aufgabensperre und ausdrückliche Empfangsaktivierung/-pause. Der reale Bleak-Callback verlangt exakt zwei Parameter; die anfangs falsche Signatur wurde korrigiert und der korrigierte Pfad am Gerät erfolgreich geprüft.

Chromium-Test erweitert und bestanden: Wechsel zwischen Simulation und Echtdaten mit ausdrücklich künstlichen Protokoll-Testvektoren im temporären Testordner, Schema-2-CSV-Export, manueller Zoom pausiert Liveaktualisierung. Keine JS-Ausnahmen oder externen Requests.

Ein realer Advertising-Empfang mit angekündigter Firmware 2.05 wurde dekodiert und mit fsync in einer privaten Prüfdatei gespeichert. Dies ist kein GATT-/Historientest und kein Kalibrierungsnachweis. Die installierte Dashboard-Anwendung läuft mit V0.2.0. Der Benutzer hat den vorbereiteten Hostinstaller in seiner normalen SSH-Sitzung erfolgreich ausgeführt; dabei wurden keine Mounts verändert.

Der tatsächliche Dienst empfing mehrere reale Pakete und bestätigte mindestens zwei CSV-Stichproben mit 60 Sekunden Abstand. Der API-Verlauf lieferte dieselben gespeicherten Zeilen unter Quelle BLE-Advertising. Chromium prüfte die echte installierte Oberfläche ausschließlich mit GET-Abfragen: aktuelle Livekachel, reales Diagramm, CSV mit Host-Zeitbasis, Zoom-Pause, 390-Pixel-Ansicht ohne Überlauf, keine JavaScript-Ausnahmen oder externen Abrufe. Die Screenshots bleiben privat.

Korrektur der Mountdiagnose: In der normalen Benutzer-/SSH-Ansicht ist `/` schreibbar; dort sind `/usr` und `/etc` keine eigenen Mounts und sudo funktioniert. Die sichtbaren separaten `ro,nosuid,nodev`-Mounts gehören zum Ausführungskontext der Werkzeuge. Die frühere Aussage, sudo auf dem Host sei beschädigt, war falsch. Ein Mount-Reparaturversuch oder Host-Neustart ist nicht nötig. Der vorbereitete V0.2-Hostinstaller verwendet die normale sudo-Berechtigung und führt keinerlei Mountoperation aus.


## V0.3-Entwicklungsprüfung

37 automatisierte Tests bestanden. Neue synthetische Fälle: ausschließlich freigegebene Leseopcodes, negative/falsche Antworten, explizite Kalenderjahresbasis, fragmentierte und zusammengefasste Historienrahmen, jede mögliche Trunkierung eines Teststreams, widersprüchliche Anzahl/Endezähler, fehlender Zeitkontext, Nullintervall, Überlauf, unbekannte Typen, wiederholte Zeitstempel und Fahrenheit. Diagnose- und Receiver-Tests prüfen DuplicateData=True am Scanner-Aufruf.

Reale Hardwareprüfung separat erfolgreich: GATT-Inventar, Notifications und belegte Leseabfragen ohne Pairing; vollständige Historie nach expliziter temporärer Tastenaktion übertragen und privat dekodiert. Anzahl, Enderahmenzähler, Anfang/Ende und Zeitabstände passen. Ein anderer Leseopcode wurde abgewiesen, nicht als Erfolg gewertet. Negative Verbindungsversuche haben Hostempfang jeweils wieder aktiviert. Produktionsintegration, Gerätezeit/UTC-Zuordnung, Dedupe und unbeaufsichtigter Sync sind damit nicht getestet oder freigegeben. Laufender Dienst unverändert V0.2.


## V0.3.0-dev: Import und Oberfläche

49 automatisierte Tests bestanden außerhalb der Socket-beschränkten Sandbox. Zusätzlich geprüft: atomare Veröffentlichung und unveränderte Bestände bei simuliertem Schreibfehler, Wiederimport nach Neustart ohne Kopie, abweichende Stände getrennt, Monatswechsel, wiederholte Gerätezeiten, rückwärts laufende Uhr, Dateikorruption, Pfad-/Quellenprüfung, unveränderte Originalexportfelder, gemeinsame BLE-Steuerungssperre, simulierte BLE-Lesesequenz ohne Pairing, Fehler/Timeout beim Auftrag sowie Wiederaufnahme des vorherigen Empfangswunsches. Geordnetes Beenden bricht wartende BLE-Aufträge ab.

Synthetische Chromium-Prüfung: Quellenwechsel, Gerätezeitwarnung/-achse, Auswahl eines Historienstands, freie Geräte-Kalenderbereiche, Originalexport, Rückwechsel zur Simulation sowie bestehende Funktionen. 390 Pixel ohne Seitenüberlauf, keine JS-Ausnahmen oder externen Requests. Browserprozesse werden vor Entfernen der temporären Dateien abgewartet.

Die private Original-Capture wurde mit dem neuen Importer vollständig übernommen; wiederholter Import liefert denselben Stand ohne Kopie. Neue Ansicht und Originalexport der realen Historie wurden über einen nur lesenden Vorschauprozess geprüft; kein Start des zweiten BLE-Empfängers oder Änderung am laufenden Dienst. Die neue integrierte BLE-/API-Strecke ist damit noch nicht auf Hardware abgenommen. Keine zusätzliche Geräteaktion für diese Prüfung erforderlich.

Synthetischer `python3 tools/benchmark_history.py`-Einzellauf auf DeskPi: 32.000 Werte, Erzeugen/Dekodieren/Speichern 1,937 s; erneuter Import 1,891 s; Prüfsummen/Lesen/Diagramm 1,312 s; 401 Grafikpunkte; 7.542.480 CSV-Bytes; maximales RSS des gesamten Testprozesses 67.156 KiB (ca. 65,6 MiB). Keine garantierte Latenz, keine isolierte Server-Grundlast und keine SMApi-Messung.
