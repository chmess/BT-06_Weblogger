# Prüfung · V0.1.0 · 21.11.2026

## Automatisiert

```sh
python3 -m unittest discover -s tests -v
node --check web/js/app.js
node tools/browser_smoke.mjs
python3 tools/benchmark.py
```

17 Python-Tests bestanden: atomare Settings einschließlich simulierter Schreibfehler, Ablehnung ungültiger Einstellungen, Schutz bestehender Dateien, eindeutige Testläufe, reproduzierbare CSV, Monatsgrenzen, wiederholte DST-Stunde, Offsetpflicht, beschädigte Zeilen, Min/Max/Grafiklücken, vollständiger CSV-Export, exklusive Instanz, API-Routen, Favicon-MIME, Basispfad, mehrere explizite Proxy-Origins, Origin/Host/CSRF und Datenisolation. BLE-Unit-Tests verwenden ausschließlich künstliche Geräte: explizites Pairing, Trennung und serialisierte Aufträge, keine Characteristic-Zugriffe.

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
- Noch offen: GATT-Verbindung, Kopplungsbedarf, Firmware, Messwert-/Historienprotokoll, SMApi, ARM32 und weitere Linux-Systeme. Keine Tests mit realem Historienimport oder destruktiven Einstellungen ausgeführt.

## Headless-Installation auf dem DeskPi

Unter `/klima/` hinter dem bestehenden nginx-Login eingerichtet; Dashboard-Kachel meldet den Dienst als erreichbar. Backend-Antworten für die ausdrücklich konfigurierten Host-/IP-Aliase: HTTP 200. Ohne Login liefern nginx-Seite, API und Favicon jeweils HTTP 401 mit dem vorhandenen Dashboard-Realm. Der Benutzer-Dienst ist aktiv und für den Start nach einem Neustart aktiviert. Ein echter Neustart wurde nicht durchgeführt. Der bestehende Dashboard-Dienst und nginx sind ebenfalls aktiv. Ein authentifizierter Zugriff vom anderen Endgerät wurde noch nicht geprüft.

`/etc` und `/usr` sind wieder mit den ursprünglichen Flags `ro,nosuid,nodev,noatime` eingehängt. Der erste Rücksetzversuch ohne Bind-Remount schlug fehl; mit gezieltem Bind-Remount wurden beide Originalzustände wiederhergestellt und außerhalb der Sandbox überprüft. Installationsdateien und ursprüngliche Systemkonfigurationen liegen ausschließlich lokal unter `private/headless-install/`.
