# BT-06 Weblogger

Lokaler Klimamonitor für Linux und Raspberry Pi. **Entwicklungsstand: V0.6.0-dev vorbereitet; V0.5.1 läuft.** Taupunktkurve, absolute Feuchte und ein Oberflächenrechner sind ergänzt. Alle Ableitungen werden als berechnet gekennzeichnet; Gerätezeit, Messlücken und Original-CSV bleiben unverändert. Die Oberflächentemperatur im Rechner ist eine manuelle Annahme. Modellbereich, Formeln und Quellen stehen in [docs/KLIMA.md](docs/KLIMA.md). Zeitabhängige Schimmelbewertung, weitere Gerätefunktionen und V1.0-Abnahme bleiben offen.

Funkparameter, Aufzeichnungsintervall/-einheit, Name, Status, Gerätezeitfelder und Alarmgrenzen wurden am realen BT06 2.05 rein lesend abgefragt. Die neue Oberfläche zeigt nur belegte Werte; die Bedeutung des Funkmoduscodes sowie weitere Parameter bleiben offen. Gezielter Schreibpfad für Name, Sendeleistung/-intervall und Aufzeichnungsintervall implementiert. App-Stopp, Aufzeichnungs-Setter, Save/Abschluss und Rücklesen am realen BT06 geprüft. Nach Save liefert der Logger acht Nullbytes ohne Aufzeichnungsdetails; daraus wird kein aktiver oder gestoppter Aufzeichnungszustand geraten. Frisches Advertising meldet Initialzustand; kein automatischer Aufzeichnungsstart. Manuelle Historie/Nachladen funktionieren; unbeaufsichtigter Zugriff war auch mit längerem Zeitfenster nicht erfolgreich. Die Automatik bleibt ausgeschaltet.

## Start

Python **3.10 oder neuer**, Linux und Zeitzonendaten (`Europe/Berlin`) werden benötigt. Weboberfläche und Testdatengenerator verwenden ausschließlich die Python-Standardbibliothek; Apache ECharts ist lokal enthalten. Keine Cloud und kein Internetzugriff im Betrieb.

```sh
./install.sh
./start.sh
```

Im Browser `http://127.0.0.1:8766/` öffnen. Der Prozess läuft im Vordergrund. Mit `Strg+C` oder aus einer zweiten Shell mit `./stop.sh` beenden; `./status.sh` prüft die laufende Instanz. `./start.sh --port 8767` wählt einen anderen Port. Das Programm bindet ausschließlich an Loopback und benötigt keine Root-Rechte.

## Was funktioniert

