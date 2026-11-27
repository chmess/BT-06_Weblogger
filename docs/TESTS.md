# Prüfung · V0.4.4-dev · 21.11.2026

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


## Installierte manuelle Historienstrecke: Geräteprüfung erfolgreich

Nach Dienstneustart startete der Nutzer das manuelle Historienlesen in der Oberfläche. Der Dienst bestätigte vollständige Übertragung und dauerhafte Speicherung. Anschließend unabhängig lesend geprüft: empfangene und erwartete Anzahl gleich, alle Datei-Prüfsummen gültig, Original-CSV-Export exakt gleich dem gespeicherten Stand. Der frühere Historienstand ist unverändert erhalten; seine komplette Folge aus Geräte-Sekunden und Rohwerten entspricht dem Anfang des neuen Standes. Zusätzliche Messungen folgen unverändert dem Zehn-Minuten-Intervall. Aktivierter Hostempfang nach dem Auftrag wieder `receiving` mit frischen Werten; keine Sync-, Wiederaufnahme- oder Livefehler. Privater Prüfbericht: `private/installed-v03-hardware-report.json`.

Damit ist die integrierte manuelle BLE-/API-/CSV-Strecke auf dem realen BT06 geprüft. Dies ersetzt keine Prüfung von automatischem Sync, inkrementeller Zusammenführung, längerem Dauerbetrieb oder tatsächlicher UTC-Zuordnung.


## V0.3.1-dev: Nachladebereich und Präfixverlauf

56 automatisierte Tests bestanden. Neue Fälle: feste begrenzte Lesebereichsrahmen, ungültige Grenzwerte/Reservierungsbytes, Wiederholung ohne neue Daten, identisches Ergebnis aus Vollimport und aus Basis plus Bereich, geänderte Vergleichswerte/Zähler/Anfangsgrenzen, fehlende Basis, getrennte abweichende Reihen, wiederholte Zeitstempel, beschädigte CSV nach warmem Indexcache und simulierter BLE-Bereichspfad einschließlich Vollauslesung bei ungeeigneter Basis.

Chromium: exakt fortgesetzte synthetische Stände erscheinen als ein Verlauf mit korrekter Rohanzahl; frühere Einzelstände bleiben auswählbar. Nachlade-Button ohne Gerät gesperrt. Bestehende Quellen-, Kalender-, Export-, Zoom- und Mobilprüfungen weiterhin erfolgreich; keine JS-Fehler oder externen Requests.

Hardware getrennt geprüft: kleine Bereichsabfrage gegen bekannte Originalwerte; danach neuer Treiber mit Basis und 16 Vergleichswerten. Bereichsanzahl, Endemarkierung und Rohwertüberlappung stimmen; neue Messungen wurden ergänzt und vorherige Daten erhalten. Fortgesetzter Originalverlauf anschließend nur lesend in der Browser-Vorschau geprüft. Private Berichte unter `private/gatt-range-verification.json` und `private/incremental-driver-report.json`. Die neue UI/API benötigt noch Dienstneustart. Kein Nachweis für automatischen Sync oder korrekte UTC-Zeitbasis.


## V0.3.2-dev: Automatik, Speicher und bestätigte Zeitzone

74 automatisierte Tests bestanden. Automatik: standardmäßig aus, ausdrückliche Aktivierung, Bindung an Logger/Adresse/Adapter/Firmware, Start erst nach Frist, Pausen bei unfrischem/pausiertem Empfang oder belegtem Bluetooth, Abschalten während eines Auftrags, Wiederaufnahme des Empfangs, Fehlerwartezeiten nach Neustart, monotone Fristen bei Host-Uhrsprung und Blockade bei Persistenzfehler. Integration mit echtem HistoryJobs-Ablauf wird mit simuliertem BLE geprüft; automatische Aufträge dürfen nicht auf Vollabruf wechseln.

Speicher: nur zusätzliche Messwertzeilen, unveränderte IDs vorhandener Werte, rekonstruiertes Ergebnis nach Neustart, vollständiger Zwischenstand nach spätestens 32 Schritten, beschädigte Basis und alte Manifestversion 1. Zeitzonen: ausdrückliche Bestätigung, unveränderte Originale, begrenzter Rohpräfix, spätere Werte unbestätigt, abweichende Reihe abgewiesen, Winter-/Sommerzeitoffsets und Ablehnung mehrdeutiger/nicht existierender Stunden.

Chromium-Prüfung erfolgreich: Auto-Sync bleibt beim Speichern eines Intervalls aus, zusätzliche Zeitzonenbestätigung und abgeleiteter Export, spätere Werte unbestätigt sowie bestehende Quellen-/Verlaufs-/Zoom-/Mobilprüfungen. Originalverlauf und bestätigte historische Zeitzone zusätzlich nur lesend geprüft. Keine JS-Ausnahmen oder externen Requests. Die neue UI/API ist bis zum Dienstneustart noch nicht produktiv aktiviert.

Realer automatischer Verbindungsversuch ohne Tastendruck endete nach etwa acht Sekunden im Timeout; keine Historienänderung, Hostempfang wieder gestartet. Damit ist unbeaufsichtigtes Auslesen im aktuellen Gerätemodus ausdrücklich nicht erfolgreich abgenommen. Privater Bericht: `private/unattended-sync-report.json`. Automatik bleibt aus; geeigneter Gerätemodus und tatsächliches Gerätedatum müssen weiter geklärt werden.

Aktualisierter synthetischer Historienbenchmark (Einzellauf auf DeskPi, 32.000 Ausgangswerte): Vollimport 1,931 s, Wiederimport mit Inhaltsprüfung 2,726 s, Lesen/Diagramm 1,380 s. Drei neue Werte aus 19 übertragenen Vergleichs-/Neuwerten ergänzen: 1,263 s einschließlich synthetischem Capture-Aufbau, zusätzlich 823 Byte Messwert-CSV. Rekonstruktion und Verlaufsindex anschließend 1,784 s. Maximales RSS des gesamten Benchmarkprozesses einschließlich Datengenerator 107.260 KiB (ca. 104,7 MiB); keine Server-Grundlast oder SMApi-Messung. Test enthält zusätzlich zum Ausgangsbestand den vollständigen synthetischen Nachladefixture-Aufbau im selben Prozess.


