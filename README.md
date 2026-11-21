# BT-06 Weblogger

Lokaler Klimamonitor für Linux und Raspberry Pi. **Entwicklungsstand: V0.3.0-dev – manuelles Historienlesen und getrennte Historienansicht für BT06 2.05.** Auf dem DeskPi läuft bis zum nächsten Dienstneustart weiterhin V0.2.

Vollständiger Historientransfer am realen BT06 und Import der gesicherten Originaldaten sind geprüft. Die neue integrierte BLE-/API-Strecke wurde automatisiert mit simuliertem BLE geprüft; ihre Geräteabnahme im Dienst steht noch aus. Automatischer Sync, zusammengeführte Langzeithistorie und verifizierte Zeitzuordnung sind noch offen. Details: [BLE-Protokoll](docs/BLE-PROTOKOLL.md).

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
- Historie manuell auslesen: **Logger / Bluetooth → Historie jetzt lesen** verwendet den eingerichteten Live-Logger, pausiert den Hostempfang und stellt ihn danach wieder her. Beim angezeigten Signal START und danach STOP jeweils nur kurz antippen; nicht halten, Handy-App vorher trennen. Keine Kopplung oder Änderung von Loggeruhr/Aufzeichnung.
- Vollständige Historienstände als monatliche Original-CSV mit überprüfter Anzahl/Endemarkierung; identische Wiederholungen erzeugen keine Kopie. Veränderte oder überlappende Stände bleiben getrennt, weil kein dauerhaft stabiler Geräteindex belegt ist.
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

Beim ersten Start gibt es keinen automatischen Scan oder Verbindungsversuch. Ein auf der Loggerseite bewusst aktivierter Advertising-Empfang wird nach einem Programmneustart wieder aufgenommen. „Empfang pausieren“ deaktiviert diese Wiederaufnahme; die Aufzeichnung im Logger bleibt unverändert. Der lokale BT06 wurde per Advertising erkannt und anhand seiner Aufkleberkennung zugeordnet. Nach frühen Timeouts gelangen GATT und vollständige Historienübertragung im kurzen Standard-BLE-Fenster ohne Pairing. Advertising-Empfang benötigt diese Verbindung nicht. Die neue integrierte manuelle Sync-Strecke muss nach Aktivierung im Dienst noch mit Hardware abgenommen werden; automatische Wiederverbindung und Geräteparametrierung bleiben offen. Siehe [Protokollstand](docs/BLE-PROTOKOLL.md).

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

Für die vorbereitete DeskPi-Aktualisierung genügen `sudo systemctl restart bt06-weblogger.service` in der normalen SSH-Sitzung und anschließend Neuladen von `/klima/`. Keine Paketinstallation oder System-/Mountänderung nötig. Der aktivierte Liveempfang wird beim Start wieder aufgenommen; Historienlesen startet ausschließlich auf Klick.