- Deutsche responsive Oberfläche, hell/dunkel, Übersicht, Klimaverlauf, Testdaten, Logger/Bluetooth, Einstellungen und Diagnose.
- Echte BT06-Advertising-Empfänge und synthetische Testdaten sind getrennte Datenquellen. Temperatur, relative Feuchte, Batteriespannung, RSSI, Firmware und Aufzeichnungsstatus aus dem verifizierten Format. Kein erfundener Batterie-Prozentwert.
- Bewusst aktivierbarer Empfang mit CSV-Speicherabstand (Standard 60 Sekunden), Datenalter, sichtbaren Schreibfehlern und Wiederaufnahme nach Programmneustart. Der Logger bleibt autonom; kein GATT, Pairing oder Logger-Schreibbefehl für diesen Empfang nötig.
- **Save Settings** speichert Programmeinstellungen atomar und lädt dieselbe JSON-Datei im Browser herunter. **Load Settings** liest eine Datei zunächst zur Prüfung in das Formular; erst Save Settings übernimmt sie. Keine gesonderte Backupfunktion.
- Testdatengenerator: Tagesgang, Feuchtespitzen, Lüftung, Datenlücken; 1–90 Tage, 1–60 Minuten, bis 80.000 Werte je Testmessstelle.
- Jeder Testlauf erhält ein eigenes Verzeichnis. Alle Werte bleiben als Simulation gekennzeichnet. Keine erfundenen Batterie-/RSSI-Werte.
- Interaktiver ECharts-Verlauf mit Temperatur/Feuchte, Tooltip, Zoom, Navigator, Legende, Vollbild, freien Zeiträumen und Schwellenlinien. Lücken bleiben sichtbar. Legendenwahl wird lokal im Browser gespeichert.
- CSV-Download des gewählten Abfragezeitraums in Originalauflösung. Grafikzoom verändert den Exportzeitraum nicht; die freie Zeitraumwahl steuert ihn.
- Historie manuell auslesen: **Logger / Bluetooth → Alles vollständig lesen** verwendet den eingerichteten Live-Logger, pausiert den Hostempfang und stellt ihn danach wieder her. Beim angezeigten Signal START und danach STOP jeweils nur kurz antippen; nicht halten, Handy-App vorher trennen. Keine Kopplung oder Änderung von Loggeruhr/Aufzeichnung.
- Vollständige Historienstände als monatliche Original-CSV mit überprüfter Anzahl/Endemarkierung; identische Wiederholungen erzeugen keine Kopie. Exakte Fortsetzungen erscheinen als ein Verlauf; frühere Einzelstände bleiben erreichbar. Abweichende Reihen bleiben getrennt, weil kein dauerhaft stabiler Geräteindex belegt ist.
- **Neue Werte nachladen** liest bei geeigneter Basis nur einen Zeitbereich mit den letzten 16 gespeicherten Vergleichswerten und neuen Messungen. Anzahl, Grenzen und Rohwerte müssen übereinstimmen; bei Widerspruch bleibt der Bestand erhalten und eine Vollauslesung wird verlangt. Ohne geeignete Basis erfolgt eine Vollauslesung. Manuelles Nachladen startet auf Klick; automatische Versuche sind separat einschaltbar.
- **Geräteeinstellungen lesen** unter Logger / Bluetooth: Name, Aufzeichnungs- und Sendeparameter, Alarmgrenzen sowie ungeprüfte Gerätezeit auslesen. Rohbeleg und Zusammenfassung werden geprüft gespeichert; GET/Anzeigen verbindet nicht mit dem Gerät. Unbekannte Felder werden nicht als SDK-Standardwerte dargestellt.
- **Änderungen vorbereiten → Änderungen prüfen** vergleicht gewünschten Namen, Sendeintervall, Sendeleistung und Aufzeichnungsintervall mit dem gelesenen Stand. Vorschau enthält Alt-/Neuwerte und nötige Schutzschritte; sie sendet keine Gerätebefehle und gibt keinen Schreibauftrag frei. Neue Lesestände ersetzen ungespeicherte Eingaben nicht automatisch. Die Vorschau ist erst nach ausdrücklicher Übernahme des aktuellen Stands wieder möglich. **Vorbereiten: Historie vollständig lesen** liest den aktuellen gesamten Bestand und die Einstellungen. Erst die danach angezeigten konkreten Änderungen und zwei ausdrückliche Bestätigungen erlauben einen Schreibauftrag. Dieser liest vor dem Stoppen und danach nochmals vollständig, speichert dauerhaft, schreibt ausschließlich bekannte Felder, prüft vor dem Commit und liest danach zurück. Aufzeichnung bleibt gestoppt; kein Reset, kein automatischer App-Start, keine automatische Wiederholung oder Rollback. Vorbereitung verfällt nach zehn Minuten und beim Dienstneustart. **Gespeicherte Einstellungen nachprüfen (nur lesen)** bestätigt einen unklaren Auftrag anhand vollständiger ACK-/Historienbelege und strikt passender Werte. Ein bereits geprüfter Original-Lesebeleg nach dem Abschluss kann dafür ohne neue Bluetooth-Kommunikation verwendet werden; andernfalls wird frisch gelesen. Keine Setter werden wiederholt.
- Automatik unter **Logger / Bluetooth → Automatische Synchronisation**: standardmäßig aus, an den eingerichteten Logger gebunden, 15–1440 Minuten Intervall. Versuche benötigen frisches Advertising und aktiven Liveempfang; bei Fehlern längere Wartezeiten. Kein automatischer Vollabruf, keine Kopplung, keine Änderung des Verbindungsmodus.
- **Historische Zeitzone zuordnen** bestätigt nur die Zeitzone eines gewählten Datenstands. Zusätzlicher Export **CSV mit Zeitzuordnung** enthält daraus abgeleitete Kalenderzeiten mit Offset. Originalzeitstempel bleiben leer, Datum bleibt ungeprüft. Spätere Messungen werden nicht ungefragt mit bestätigt; mehrdeutige Zeitumstellungsstunden werden abgewiesen.
- Datenquelle **Loggerhistorie · Gerätezeit**: Verlauf, freie Kalenderbereiche und Original-CSV-Export, ausdrücklich ohne bestätigten UTC-Offset. Keine Verschiebung auf Hostzeit und keine Vermischung mit Liveempfängen.
- Explizite BLE-Gerätesuche, Geräteauswahl und vorübergehende GATT-Verbindungsprüfung. Betriebssystem-Kopplung nur mit eigenem Button/CLI-Option. Keine Logger-Konfigurationsbefehle.