## V0.4.0-dev: lesende Geräteeinstellungen

82 automatisierte Tests bestanden. Neue Fälle: BlueZ-Cache und erneute Suche mit passendem Adapter, Adresse, Kennung und Firmware; Zeitlimits für vorhandene/frisch gefundene Geräte; feste Getter einschließlich benötigter Leseparameter; keine Setter/Paarung; verifizierte Felddekodierung; unbekannte Formate ohne Defaultwerte; negative Antworten; Rohbeleg und Zusammenfassung widerspruchsfrei; Erfassungszeit aus Original; Dateifehler erhalten früheren Stand; gemeinsamer Einstellungsauftrag stellt Empfang wieder her und erzeugt keine Historienmessungen; API/CSRF/Sperre und keine Geräte-Schreibroute.

Chromium-Prüfung: neue lesende Feldanzeige einschließlich unbekannter Funkmodusbedeutung und gesperrter Leseaktion ohne Geräteauswahl. Bestehende Quellen-/Historien-/Zeitzonen-/Automatik-/Export-/Mobilprüfungen erfolgreich, keine JS-Ausnahmen oder externen Requests. Die gespeicherten Originalbelege zusätzlich nur lesend in der neuen Ansicht geprüft. Keine lokale Desktop-Anzeige oder Chat-Visualisierung vorausgesetzt.

Reale Getter-Sequenz erfolgreich (Name, Zeit, Status, Aufzeichnung, Funk, Alarmgrenzen), sauber getrennt und Hostempfang wieder gestartet. Zusätzlich gelang ein nur lesender Verbindungsversuch nach ausschließlich kurzem STOP. Anschließender Versuch ohne Tastenaktion und mit korrigierter längerer Wartezeit: weiterhin Timeout, Historien unverändert, Hostempfang wieder gestartet. Private Belege: `private/gatt-config-read-report.json`, `private/gatt-config-stop-only-report.json`, `private/unattended-sync-interval-report.json`. Integrierter Leseweg anschließend im installierten Dienst mit acht erfolgreichen Abfragen, neuem prüfsummenverifiziertem Stand und frischem Liveempfang bestätigt (`private/v04-installed-settings-read.json`). Kein Geräteschreibtest; V0.4 ist noch nicht vollständig.

### Änderungsvorschau

88 Python-Tests bestanden: Alt-/Neuwerte, unveränderte Gegenwerte im gemeinsamen Funkblock, keine Dateiänderung durch Vorschau, unveränderte Werte ohne Änderungsschritte, UTF-8-Bytelimit ohne Kürzung, Steuerzeichen, falsche Typen/NaN/Inf und unbekannte Felder, exakte Intervallschritte, ersetzter Beleg und andere Geräte/Firmware, fehlende/ungültige Gegenwerte, API-Auswahl/CSRF/Sperre und weiterhin keine Write-/Apply-/Save-Route. Vorschau startet keinen BLE-Auftrag und pausiert keinen Empfänger. Browserprüfung umfasst zusätzlich erhaltenen Entwurf bei neuem Stand, Sperre bis expliziter Übernahme, ungültig gewordenes Prüfergebnis nach Eingabeänderung, Datenverlusthinweis, Verwerfen verspäteter Antworten nach neuer Eingabe und mobile Darstellung. Aktueller realer Einstellungsbeleg zusätzlich ohne Geräteaktion als unveränderte Vorschau geprüft (`private/v04-settings-preview-local.json`). Vorschau noch nicht im installierten Dienst aktiviert; keine Hardware-Schreibprüfung behauptet.

## V0.4.1-dev: kontrollierter Schreibpfad

99 Python-Tests: echter Parser/CSV-Speicher und gemeinsamer Jobpfad mit simuliertem GATT-Gerät, eine Verbindung pro Vorbereitung/Ausführung, keine Setter in Vorbereitung; erster Vollstand vor Stop und zweiter Vollstand vor Set dauerhaft verifiziert, 25-Minuten-Ziel und erhaltene Einheit/andere Felder, identische Stände ohne Kopie, expliziter Stopp ohne Start, Zwischen-/Endprüfung, feste Save-/Abschlussreihenfolge. Diskfehler vor Stop verhindern jeden verändernden Befehl; Diskfehler nach Stop verhindern Set/Save; Ausfall bei Stop/Set/Save/Abschluss sowie abweichendes Rücklesen führen zu unklarem Zustand ohne erneuten Befehl und mit dauerhaftem Auftragsbeleg. Hostempfang nach jedem Ausgang wiederhergestellt.

Weitere Schutzfälle: aktuelle Advertising-Identität erforderlich, veränderte Einstellungen/Identität/Adapter, Ablauf/Abbruch/ersetzter Beleg, falsche boolesche Bestätigung, verbrauchter Token und Prozessneustart, unbekannte Nichtnullfelder im Aufzeichnungsblock, Wertebereiche/Antwortopcode/Status/Länge, CSRF/Steuersperre und kein Umgehen über `/api/sync`. API bleibt ohne generische Byte-, Reset- oder Start-Schnittstelle.

Browserprüfung mit synthetischer Vorbereitung: Aufzeichnungsintervall in Minuten wird korrekt als Sekunden übertragen; Alt-/Neuwert, geprüfter Vollstand und Folgen sichtbar; Schreiben erst mit beiden Bestätigungen möglich; neue Entwurfseingabe löscht Bestätigungen und sperrt abweichenden Auftrag. Unklarer Schreibzustand wird nicht als Erfolg ausgegeben. Bestehende UI-/Export-/Favicon-/Mobilprüfungen weiterhin bestanden. **Keine reale Geräteänderung ausgeführt.** Aktivierung und erster realer, bewusst bestätigter Hardwaretest stehen aus. Ein erfolgreicher simulierter Save ist kein Nachweis von Firmware-Nebenwirkungen oder Reset-/Restore-Fähigkeit.

