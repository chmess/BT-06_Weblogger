# Architektur · V0.3.0-dev

## Laufzeit

Ein Python-Prozess mit Standardbibliotheks-HTTP-Server auf `127.0.0.1`. Die Architektur ist für die lokale Anwendung bzw. einen vorgeschalteten authentifizierenden nginx gedacht. Kein eigener LAN-Server in dieser Version. Ein Linux-flock schützt den Programm-/Datenordner vor gleichzeitigem Server- und CLI-Schreibbetrieb. Keine zusätzlichen Hilfsdienste.

- `backend/common/settings.py`: Schema-Prüfung, atomare JSON-Ersetzung, fsync.
- `backend/common/simulation.py`: reproduzierbarer Testdatengenerator, getrennte Laufverzeichnisse.
- `backend/common/storage.py`: CSV-Codec, Zeitraumfilter, Grafikverdichtung.
- `backend/linux/runtime.py`: exklusive Prozesssperre.
- `backend/linux/ble_diagnose.py`: explizite BLE-Suche und GATT-Inventar, optionale Betriebssystem-Kopplung.
- `backend/linux/ble_jobs.py`: ein BLE-Auftrag gleichzeitig, Fortschritt über Statusabfrage.
- `backend/server.py`: feste Routen, Host-/Origin-Prüfung, CSRF-Schutz für POST.
- `web/`: lokal gebündelte Oberfläche ohne CDN-Zugriffe.

BLE-Aufträge erstellen ihre Bleak-Objekte vollständig im selben Eventloop. Es gibt kein automatisches Pairing. Characteristic-Leseabfragen und Notifications erfolgen nur beim ausdrücklich gestarteten Historienauftrag. Advertising-Empfang beginnt nur nach bewusster Aktivierung; dieser Zustand wird für Neustarts gespeichert. Bei BlueZ-Ausfall versucht der Empfänger begrenzt verzögert erneut zu scannen. Eine gemeinsame Adaptersperre schließt parallele Diagnose-/Empfangsaufgaben aus. Ein erfolgreicher GATT-Test bestätigt keine Messwerterfassung. Die Diagnoseverbindung wird anschließend geschlossen. Die Website startet keine Shellbefehle.

## Dateien

Alle Laufzeitpfade relativ zum Programmordner, alternativ `python3 app.py --root /anderer/ordner serve`. Assets bleiben beim Quellcode. `status.sh` und `stop.sh` verwalten den Standardordner; bei eigenem Root den gestarteten Vordergrundprozess mit Strg+C beenden.

`config/settings.json`: Programmeinstellungen, `private/`: nur lokale Klimavorlagen und Herkunft, `simulation/<run>/<logger>/<UTC-jahr>/<UTC-monat>.csv`: Testwerte, `runtime/app.lock`: Prozesssperre. V0.2 speichert Host-Empfänge getrennt unter `data/` als CSV-Schema 2. Ein koordinierter Schreiber mit Dateisperre bestätigt erst nach fsync. Beschädigte Endzeilen blockieren weitere Anhänge und bleiben erhalten. Loggerhistorien werden in der Entwicklungsfassung auf ausdrücklichen Auftrag getrennt ausgelesen. Kein gesondertes Backupverzeichnis oder Backupdienst.

Der Testdatengenerator schreibt zunächst in ein verstecktes Staging-Verzeichnis. Sichtbar wird der Lauf erst nach vollständigen CSV-Dateien und Manifest per atomarer Umbenennung. Abgebrochene Staging-Läufe bleiben für Diagnose erhalten, werden aber nicht als vollständige Läufe angeboten. Einstellungen werden separat atomar geschrieben. Für einen späteren produktiven Historienimport sind weitergehende Recovery-/Dedupe-Mechanismen erforderlich; V0.1 behauptet deren Fertigstellung nicht.

## Performance

Testgenerator: höchstens drei Profile, je höchstens 80.000 Messwerte. Gleichzeitige Generatoraufträge werden abgewiesen. Zeitraumabfragen öffnen nur passende UTC-Monatsdateien. Die V0.1-Diagrammabfrage materialisiert den gewählten Bereich im Speicher; der Eingabebestand ist entsprechend begrenzt. Pro Bucket werden Min/Max beider Kurven erhalten, zusätzlich Lückenränder. Diagramme rendert der Browser. CSV-Export verwendet Originalzeilen und wird derzeit im Speicher erzeugt.