## Bluetooth / Kopplung

Für BLE werden BlueZ und D-Bus sowie passende Benutzerberechtigungen des vorhandenen Systems benötigt. Die Anwendung installiert/ändert keine Systemdienste, Udev-Regeln oder Adapterkonfiguration. Die optionale Python-Abhängigkeit lässt sich ausschließlich im Projekt installieren:

```sh
./install.sh --ble
./start.sh
```

Auf **Logger / Bluetooth** den vorhandenen Adapter auswählen/eintragen (`hci0`, `hci1`, …), Geräte suchen und das Ziel bewusst auswählen. Geräte anderer Hersteller werden ebenfalls angezeigt; Namen bestätigen kein konkretes Modell.

**Verbinden & prüfen** liest die verfügbaren Services und Characteristic-Eigenschaften und beendet die Verbindung anschließend. **Koppeln & prüfen** versucht zuvor ausdrücklich eine BlueZ-Kopplung (`pair=True`). Eine Kopplung kann im Betriebssystem gespeichert bleiben. Falls PIN/Bestätigung nötig ist, wird der systemeigene Bluetooth-Agent benötigt; die Weboberfläche besitzt noch keinen eigenen PIN-Dialog. BT06-Zugangsschlüssel und Betriebssystem-Kopplung sind getrennt.

Alternativ:

```sh
./tools/ble-diagnose.sh scan --seconds 10 --adapter hci0
./tools/ble-diagnose.sh gatt --device <BEWUSST-GEWAEHLTE-ADRESSE> --adapter hci0
# Nur bei ausdrücklich gewünschter Betriebssystem-Kopplung:
./tools/ble-diagnose.sh gatt --device <BEWUSST-GEWAEHLTE-ADRESSE> --adapter hci0 --pair
```

Beim ersten Start gibt es keinen automatischen Scan oder Verbindungsversuch. Ein auf der Loggerseite bewusst aktivierter Advertising-Empfang wird nach einem Programmneustart wieder aufgenommen. „Empfang pausieren“ deaktiviert diese Wiederaufnahme; die Aufzeichnung im Logger bleibt unverändert. Der lokale BT06 wurde per Advertising erkannt und anhand seiner Aufkleberkennung zugeordnet. Nach frühen Timeouts gelangen GATT und vollständige Historienübertragung im kurzen Standard-BLE-Fenster ohne Pairing. Advertising-Empfang benötigt diese Verbindung nicht. Die integrierte manuelle Sync-Strecke ist im installierten Dienst mit Hardware geprüft; automatische Wiederverbindung und Geräteparametrierung bleiben offen. Siehe [Protokollstand](docs/BLE-PROTOKOLL.md).

## Echte BT06-Empfänge