## V0.4.2: Hardwareversuch und Zwischenprüfung

Reale integrierte Vorbereitung und bestätigter Schreibversuch in V0.4.1: vollständige Historie/Original-CSV vor Stop und danach geprüft, App-Stopp und Parameterbefehl mit Status 1 beantwortet. Vor-Save-Vergleich abgebrochen; kein Save/Abschluss gesendet. Originalbelege und private Vergleichsberichte belegen anschließenden Zustand App-Stopp, alten Intervallwert und unveränderte übrige Konfiguration. Hostempfang wieder aktuell. Keine erfolgreiche Intervalländerung behauptet. Private Belege: `private/v041-preparation-verified.json`, `private/v041-first-write-journal.json`, `private/v041-postwrite-comparison.json`.

103 Python-Tests: zusätzlicher simuliert verzögerter Setter (Getter bleibt bis Save alt), finales Zurücklesen muss dennoch den neuen Wert liefern; dritter Zwischenwert sperrt Save und bleibt als Originalbeleg erhalten; alter Wert trotz positivem Save-ACK bleibt Fehler; bereits gestopptes Gerät erhält keinen Stop, jedoch weiterhin zwingend Vollauslesung. Vor- und Nach-Commit-Prüfung sind getrennt. Korrigierter Save-/Abschlussweg noch ohne realen Erfolgstest, Dienstaktualisierung erforderlich. Browserprüfung unverändert einschließlich expliziter Bestätigungen und unklarem Ausgang.

## V0.4.3: Parameter gespeichert, Status ohne Details

Realer V0.4.2-Folgetest: vollständige Historie nochmals gesichert, kein erneuter Stop beim bereits gestoppten Gerät; Setter, Save und Abschluss positiv beantwortet. Zwischenbeleg zeigt den alten Wert bis Save. Neue lesende Verbindung nach Abschluss bestätigt den gewünschten Parameter und unveränderte übrige Konfiguration. Statuspayload exakt acht Nullbytes, daher alte Dekodierung noch fehlerhaft; frisches Advertising meldet Initialzustand. Kein automatischer Start, kein Reset. Die gesamten Originalmessdaten bleiben auf dem DeskPi erhalten. Private Belege: `private/v042-write-journal.json`, `private/v042-postsave-comparison.json`, `private/v042-postsave-live.json`.

110 Python-Tests einschließlich Nullstatus ohne erfundenen Aufnahmezustand/Historienspeicher, Ablehnung anderer Varianten, Legacy-Zusammenfassung ohne Dateiänderung, beschädigter Zusammenfassung, konsequenter Trennung von Parametern und Status, rein lesender Nachprüfung vollständiger ACK-/Historienbelege, fehlender ACKs ohne Verbindungsaufbau, beschädigtem Original und weiterhin falschem Zielwert. Nachprüfung eines belegten post-Commit-Originals sendet keine zusätzliche Bluetooth-Anfrage. Browserprüfung zeigt Parametererfolg ohne falsche Stoppaussage und behält ausdrücklich lesende Nachprüfung bei. V0.4.3 anschließend im installierten Dienst geprüft: Auftrag `parameters_verified`, Zielwert stimmt, keine neue Bluetooth-Anfrage, ursprüngliche Schreib-CSV unverändert, keine Lese-/Wiederaufnahmefehler und wieder frischer Advertising-Empfang. Geladene UI-Dateien entsprechen dem aktivierten Quellstand, SVG-/ICO-MIME korrekt. Private Berichte: `private/v043-installed-reconciliation.json`, `private/v043-final-hardware-report.json`.


## V0.4.4: Aufzeichnungsstart

119 Tests und Browserprüfung bestanden. Neue Fälle: nichtleere Historie vollständig vor Start gesichert; Leerstand nur durch eigene zehnbyteige Nullmetadaten, keine leere Messwertserie; laufender Logger, falsche Bestätigungen, Ablauf/Neustart/Abbruch, geänderte Einstellungen/Umfang, beschädigte Belege und Speicherfehler ohne Start. Genau ein Start ohne Stop/Save/Reset; verlorener ACK ohne Wiederholung, anschließend lesende Statusbestätigung. ACK mit Status ohne Details bleibt pending; erst frischer Advertising-Übergang oder Aufnahmestatus 16 bestätigt. API-CSRF/Sperre, kein Umgehen über Sync; Oberfläche verlangt beide Bestätigungen. Realer Dienst aktiviert: nach Timeout gelang die zweite Verbindung samt Einstellungslesen. Historienumfangsantwort Status 3 blockiert Vorbereitung. Keine Auslegung als leerer Speicher, kein Startbefehl. Hostempfang wieder frisch. Privater Bericht `private/v044-recording-status.json`. Hardwarestart weiterhin nicht ausgeführt.


V0.4.5: 9 Aufzeichnungs- und 19 Konfigurationstests bestanden. Zusätzliche Prüfung: unmittelbare Folge Status/Umfang; negativer Status 3 trotz Null-Nutzdaten erzeugt ausschließlich einen Diagnosebeleg und niemals Leerstandsbeweis oder Startfreigabe. Keine erneute Gesamt-/Browserprüfung bei unveränderter Oberfläche.

## V0.4.6

11 Aufzeichnungs- und 9 Einstellungstests bestanden; zusätzlich 15 API-Tests und Chromium-Browserprüfung. Prüft: unbekannter Bestand bleibt unbekannt, explizite Zusatzbestätigung, vorhandene vollständige Alt-CSV erforderlich, andere negative Antwort bleibt gesperrt, genau ein Start, rein lesende Nachprüfung, Speicherzeit bei 25 Minuten und Darstellung der Zusatzbestätigung. Hardwarestart bestätigt: genau ein START-TX mit positiver Antwort, finales Rücklesen bestätigt Aufzeichnungsstatus 16 und unverändertes Intervall. Die vollständige Alt-CSV wurde vor Start erneut geprüft. Keine Uhr-/Resetbefehle.

## V0.4.7

