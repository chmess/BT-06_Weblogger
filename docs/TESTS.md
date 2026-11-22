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
