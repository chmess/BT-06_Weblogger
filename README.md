# BT-06 Weblogger

Lokaler Klimamonitor für Linux und Raspberry Pi. **Aktueller Stand: V0.1.0 – Offline-Testbetrieb und BLE-Diagnose.** Noch keine produktive BT06-Messwerterfassung, Historienauslesung oder Schimmelbewertung.

## Start

Python **3.10 oder neuer**, Linux und Zeitzonendaten (`Europe/Berlin`) werden benötigt. Weboberfläche und Testdatengenerator verwenden ausschließlich die Python-Standardbibliothek; Apache ECharts ist lokal enthalten. Keine Cloud und kein Internetzugriff im Betrieb.

```sh
./install.sh
./start.sh
```

Im Browser `http://127.0.0.1:8766/` öffnen. Der Prozess läuft im Vordergrund. Mit `Strg+C` oder aus einer zweiten Shell mit `./stop.sh` beenden; `./status.sh` prüft die laufende Instanz. `./start.sh --port 8767` wählt einen anderen Port. Das Programm bindet ausschließlich an Loopback und benötigt keine Root-Rechte.

## Was funktioniert

- Deutsche responsive Oberfläche, hell/dunkel, Übersicht, Klimaverlauf, Testdaten, Logger/Bluetooth, Einstellungen und Diagnose.
- **Save Settings** speichert Programmeinstellungen atomar und lädt dieselbe JSON-Datei im Browser herunter. **Load Settings** liest eine Datei zunächst zur Prüfung in das Formular; erst Save Settings übernimmt sie. Keine gesonderte Backupfunktion.
- Testdatengenerator: Tagesgang, Feuchtespitzen, Lüftung, Datenlücken; 1–90 Tage, 1–60 Minuten, bis 80.000 Werte je Testmessstelle.
- Jeder Testlauf erhält ein eigenes Verzeichnis. Alle Werte bleiben als Simulation gekennzeichnet. Keine erfundenen Batterie-/RSSI-Werte.
- Interaktiver ECharts-Verlauf mit Temperatur/Feuchte, Tooltip, Zoom, Navigator, Legende, Vollbild, freien Zeiträumen und Schwellenlinien. Lücken bleiben sichtbar. Legendenwahl wird lokal im Browser gespeichert.
- CSV-Download des gewählten Abfragezeitraums in Originalauflösung. Grafikzoom verändert den Exportzeitraum nicht; die freie Zeitraumwahl steuert ihn.
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

Beim Start gibt es keinen automatischen Scan oder Verbindungsversuch. Der lokale BT06 wurde per Advertising erkannt und anhand seiner Aufkleberkennung zugeordnet. Zwei GATT-Verbindungsprüfungen endeten mit Timeout; eine Kopplung wurde nicht versucht. GATT und Kopplung sind damit noch nicht an echter Hardware abgenommen. Gerätefunktionen, UUIDs und Bytebefehle bleiben bis zur Verifikation offen; siehe [Protokollstand](docs/BLE-PROTOKOLL.md).

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