6 Vorschau-, 20 Konfigurations- und 15 API-Tests sowie Chromium-Browserprüfung bestanden. Neue Prüfungen: nur C/F zulässig, fehlender Intervall-Gegenwert blockiert, gemeinsamer Setter ohne Fremdfeldänderung, unbekannte Rohfelder blockiert, vollständiger Schutzablauf archiviert die bisherige Einheit und liest die neue strikt zurück. UI übermittelt die Einheit als Text und erhält das Intervall; Übernehmen setzt den Entwurf korrekt zurück. Keine reale Einheitenänderung ausgeführt.

## V0.4.8

7 Vorschau-, 22 Konfigurations- und 15 API-Tests sowie Chromium-Browserprüfung bestanden. Neue Prüfungen: Temperatur-/Feuchtegrenzen und strikte Bool-Aktivierung, Wertebereich und 0,1-Präzision, vollständiger Gegenblock und Unter-/Obergrenzenrelation; unveränderter °C-Modus für Temperaturalarm. Integrierter Schreibtest prüft beide festen Alarmsetter, Vorab-Historie, unveränderte Typ-/Verzögerungsbytes, unveränderten Aufzeichnungsblock, Save/Abschluss und finales Rücklesen. Fehler am Alarmsetter verhindert Save und Wiederholung; unbekannte Typcodes blockieren. Browser prüft Alarm-Entwurf, Checkbox-Bool, Rücksetzen und Fahrenheit-Sperre. Keine reale Alarmänderung ausgeführt.

## V0.5.0

Chromium-Browserprüfung mit synthetischen Daten bestanden: alle Zeitvorgaben, Zoom-Erhalt, Vor-/Zurücknavigation mit exakter Fensterbreite, CSV-Export ausschließlich der sichtbaren Originalwerte, unveränderte Gesamtabfrage. Zusätzlicher Test mit Europe/Berlin und doppelter Ortszeit am 25.10.2026 bestätigt exakte Navigation; manuelle Eingabe entfernt die interne exakte Zuordnung. Vollbild enthält Export-/Navigationsbedienung und lässt sich verlassen. Bestehende mobile Breitenprüfung, Gerätezeitwarnungen, originale Historienexporte, Live-Follow-Verhalten und Einstellungsabläufe weiterhin bestanden; keine JavaScript-Fehler oder externen Anfragen. Backend-Tests nicht erneut ausgeführt, da API/CSV/BLE unverändert. Keine realen Gerätebefehle.

## V0.5.1

Erweiterte Chromium-Browserprüfung bestanden: Temperatur-/Feuchteachsen mit unabhängigen festen Grenzen, ungültige Grenzreihenfolge ohne Änderung der aktiven Achsen, getrenntes Zurücksetzen, Speicher-/Ladeansicht mit exaktem Zeitbereich, Zoom und ausgeblendeter Kurve. Nach echtem Seitenneuladen bleibt die browserlokale Ansicht verfügbar und stellt Grenzen, Zoom und Kurvenauswahl wieder her. Ungültiger gespeicherter Zoombereich wird abgewiesen. Bestehende Export-, Zeitumstellungs-, Vollbild-, Mobil- und Geräteeinstellungsprüfungen weiterhin bestanden; keine JavaScript-Fehler oder externen Anfragen. Backend-Tests bei unveränderter API/CSV/BLE nicht wiederholt. Keine Geräteänderung.

## V0.6.0

6 Klimatests, 10 Kerntests und 16 API-Tests bestanden. Prüft Referenzwerte, Sättigung an Modellgrenzen, 70-/80-%-Schwellen, fehlende Oberflächenannahme, Kondensationsbedingung, 0 % rF, Ausreißer, Bool-/Text-/NaN-/Riesenwerte und fehlende Felder. Ableitung vor Verdichtung erhält ein Taupunktmaximum, das weder Temperatur- noch Feuchtemaximum ist; ursprüngliches Punktformat, gemeinsame Zeitkoordinaten und Lücken bleiben erhalten. Browserprüfung bestätigt Taupunktkurve, Rechnerwerte, Herkunft, Oberflächenannahme, Verwerfen überholter Antworten und mobile Breite; bestehende Diagramm-/CSV-/Einstellungsprüfungen weiterhin bestanden. Keine Geräteaktion. Synthetische Laufzeitmessung in KLIMA.md dokumentiert.

## V0.6.1

8 Algorithmus- und 17 API-Tests sowie Chromium-Browserprüfung bestanden. Prüft Dauerqualifikation, getrennte Hysterese-/Schwellenzeit, größere Lücken, fehlende Werte, unbelegte Bereichsränder, leere/Einzelwertreihen, strikte Zeitordnung und Offsetnormalisierung. Luftfeuchte bleibt bei ungültigem Temperaturmodell separat auswertbar; Oberfläche nur mit gültiger expliziter Annahme, Kondensationsbedingung wird nicht durch Begrenzen auf 100 % verborgen. Mehr als 100 Phasen behalten vollständige Zähler bei begrenztem Detailumfang. API erhält originale Gerätezeitwarnung und weist ungültige/mehrfache Kriterien zurück. Browser prüft Originalzeitraum, sichtbaren Ausschnitt, Annahme und das Verwerfen überholter Antworten. Bestehende Klima-/Diagramm-/CSV-/Mobil-/Einstellungsprüfungen weiterhin bestanden; keine JavaScript-Fehler oder externen Anfragen. Keine Geräteaktion.

## V0.7.0

7 Statistik- und 18 API-Tests sowie Chromium-Browserprüfung bestanden. Referenzfälle für Min/Max, unterschiedliche Stichproben-/Zeitmittel bei unregelmäßiger Abtastung, Lücken, fehlende Kanäle, Modellgrenzen, 0 % rF, leere/Einzelwertbereiche und nicht abgedeckte Ränder. Zeitordnung, UTC-Offsetnormalisierung und endliche laufende Mittelwerte auch bei großen Eingaben geprüft. API behält ungeprüfte Gerätezeit bei, Original-CSV ist vor/nach Auswertung bytegleich. Browser prüft vier Größen, sichtbaren Ausschnitt, zeilengleichen Originalexport, veraltete Antworten und mobile Tabellenbreite. Bestehende Klima-/Phasen-/Diagramm-/Einstellungsprüfungen weiterhin bestanden; keine JavaScript-Fehler oder externen Anfragen. Screenshotanzahl nun aus tatsächlich erstellten Dateien gezählt. Keine Geräteaktion.