Auf **Logger / Bluetooth** nach Geräten suchen (30 Sekunden). Bei einem BT06 mit verifiziertem 2.05-Format **Liveempfang starten** wählen. Der CSV-Speicherabstand ist unabhängig vom Aufzeichnungsintervall im Gerät: Änderungen daran verändern nur den DeskPi. Vor einer neuen Suche/GATT-Prüfung den Liveempfang pausieren; ein Adapter wird innerhalb der Anwendung nur von einer Aufgabe benutzt.

Unter **Datenquelle → Echte BT06-Empfänge** erscheinen Übersicht und Verlauf. CSV-Dateien liegen unter `data/bt06-<geräte-id>/<UTC-jahr>/<UTC-monat>.csv`. Zeitbasis ist ausdrücklich **Host-Empfang**, da Advertising keine verifizierten Logger-Messzeitstempel liefert. Das ist keine vollständige Loggerhistorie. Ohne Hostempfang entstehen echte Lücken. Der CSV-Export behält die ursprüngliche Empfangsauflösung.

`config/receiver.json` enthält das lokal gewählte Gerät und den bewusst aktivierten Empfangszustand; es wird nicht veröffentlicht. Save/Load Settings betrifft weiterhin die allgemeinen Programmeinstellungen, nicht Loggerparameter.

## Testdaten und private Zigbee-Vorlagen

Ohne Vorlage werden drei vollständig synthetische Klimaprofile verwendet. Ein Lauf kann auch ohne Webserver erzeugt werden:

```sh
python3 app.py generate --days 7 --scenario gaps --seed 42 --end 2026-11-21T12:00:00+01:00
```

Seed, Vorlage, Optionen und Endzeit bestimmen die Messwerte. Neue Laufkennungen verhindern Überschreiben. Simulationen liegen ausschließlich unter `simulation/`, echte Daten sind künftig für `data/` vorgesehen. Alle Laufzeitdaten sind von Git ausgeschlossen.

Für eigene ioBroker-Vorlagen lokal `private/sources.json` als JSON-Liste von ein bis drei Zigbee-Gerätekennungen anlegen. Dann einmal bewusst lesend ausführen:

```sh
python3 tools/capture_templates.py --base http://<IOBROKER-HOST>:<PORT>/v1/ --sources private/sources.json
```

Das Werkzeug fragt Temperatur und Feuchte sowie bis zu sieben Tage Historie ab. Aus gültiger Historie werden Median und Temperaturamplitude ermittelt; ohne Historie dient der aktuelle Zustand als ausdrücklich dokumentierte Ersatzbasis. `private/template-sources.json` dokumentiert Datenbasis und Zustandszeitstempel; `private/profiles.json` enthält nur Generatorparameter. Keine Rohhistorien werden gespeichert. Diese Dateien dürfen nicht veröffentlicht werden. Die generierten Tagesgänge bleiben künstliche Szenarien, keine Wiedergabe der Originalhistorie.

## DeskPi und SMApi

Die Anwendung läuft eigenständig und kann hinter einem vorhandenen Reverse Proxy unter `/klima/` betrieben werden:

```sh
./start.sh --base-path /klima --public-origin http://<DEIN-DASHBOARD-HOST>
```

Der authentifizierende Proxy muss Pfad und Host erhalten. [nginx-Beispiel](docs/nginx-location.conf.example). Kein ungeschütztes LAN-Binding. Die konfigurierte Public Origin muss exakt dem Browserzugriff entsprechen. Ein neuer Port 80 oder zusätzlicher Proxy wird nicht gestartet.

Für einen **headless** betriebenen Pi erfolgt der Browserzugriff über diesen Proxy, beispielsweise `http://deskpi.fritz.box/klima/`, vom Handy oder anderen Rechner aus. `127.0.0.1` bezeichnet immer das Gerät, auf dem der Browser läuft. Mehrere ausdrücklich erlaubte Dashboard-Adressen sind möglich: `--public-origin http://deskpi.fritz.box --public-origin http://deskpi.local`. Für dauerhaften Betrieb kann der vorhandene systemd verwendet werden; der Dienst soll als normaler Benutzer laufen, Loopback beibehalten und beim Start keine Bluetooth-Verbindung öffnen. Beispiel: [systemd-Dienst](docs/bt06-weblogger.service.example). Installation in Systemverzeichnisse nur bewusst und nach Prüfung der Ziel-Mounts.