Vor Millionen realer Werte: Streaming-Exporte, Zeitindizes und Statistikkacheln ergänzen. Noch keine Zusage für solche Datenmengen oder den Parallelbetrieb mit SBFspot. Der optionale Betrieb auf SMApi benötigt dortige CPU/RAM-/BLE-Messungen. Keine Änderungen an produktiven Solar-/Zählerdiensten vornehmen.

## Schutz

Host-Freigabe gegen DNS-Rebinding, explizite Public Origin für Reverse Proxy, zufälliges Sitzungstoken und gleiche Origin für POST. Nur feste statische Assets erreichbar; kein generischer Dateibrowser. JSON auf 16 KiB begrenzt, Generatoroptionen und Kennungen validiert. Keine CORS-Freigabe. Simulationsdaten, Vorlagen, Logs und Einstellungen sind in `.gitignore`. Kein BLE-Zugangsschlüssel in Settings.

Mehrere Public Origins werden über wiederholtes `--public-origin` ausdrücklich freigegeben, z. B. Hostname und private AP-Adresse eines headless Pi. Es gibt keine pauschale Freigabe beliebiger Host-/Origin-Header.

Die Standardbibliothekslösung ist kein ungeschützter Internetserver. Für DeskPi die vorhandene Authentifizierung/Firewall verwenden. nginx darf `/klima/` nur im bereits geschützten Dashboard bereitstellen. Systemdateien werden vom Projekt weder installiert noch verändert.

## Referenzen / Abgrenzung

Lokale ESPA-Monitor-Dokumentation: Start im Benutzerkontext, Browseroberfläche, bewusster Verbindungsaufbau. Growbox-S3-Dokumentation: kompakte Status-/Konfigurations-/Diagnosebereiche. Keine Übernahme privaten Quellcodes. Windows wird erst nach funktionierendem Linux geplant.

## V0.2-Module

`common/bt06.py` dekodiert ausschließlich das belegte 2.05-Advertising-Format. `common/live_store.py` speichert lokale Host-Empfänge ohne erfundene Gerätezeit/Prozentbatterie. `linux/receiver.py` prüft Adresse **und** stabile Gerätekennung, aktualisiert den momentanen Empfang bei jedem Paket und schreibt höchstens nach Ablauf des gewählten CSV-Abstands. Andere Geräte und unbekannte Firmwareformate werden nicht als bestätigte Messung übernommen.

Der UI-Bestand wird beim Prozessstart in den Arbeitsspeicher gelesen, damit laufende Prozesse bei einem Quellcodeupdate keine neue UI mit alter API mischen. Der Dienst muss für eine neue Version geordnet neu gestartet werden.


## V0.3-Entwicklungsstand

`common/history_capture.py` prüft die erlaubte Lesebefehlsfolge aus Capture-CSV; `common/history_protocol.py` prüft den vollständigen Stream. `common/history_store.py` veröffentlicht unveränderliche, nach Inhalt deduplizierte CSV-Stände mit Dateiprüfsummen. `.pending-*` bleibt nach Fehler zur Diagnose erhalten und ist unsichtbar für die Abfrage. Das separate Offlinewerkzeug darf parallel zum Server importieren, weil es dieselbe Import-Dateisperre verwendet; es schreibt keine Live-CSV und greift nicht auf BLE zu.

`linux/history_reader.py` nutzt den bereits von BlueZ bestätigten Geräteeintrag am ausgewählten Adapter. So wartet die Verbindung schon vor dem kurzen Tastenfenster auf den Logger. Keine geratenen DBus-Pfade, UUIDs oder Gerätebefehle. `linux/history_jobs.py` steuert genau einen manuellen Auftrag. Alle BLE-Steuerungs-POSTs sind serialisiert; andere Aufträge bleiben während Sync gesperrt. Der Empfangswunsch bleibt für Neustart erhalten, auch wenn der Hostempfang gerade pausiert ist. Ein Abbruch bestätigt keinen unvollständigen Import.

Das Frontend behandelt Hostempfang, Gerätekalender und Simulation als getrennte Quellen. Die Gerätezeit ist ausdrücklich ungeprüft; Kalenderkoordinaten des Charts erhalten keine automatische UTC-Korrektur. Die integrierte manuelle Strecke ist im installierten Dienst am realen BT06 erfolgreich geprüft. Zusammengeführte Langzeithistorie und automatischer Sync bleiben offen. Dienst und UI werden erst durch geordneten Neustart gemeinsam aktualisiert.