## V0.7.1

Gesamtsuite mit 163 Tests bestanden. Anschließend zusätzlicher Test für unbestätigten Startstatus als Warnung und Ereignisschreibfehler ohne blockierten Auftrag/Scheduler-Callback; alle 11 Ereignistests separat bestanden. Keine erneute Gesamtsuite nach dieser reinen Testergänzung.

Geprüft: persistente Monatsdateien/UTC-Grenzen, Filter, private Rechte, parallele unabhängige Storeinstanzen, eindeutige IDs/ein Header, beschädigte Header/Zeilen/unvollständige Enden ohne Reparatur, unbestätigtes fsync ohne automatische Wiederholung. Receiver-Hooks deduplizieren Fehler, melden Erholung und Frische/Veraltung ohne falschen Verlust bei interner Pause. Speicherkennzeichnung nicht als Leerstand interpretiert; fehlerhafte Ereignisablage lässt primäre Messwerte und Empfangswiederaufnahme weiter zu.

API-Filter/Limit, vollständiger gefilterter Export und unveränderte Originaldatei bestätigt. Chromium prüft Ereignisseite, Filter, Export ohne Anzeige-Limit, Verwerfen veralteter Antworten, Trennung von Messdaten-/Simulationsquelle und mobile Breite. Gesamte bestehende Browserprüfung bestanden; keine JavaScript-Fehler oder externen Anfragen. Alle Ereignis-/BLE-Tests synthetisch, keine neuen Gerätebefehle oder realen Verbindungsversuche.

## V0.7.2

5 Export- und 20 API-Tests sowie Chromium-Browserprüfung bestanden. Prüft Rohwert-/Originalerhalt, Dezimalkomma, Referenz-Taupunkt, Modell-/Statuspflicht, leere Ergebnisse, gültige Nullfeuchte, Modellgrenzen und unzulässige/doppelte Spalten. Gerätezeit/Qualität und zusätzliche bestätigte Zeitzuordnungsfelder können nicht aus dem Auswahl-Export entfernt werden; ungeprüftes Datum bleibt gekennzeichnet. Standard-CSV vor/nach Klimakopie bytegleich.

Browser prüft Originalspaltenauswahl, verpflichtende Zeitspalten, Blob-CSV mit berechneten Feldern, fehlende-Größenauswahl-Sperre, Kontextwechsel und verworfene überholte Vorbereitungen. Zeitfenster des sichtbaren Ausschnitts und Statistikberichts werden exakt übernommen. Mobile Exportseite und bisherige Diagramm-/Statistik-/Ereignis-/Geräteeinstellungsprüfungen bestanden; keine JavaScript-Fehler oder externen Anfragen. Blob-Inhalt direkt gelesen statt durch die unveränderte CSP gesperrten Blob-Fetch zu erzwingen. Keine erneute Gesamtsuite bei unveränderter Empfangs-/Schreibsteuerung.

## V0.8.0

Gesamtsuite mit 179 Tests bestanden, einschließlich 8 neuer Messstellen-Kerntests und geschützter API-Strecke. Geprüft: stabile ID, persistente/private JSON-Datei, Standort-/Loggerwechsel mit geschlossenen kollidierenden Intervallen, exklusive Endgrenze, damalige Namen/Kriterien nach Bearbeitung, Zuordnungsende, unveränderte alte Hostzeilen und korrekte IDs neuer Zeilen. Veraltete Revisionen, doppelte aktive Zuordnung, rückwärts laufende Uhr, fehlerhafter atomarer Schreibabschluss und überlappende/beschädigte Historie werden abgewiesen. API erlaubt keine unbekannten Logger oder Rückdatierung und ruft keine Bluetooth-Steuerung auf.

Chromium bestätigt Anlage/Bearbeitung/Zuordnung, alte Namen in der Historie, Beenden einer Zuordnung, Kriterienübernahme, Erhalt veralteter ungespeicherter Entwürfe und mobile Breite. Gesamte bisherige Browserprüfung bestanden; keine JavaScript-Fehler oder externen Anfragen. Nach Prüfung nur Auswahlbeschriftung um Raum/kurze ID zur Unterscheidung gleichnamiger Messstellen ergänzt; kein erneuter Testlauf für diese reine Beschriftung. Keine reale Messstelle oder Loggerzuordnung angelegt.


## V0.8.1

Gesamtsuite 191 Tests bestanden. Nach den abschließenden Fehler-/Datenschutzkorrekturen alle 12 Konfigurations-Kerntests bestanden. Geprüft: atomare gemeinsame Ablage, private Dateirechte, unveränderte Altdateien/Migration, kein Fallback bei beschädigtem gemeinsamen Stand, alte Einstellungsdateien, Vorschau ohne Schreibzugriff, Tokenablauf/-verbrauch und Revision, Erhalt späterer Loggerwechsel, Metadatenänderung erst bei Übernahme, geschlossene importierte Historie ohne aktive Bindung, Konflikte und reine Einstellungsübernahme. Schreibfehler vor und nach Rename halten den Gesamtstand kohärent und sperren weitere Änderungen; Neustart liest den gültigen sichtbaren Stand. Ereignisdetails enthalten nur Importzähler, keine kopierten Beschreibungen. API prüft CSRF, Dateiformat und fehlende Empfängeraktivierung.

Vollständige Chromium-Prüfung bestanden, 14 lokale Screenshots: kombinierte Datei, Vorschau ohne Speicherung, Abbrechen, Übernahme ohne Messstellen, bearbeitete Formularwerte mit erneuter Vorschau und Übernahme der Messstellen. Bestehende Diagramm-/Statistik-/Export-/Geräteprüfungen einschließlich mobiler Breite weiter erfolgreich; keine JavaScript-Ausnahmen oder externen Anfragen. Alle Tests verwenden temporäre Konfigurationen, keine echten Loggeränderungen oder neuen Messstellen.