SMApi ist ein vorgesehenes Linux-Ziel, **dort noch nicht installiert oder getestet**. CPU/RAM und ein möglicherweise mit SBFspot geteilter Bluetooth-Adapter müssen vor Ort geprüft werden. Ein Prozess, koordinierte Schreibvorgänge und begrenzte Testdatenmengen halten den Grundbetrieb überschaubar. Leistungsgrenzen sind in [Architektur](docs/ARCHITEKTUR.md) beschrieben.

## Tests / Updates

```sh
python3 -m unittest discover -s tests -v
node --check web/js/app.js  # optionaler JS-Syntaxcheck, Node nicht für Betrieb nötig
```

`update.sh` verlangt einen beendeten Prozess und einen sauberen Git-Arbeitsstand, verwendet nur `git pull --ff-only` und führt danach die Tests aus. Daten, Simulationen und Konfiguration bleiben erhalten. Keine globalen Paketupdates. Windows bleibt zurückgestellt, bis Linux funktioniert.

Weitere Dokumente: [Architektur](docs/ARCHITEKTUR.md), [CSV](docs/CSV.md), [API](docs/API.md), [Tests](docs/TESTS.md), [Änderungen](CHANGELOG.md), [Roadmap](ROADMAP.md).

## Lizenzen und Referenzen

Apache ECharts 6.0.0 wird unverändert lokal gebündelt; Lizenz, NOTICE und d3-Lizenz liegen in `web/assets/`. [Drittanbieterhinweise](docs/THIRD-PARTY.md). Aus dem TZONE-Android-SDK wurde kein Code übernommen; dessen Wiederverwendungslizenz ist ungeklärt. Private Referenzprojekte wurden nur als Architektur-/Bedienreferenz gelesen und nicht kopiert.


## Vorhandene Historien-Capture-CSV offline importieren

Nur für zuvor eindeutig einem BT06 2.05 zugeordnete Captures mit den Spalten `Hostzeit;Richtung;DatenHex` und vollständigem belegtem Lesetransfer:

```sh
python3 tools/import_history.py /pfad/capture.csv --device-id 12345678 --firmware 2.05
```

Die Kennung im Beispiel ist synthetisch. Das Werkzeug greift nicht auf Bluetooth zu. Es prüft Befehlsfolge, Metadaten, Rahmen und Vollständigkeit erneut und schreibt unter `data/history/`. Original-Capture bleibt unverändert. Unsichere, unvollständige oder fremde Formate werden abgewiesen. Wiederholung ist sicher; nach Fehler vor der Veröffentlichung erneut vollständig importieren. Nicht veröffentlichte `.pending-*` bleiben zur Diagnose erhalten und werden nicht angezeigt.

Für spätere DeskPi-Aktualisierungen genügen `sudo systemctl restart bt06-weblogger.service` in der normalen SSH-Sitzung und anschließend Neuladen von `/klima/`. Keine Paketinstallation oder System-/Mountänderung nötig. Der aktivierte Liveempfang wird beim Start wieder aufgenommen; Historienlesen startet ausschließlich auf Klick.


Bereichs-Captures benötigen beim Offlineimport zusätzlich `--base-snapshot <Inhaltskennung>`. Eine Bereichsabfrage ist kein frischer Nachweis einer vollständigen Geräteauslesung: ältere Teile stammen aus dem bereits gespeicherten Basisstand. Die Oberfläche zeigt empfangene Vergleichswerte und neue Messungen getrennt vom Gesamtbestand. Es erfolgt keine automatische Zusammenführung mit Host-Empfängen und keine automatische UTC-Korrektur.


## V0.3.2: Speicherformat und automatische Versuche