## V0.8.2

Gesamtsuite 198 Tests bestanden (6 neue Messstellenfiltertests). Prüft Original-ID plus exklusive Host-Intervallgrenzen, falschen Logger, fehlende/ungültige Messstellen, leere Daten und konsistenten Registrierungssnapshot vor verzögerter Zeileniteration. Metadatenwechsel unterbrechen Grafik, Taupunktkurve, Zeitmittel und Feuchtephasen auch unterhalb der normalen Lückenschwelle; Verdichtung erhält sämtliche Zuordnungsgrenzen. Original-CSV ist bytegleich zur passenden Originalzeilenauswahl, keine interne Segmentspalte oder Änderung der Ausgangsdaten. API prüft denselben Filter für Grafik, Statistik, Feuchtebericht, Original-/Klima-Export und Exportoptionen sowie unveränderten ungefilterten Export und abgewiesene andere Datenquellen.

Vollständige Chromium-Prüfung mit 15 lokalen Screenshots bestanden: Messstellenwahl in mobiler Hostansicht, sichtbare Zuordnungslücke, beschriftete Statistik, unveränderter Original-CSV-Inhalt, korrekt gebundener Statistikexport und Aufheben des Filters mit ungültig gewordener Exportvorbereitung. Bestehende Save/Load-, Diagramm-, Feuchte-, Zeit-, Geräte- und Schutzprüfungen erfolgreich; keine JavaScript-Ausnahmen oder externen Anfragen. Ausschließlich isolierte synthetische Daten, keine echte Zuordnung/BLE-Aktion.


## V0.8.3

206 Tests der Gesamtsuite und vollständige Chromium-Prüfung bestanden. Sieben neue Speicherdiagnose-Kerntests prüfen leeren/gültigen Bestand, unveränderte Originalbytes und Änderungszeit, defekte Kopfzeile, Dateischluss/UTF-8, doppelte Kennungen, falschen Monat, Zeitfolge, nicht endliche Messwerte/ungültige Feuchte, falsches Schema, aktive Schreibsperre, Byte-/Zeilen-/Datei-/Zeitgrenzen, Quellenabgrenzung, symbolische Links und unlesbare Verzeichnisse. Fehler enthalten keine rohen Dateiinhalte. API-Test bestätigt parameterlose Strecke, Hostschutz, Auftragssperre und keine Empfängeraktivierung.

Browser bestätigt sichtbaren Konfigurations-/Ereignisstatus sowie explizite Empfangsdateiprüfung mit vier synthetischen Zeilen ohne Befund in der mobilen Ansicht. Insgesamt 16 lokale Screenshots; bisherige Messstellen-, Einstellungs-, Diagramm-, Statistik-, Export- und Geräteabläufe weiter bestanden, keine JavaScript-Ausnahmen oder externen Anfragen. Tatsächlicher Empfangsbestand anschließend separat rein lesend geprüft, keine Reparatur oder Geräteaktion. Keine neue Dauerlastmessung oder allgemeine Integritätszusage für nicht geprüfte Datenquellen.


## V0.8.4 · gezielte Prüfung

Auf Benutzerwunsch Prüfungen künftig nach Änderungsumfang wählen: bestehende Tests behalten, aber Gesamtsuite und vollständige Browserstrecke nicht bei jedem Versionsschritt ausführen. Notwendige Datenintegritäts- und Sicherheitsprüfungen bleiben verbindlich.

Acht Messstellen-/API-Tests und fünf Exporttests bestanden. Neue Abdeckung: zwei historische Logger gemeinsam chronologisch auswählen, exklusive Wechselgrenze, vollständige Logger-Herkunft ohne Änderung der Ausgangszeilen, keine Verbindung von Kurven/Phasen/Zeitmitteln über Wechsel, Zeitraumeingrenzung/leer vor erster Zuordnung, konsistente Revision, Quellenlimit und Freigabe vorzeitig abgebrochener Leseströme. Gemeinsame API-Strecke prüft Diagramm/Statistik, Original-/Spaltenexport mit verpflichtendem Logger, Exportoptionen und ungültiges `all` ohne Messstelle; bisheriger Einzel-CSV bleibt unverändert.

Gezielter Browserlauf mit zwei synthetischen Loggern bestätigt Standort-/Loggerwechsel, gemeinsamen Verlauf mit Unterbrechung, Statistik, CSV-Provenienz, getrennte gespeicherte Ansicht, mobile Breite und ungültig gewordene Exportvorbereitung nach Filteraufhebung. Wechsel zur Gerätehistorie entfernt den Messstellenfilter. Keine JavaScript-Ausnahmen oder externen Anfragen; ein Screenshot, separater Bericht `test-results/browser-site-continuity.json`. Keine echten Geräte oder Zuordnungen. Python-Gesamtsuite nicht erneut ausgeführt.

```sh
python3 -m unittest discover -s tests -p test_site_selection.py -q
python3 -m unittest discover -s tests -p test_export.py -q
node tools/browser_smoke.mjs --site-continuity
```

Der Browserparameter wählt ausschließlich dieses Szenario im vorhandenen temporären Testaufbau; ohne Parameter bleibt die vollständige Browserstrecke verfügbar.


## V0.8.5 · gezielte Prüfung

29 Python-Prüfungen bestanden: acht neue Warnlogik-/Integrationsprüfungen, neun vorhandene Empfangsprüfungen, elf Ereignisprüfungen und eine neue API-Prüfung. Mindestdauer, Hysterese, einmalige Warnung/Freigabe, unbekannt nach Lücke ohne vorherigen Statusabruf, Timeout ohne Entwarnung, fehlende Messwerte, Pause/Neustart/Hostzeit/Speicherabstand, Zuordnungswechsel, Original-ID und Quellenabgrenzung geprüft. Oberflächen-/Kondensationskanäle verlangen die ausdrückliche Annahme und bleiben unabhängig vom Luftkanal. Fehlgeschlagene Ereignisablage führt nicht zu Wiederholung oder falscher Bestätigung.

Empfängerintegration mit synthetischen Protokollvektoren: nur erfolgreich gespeicherte Zeilen zählen, unterdrückte Zwischenpakete und fehlgeschlagene primäre CSV-Anhänge qualifizieren keine Warnung. Bestehende CSV-Zeilen bleiben erhalten. API liefert Sitzungsstatus ohne Empfängerstart. Keine Gesamtsuite oder vollständige Browserstrecke wiederholt.

Fokussierter Browserlauf prüft echte leere API-Antwort und danach ausschließlich synthetische Anzeigezustände (ausstehende Mindestdauer, Warnung, fehlende Ereignisbestätigung, Oberflächenannahme, unbekannte Lücke und Auswertungsfehler), mobile Breite sowie Trennung von Simulation/Gerätehistorie. Die Anzeigevektoren verändern den Backendzustand nicht und sind kein Hardwaretest. Bericht `test-results/browser-climate-warnings.json`, ein Screenshot.

```sh
python3 -m unittest discover -s tests -p test_climate_warnings.py -q
python3 -m unittest discover -s tests -p test_live.py -q
python3 -m unittest discover -s tests -p test_events.py -q
PYTHONPATH=tests python3 -m unittest test_api.ApiTests.test_live_exposes_session_warning_status_without_starting_receiver -q
node tools/browser_smoke.mjs --climate-warnings
```


## V0.8.6 · gezielte Prüfung

Sechs neue Historien-Diagnosetests und ein API-Test bestanden. Voll-/Deltakette samt Basis, Datei-/Zeilen-/Prüfaufwand, byte- und mtime-unveränderte Originale, manipulierte/fehlende Basisdatei, defektes Manifest, inkonsistente Kettentiefe, Datei-/Byte-/Zeit-/Zeilenlimits, symbolische Pfade, ungültige Kennungen, belegte Ablage und logische Verifizierungsfehler geprüft. Ungeprüfte Gerätezeit bleibt ausdrücklich ungeprüft, rohe Fehlermeldungen werden nicht ausgegeben. API prüft passende Auswahl, Abweisung zusätzlicher/mehrfacher Parameter, gemeinsame Auftragssperre und keine Empfängeraktivierung.

Gezielter Browserlauf gegen echte synthetische Archive: explizit gewählten Stand prüfen, drei Messwerte und unverifizierte Gerätezeit anzeigen, mobile Breite, beschädigten Rohbeleg ohne automatische Reparatur melden, nach Wiederherstellen des Testoriginals erneut erfolgreich prüfen und Aktion ohne Archiv deaktivieren. Ein Screenshot, Bericht `test-results/browser-history-diagnostics.json`; keine JavaScript-Ausnahmen oder externen Anfragen. Keine Gesamt-Test-/Browserstrecke wiederholt. Neuester tatsächlicher DeskPi-Archivstand anschließend separat rein lesend ohne Befund geprüft; kein Hardware-/Uhrtest.

```sh
python3 -m unittest discover -s tests -p test_history_diagnostics.py -q
PYTHONPATH=tests python3 -m unittest test_api.ApiTests.test_history_diagnostics_validates_scope_lock_and_corruption_without_bluetooth -q
node tools/browser_smoke.mjs --history-diagnostics
```


## V0.8.7 · gezielte Prüfung

Fünf neue Strukturdiagnose-Kerntests und ein API-Test bestanden. Geprüft: unveränderte Originalbytes/mtime, normale und absichtlich lückenhafte Testläufe über die Herbst-Zeitumstellung, Quellen-/Datensatzkennung, falsches Zeitraster, nicht endliche Temperatur/ungültige Feuchte, fehlende Zeilen, kaputter Dateischluss, ungültige Manifest-Zeit/JSON, Datei-/Byte-/Zeit-/Zeilengrenzen, symbolische Pfade, unerwarteter Laufinhalt und Pfadmanipulation. Referenz-Prüfsummen bleiben ausdrücklich nicht verfügbar. API prüft Auswahl, Parameterabwehr, gemeinsame Auftragssperre, beschädigte Originale ohne Reparatur und fehlende Empfängeraktivierung.

Fokussierter Browserlauf erzeugt im temporären Testaufbau einen Lückentestlauf und prüft Auswahl, drei vollständig geprüfte Testmessstellen, sichtbare Prüfsummengrenze, mobile Breite und Fehleranzeige bei künstlich beschädigter Test-CSV. Die App repariert nichts; erst das Browserwerkzeug stellt sein Testoriginal wieder her und prüft erneut erfolgreich. Ohne Testlauf ist die Aktion deaktiviert. Ein Screenshot, Bericht `test-results/browser-simulation-diagnostics.json`, keine JavaScript-Ausnahmen oder externen Anfragen. Keine Gesamt-Test-/Browserstrecke wiederholt, keine echten Messdaten berührt.

```sh
python3 -m unittest discover -s tests -p test_simulation_diagnostics.py -q
PYTHONPATH=tests python3 -m unittest test_api.ApiTests.test_simulation_diagnostics_validates_run_scope_lock_and_damage -q
node tools/browser_smoke.mjs --simulation-diagnostics
```


## V0.9.0 · gezielte Performanceprüfung

33 bestehende Prüfungen aus `test_core`, `test_climate`, `test_live` und `test_site_selection` bestanden. Kompakte Spalten erhalten Originalextrema, abgeleitete Kurven, fehlende Werte und Daten-/Messstellenunterbrechungen. Zwölf zusätzliche direkte Vergleiche mit der bisherigen Funktion prüfen verschiedene Grafikbudgets, leere/einzelne Reihen, Nullfeuchte, Modellgrenzen, negative Zeitstempel, Lücken und Zuordnungswechsel; normalisierte JSON-Ausgaben identisch. Nach der abschließenden Erhaltung der JSON-Zahlendarstellung an Modellgrenzen alle sechs Klimaprüfungen erneut bestanden.