Nachgeladene Werte werden als zusätzliche Monats-CSV-Zeilen mit Verweis auf die geprüfte Basis gespeichert. Spätestens nach 32 Fortsetzungen entsteht ein vollständiger Zwischenstand, um Leseketten zu begrenzen. Alte CSV bleiben erhalten, Originalexport und Verlauf rekonstruieren die gesamte Reihe. Die Manifestversion ist dafür 2; vorhandene Version-1-Stände bleiben lesbar. Neue Stände benötigen zum Lesen V0.3.2 oder neuer.

Die Automatik läuft innerhalb des bestehenden Prozesses, ohne zusätzlichen Systemdienst. Nach bewusster Aktivierung erfolgt der erste Versuch nach Ablauf des Intervalls. Der automatische Verbindungsaufbau wartet etwa neun Sekunden; der ganze Auftrag ist begrenzt. Ein Fehler verdoppelt die Wartezeit bis mindestens zum konfigurierten Intervall bzw. maximal sechs Stunden, falls das Grundintervall kürzer ist. Beim gewählten Tagesintervall bleibt die Wartezeit entsprechend länger. Zustand wird lokal gespeichert, Host-Uhrsprünge lösen im laufenden Prozess keine zusätzlichen Versuche aus.

Im derzeit geprüften BT06-Modus war ohne Tastendruck keine Verbindung möglich. Automatische Versuche ändern das nicht; der Verbindungsmodus muss später bei der kontrollierten Gerätekonfiguration geprüft werden. Nach Fehlversuch läuft der Hostempfang weiter. Automatik bleibt ausgeschaltet, solange sie nicht ausdrücklich gespeichert aktiviert wird.

`config/autosync.json` enthält die bewusste Aktivierung und Gerätebindung, `autosync-state.json` abgeleiteten Versuchszustand, `history-timezones.json` bestätigte historische Zeitzonen. Die allgemeinen Save/Load-Settings-Dateien enthalten weiterhin die bisherigen allgemeinen Programmeinstellungen. Eine umfassendere Einstellungszusammenführung gehört zu V0.8; es gibt keinen gesonderten Backupdienst.


## V0.4: lesende Geräteeinstellungsansicht

**Einstellungen jetzt lesen** verwendet die vorhandene Geräteauswahl und dieselbe Adaptersperre wie Historienlesen. Hostempfang wird kurz pausiert und danach wieder aufgenommen. Das Ergebnis wird unter `data/device-settings/bt06-<id>/` gespeichert: Rohantworten als CSV, geprüfte Einstellungszusammenfassung als JSON. Angezeigter Stand ist die ursprüngliche Abfragezeit, nicht die Zeit eines späteren Imports. Auch teilweise abgewiesene Abfragen werden kenntlich gemacht. Ungültiger/inkonsistenter Rohbeleg wird nicht als verifiziert angezeigt.

Die neue Ansicht sendet ausschließlich belegte Leseabfragen. Änderungen von Uhr, Start/Stop, Zugangsschlüssel, Intervallen oder Speichern sind hier noch nicht möglich. Insbesondere wird aus einem Funkmoduscode noch kein Long-Range-Schalter abgeleitet. Vor einer späteren Geräteänderung müssen konkrete Wirkung, frischer vollständiger Historienabruf und ausdrückliche Zustimmung vorliegen.

Die reale Prüfung zeigte ein langsames Advertising-Intervall. Acht Sekunden Verbindungszeit können deshalb zu kurz sein: ein vorhandener BlueZ-Eintrag erhält bei automatischen Versuchen nun bis zu 35 Sekunden; nach frischer Suche bleibt das kürzere Fenster. Verschwindet ein ungekoppelter Cacheeintrag, wird erneut nach exakt gewählter Adresse, Kennung und Firmware gesucht. Ein Test mit nur kurzem STOP war erfolgreich, ein Versuch ganz ohne Tastenaktion trotz längerem Zeitfenster nicht. Das Problem ist damit nicht allein durch das Sendeintervall erklärt; Automatik nicht als zuverlässig abgenommen.