`tools/check_background_refresh.mjs` führt den vorhandenen JS-Code ohne DOM-Start, HTTP oder Browser in einer isolierten Node-VM aus: keine Überlappung trotz abgelaufenem Intervall, Sperrfreigabe nach Fehler, unveränderte Zeitsteuerung und Pause bei verborgenem Tab. Vier Ablaufprüfungen bestanden. Keine erneute vollständige Browser-/Python-Suite bei unveränderter Oberfläche.

Million-Zeilen-Benchmark vor/nach Änderung: gleiche künstliche CSV-Prüfsumme und identische normalisierte Diagrammantwort. Nur die tatsächlich geänderte Diagrammfunktion erneut gemessen; Ergebnisse, Methode und verbleibende Engpässe in [PERFORMANCE.md](PERFORMANCE.md). Kein Dauerlast-, HTTP-, BLE- oder SMApi-Nachweis.

```sh
PYTHONPATH=tests python3 -m unittest test_core test_climate test_live test_site_selection -q
node tools/check_background_refresh.mjs
```


## V0.9.1 · gezielte Exportprüfung

Vier neue Vorbereitungstests und 20 gezielte Export-/API-Prüfungen bestanden: bytegleiche CSV einschließlich BOM, Unicode, Anführungszeichen, Semikolon, Zeilenumbruch und Leerwert; exakte Länge, private temporäre Datei, einmaliges Schließen der Quelle vor Übergabe, Bereinigung bei Vorbereitungs-/Verbraucherfehlern sowie Größen-/Platzreserve.

HTTP-Prüfungen bestätigen: Quellenfehler nach erster vorbereiteter Zeile liefert 503/JSON ohne Downloadheader, paralleler CSV-Auftrag 409, anschließender Erfolg mit passender Länge. Künstlicher Übertragungsfehler nach fünf Bytes führt beim Client zu `IncompleteRead`, ohne angehängte Fehler-JSON; Sperre wird wieder frei. Nach Ergänzung der allgemeinen Transfer-Fehlergrenze und des Socket-Timeouts nur diesen Abbruchtest erneut geprüft. Nach Nachführung der Platzreserve nur die vier Vorbereitungstests erneut geprüft.

Bestehende Original-/Klima-/Ereignis-/Zeitzuordnungs-/Statistik-/Live-/Messstellen-Exporte sowie verpflichtende Logger-Herkunft weiter bestanden. Der vorhandene fokussierte Browserablauf `--site-continuity` prüft echte CSV-Antworten im Browser einschließlich Statistikexport und mobiler Auswahl; bestanden, keine JavaScript-Ausnahmen oder externen Anfragen. Danach nur ein erläuternder Hinweis zur 256-MiB-Grenze ergänzt. Keine Gesamt-Test-/Browserstrecke wiederholt.

Million-Zeilen-Vergleich prüft gleiche CSV-Inhaltskennung und Dateilänge bei erheblich geringerem Worker-RSS; Methodik und Grenzen in [PERFORMANCE.md](PERFORMANCE.md). Keine echten Messdaten, System- oder Geräteparameter verändert.

```sh
python3 -m unittest discover -s tests -p test_csv_download.py -q
PYTHONPATH=tests python3 -m unittest test_api.ApiTests.test_csv_preparation_failure_and_concurrency_never_return_partial_success test_api.ApiTests.test_csv_transport_failure_closes_connection_without_appended_error_json test_api.ApiTests.test_selection_and_climate_export_preserve_original_and_unverified_time test_api.ApiTests.test_events_filters_limits_export_and_private_storage test_api.ApiTests.test_time_assignment_export_is_explicit_and_preserves_originals test_api.ApiTests.test_statistics_retains_original_device_time_and_export_bytes test_api.ApiTests.test_real_source_export_is_separate_and_requires_known_logger test_site_selection test_export -q
node tools/browser_smoke.mjs --site-continuity
```


## V0.9.2 · gezielte Betriebsprüfung

Sechs neue Betriebsprüfungen bestanden (6,7 s im ersten Lauf). Tests kopieren nur öffentlichen Code/Webassets und Wrapper in eine temporäre Programmkopie mit Leerzeichen und starten dort isolierte Server mit separaten Datenverzeichnissen. Tatsächliche HTTP-Bereitschaft, CSRF-Einstellungsspeicherung, geordnetes Stoppen/Wiederanlauf, unveränderte Originaldatei und Konfiguration, Status nach Ende, doppelte Instanz und zwei Datenwurzeln geprüft. Der Update-Guard blockiert auch bei einer unbenutzten ausgewählten Datenwurzel, solange eine andere dokumentierte Skriptinstanz derselben Codekopie läuft. Kein git pull/Installer ausgeführt.

Manipulierte PID, Startzeit, Datenpfad, Belegform/-version und ungültiger Fingerabdruck werden ohne Signal abgewiesen. Alte PID-only-Belege bleiben bei verifizierter tatsächlicher Flock-/Skriptzuordnung nutzbar. Ein fremder Python-c-Aufruf mit bloßem app.py-Argument wird nicht als Server akzeptiert. Systemd-MainPID-Zuordnung wird rein simuliert unterschieden; ein normaler portabler Kindprozess im vorhandenen Service-Cgroup bleibt kontrollierbar.

Fehlgeschlagenes Sperrbelegschreiben gibt den Flock sofort frei; private Dateirechte und Symlinkschutz erhalten synthetische Originalbytes. Nach diesen Ergänzungen nur zwei zugehörige Tests wiederholt, nach strikterer Belegformatprüfung nur den betroffenen Identitätstest. Python-/Shellsyntax geprüft. Keine Gesamt-/Browserstrecke wiederholt. Kein tatsächlicher Dienst-/Loggerstopp oder Geräteeingriff. Unerwartete Beendigung/Stromausfall und laufende Hardwareaufträge sind damit nicht abgenommen.

```sh
python3 -m unittest discover -s tests -p test_lifecycle.py -q
bash -n start.sh stop.sh status.sh update.sh
```
