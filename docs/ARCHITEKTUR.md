# Architektur · V0.4.4-dev

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


## V0.3.1: Nachladen und Verlaufsindex

`HistoryStore.series()` rekonstruiert Präfixbeziehungen aus den geordneten Rohzeiten/Rohwerten und deren Inhaltskennung. Genau enthaltene frühere Stände werden im Hauptverlauf zusammengefasst, Originalarchive bleiben unverändert. Cache ist ausschließlich im Arbeitsspeicher und wird bei geänderten Manifest-/Dateistatistiken verworfen; gewählte CSV werden weiterhin anhand ihrer Prüfsummen gelesen. Mehrdeutige Reihen verhindern automatische Basiswahl.

Der manuelle Nachladeauftrag verwendet dieselbe Adaptersperre und Wiederaufnahme wie die Vollauslesung. Erst passende Gesamtmetadaten erlauben die Bereichsabfrage; vor Veröffentlichung werden Basis, 16 überlappende Messungen, Grenzen und Anzahl nochmals geprüft. Abbruch/Widerspruch ändert bestehende Daten nicht. Teilbereichsherkunft wird ausdrücklich dokumentiert und gilt nicht als neuer Vollabruf. Noch kein automatischer Zeitplan oder separater Hintergrunddienst. Die Gesamt-CSV-Stände bleiben vollständig; Archivspeicheroptimierung ist nicht Teil dieses Schritts.


## V0.3.2: Automatik und Zeitzonenzuordnung

`linux/auto_sync.py` hält einen abschaltbaren Zeitplan im vorhandenen Prozess. Ein wartender Thread nutzt dieselbe Steuersperre und dieselben HistoryJobs wie manuelle Aktionen; kein Systemdienst oder Cronjob zusätzlich. Gerät, Adapter und Firmware sind an die explizite Aktivierung gebunden. Monotone Zeit steuert laufende Fristen; UTC-Fristen und Fehlerzahl ermöglichen konservatives Fortsetzen nach Neustart. Aufträge verwenden kurze Verbindungslimits und dürfen nicht automatisch auf Vollabruf wechseln. Abschalten verhindert Folgeaufträge, Änderungen am Logger erfolgen nicht.

`common/history_timezones.py` speichert ausschließlich bestätigte historische Zeitzonenzuordnungen, ohne Geräteuhränderung und ohne Originaldateien zu ändern. Bestätigung wird durch Rohpräfixvergleich begrenzt. Zeitzone und Datum sind getrennte Aussagen: selbst eine bestätigte Zeitzone setzt `clock_verified` oder `date_verified` nicht auf wahr. Ein zusätzlicher Export enthält abgeleitete Kalenderzeiten mit dieser Kennzeichnung.

Historienfortsetzungen speichern nur neue CSV-Zeilen; ein vollständiger Zwischenstand begrenzt die Basisverkettung. Die Verlaufszuordnung arbeitet vom längsten Stand aus und erkennt Präfixe beim einmaligen Durchlauf, statt jede ältere Gesamtserie vollständig erneut zu lesen. Regenerierbarer Cache bleibt im Arbeitsspeicher. Keine Datenbank, keine Löschung alter Originale und kein zusätzlicher Backupmechanismus.


## V0.4: lesende Geräteeinstellungen

`common/device_settings.py` dekodiert unabhängig die belegten 2.05-Einstellungsantworten und prüft gespeicherte Rohbelege. `linux/settings_reader.py` nutzt eine feste Liste reiner Getter, ohne generischen Byte-Schreibzugriff. HistoryJobs serialisiert diesen Modus mit Historie/Automatik und stellt den gespeicherten Hostempfangswunsch nach jedem Ausgang wieder her. Keine Historien-CSV wird aus Einstellungsantworten erzeugt.

Die Hauptansicht bleibt bei einem beschädigten optionalen Einstellungsbeleg nutzbar; der Fehler wird im Einstellungsbereich angezeigt. UI-Felder kommen aus dekodierten Antworten, nicht aus Defaultwerten der Herstellerbibliothek. Noch keine Schreibfunktion, kein implizites Unlock, Start/Stop oder Konfigurations-Commit. Ein bestätigtes Get ist kein Beleg für die Nebenwirkungsfreiheit eines späteren Set/Save.

`common/settings_preview.py` vergleicht einen Entwurf rein lokal mit einem erneut geprüften Originalbeleg. Die Steuersperre serialisiert Auswahl und Vorschau mit manuellen/automatischen Aufträgen. Eine Capture-Kennung bindet die Vorschau an genau die aktuelle Auslesung; kein Vorschautoken berechtigt zum Schreiben. Erlaubt sind zunächst Name und die vollständig bekannten gemeinsamen Funkparameter. Unbearbeitete Gegenwerte werden nicht durch Defaults ersetzt. Keine BLE-Imports oder Persistenz im Vorschau-Modul; bestehende Einstellungs-/Historienbelege bleiben unverändert. Die UI erhält einen bearbeiteten Entwurf bei neuer Auslesung, verwirft aber sein Prüfergebnis und verlangt Übernahme des neuen Stands. Geänderte Eingaben verwerfen ebenfalls das vorherige Ergebnis; verspätete Antworten werden nicht als aktuelle Vorschau angezeigt.

## V0.4.1: gezielte Konfiguration

`linux/configuration.py` nutzt interne HistoryJobs-Aufträge; HTTP-`/sync` erlaubt diese Modi nicht. Vorbereitung und Ausführung sind getrennt, beide belegen dieselbe BLE-/Steuersperre wie Historie und Automatik. `retrieve` und `retrieve_settings` können eine bereits verifizierte Verbindung nutzen; sie öffnen oder schließen diese dann nicht selbst. Konfigurationsverbindungen prüfen zusätzlich die aktuellen Manufacturer-Daten auf ausgewählte Kennung/Firmware, bevor irgendein GATT-Auftrag gesendet wird.

Vorbereitung liest alle unterstützten Getter und die gesamte Historie in einer Verbindung, prüft gegen den bisherigen Einstellungsbeleg und speichert Originale. Eine Vorbereitung lebt maximal zehn Minuten im Arbeitsspeicher und ist an Adresse, Kennung, Adapter, Firmware und Einstellungsbeleg gebunden. Sie enthält konkrete Änderungen und Folgen. Weder Neustart noch eine alte identische CSV verleihen Schreibrechte. Die UI verlangt zwei explizite Bestätigungen und verwirft diese bei Entwurfsänderung. Der Token gilt einmalig, auch bei gescheitertem Start.

Ausführung liest aktuelle Einstellungen und Historie erneut vollständig. Erst dauerhaft gespeicherte, geprüfte Originale erlauben einen bestätigten Stopp. Danach nochmals Vollauslesung, um letzte Werte vor dem Stopp zu erhalten; keine Range-Herkunft als Ersatz. Unbekannte Nichtnullfelder im Aufzeichnungsblock werden blockiert. Gestoppten Zustand erneut prüfen, feste Setter aus `settings_commands.py`, alle Werte vor Save prüfen/speichern, belegtes Save plus Abschluss, danach alle Werte erneut lesen und mit den erwarteten Rohblöcken vergleichen. Kein Reset, Uhrsetzen, Zugangsschlüssel, geratenes Funkmodus-Mapping oder Aufzeichnungsstart.

`data/device-settings/changes/` enthält Auftrags-JSON und Original-Schreibverkehr als CSV, keine Kopie der Messdaten: Historien-/Einstellungsbelege werden referenziert. Vor jedem möglicherweise wirksamen Befehl werden Absicht und Rohframe fsync-gesichert. Unvollständiger ACK/Timeout/Abbruch nach möglichem Schreibbeginn gilt als unklar; kein Retry, Rollback oder automatischer Aufzeichnungsstart. `latest.json` macht den letzten Zustand nach einem Prozessabbruch sichtbar. Temporäre Vorbereitungen verfallen; laufende Änderungen werden nicht automatisch fortgesetzt. Die getrennte Historien-/Livezeitbasis bleibt unverändert.

V0.4.2 trennt die Prüfung vor und nach Commit: vor Save dürfen ausschließlich tatsächlich geänderte Blöcke noch exakt den Ausgangswert oder bereits den Zielwert zeigen. Eine dritte Variante, veränderte Gegenbytes oder Änderungen anderer Blöcke blockieren weiterhin. Der Zwischenbeleg wird vor dem Vergleich gespeichert und bleibt bei Abweichung erhalten. Nach Save/Abschluss gilt weiterhin der exakte Zielblock, einschließlich unveränderter Gegenwerte. Die Auftragsbelege referenzieren Stopp-/Zwischenantworten und die Sichtbarkeit vor Commit. Ein Gerät, das bereits im zulässigen Stoppzustand ist, erhält keinen erneuten Stop-Befehl; sein aktueller Gesamtbestand wird dennoch vollständig gesichert.

V0.4.3 erkennt die reale achtbyteige Null-Statusantwort ohne ein Aufnahmeflag zu erfinden. Nach Commit können Parameter vollständig verifiziert sein, während Statusdetails fehlen; eigener Ergebnis-/Auftragsstatus verhindert die irreführende Behauptung „gestoppt“. Vor neuen Änderungen bleibt der unbekannte Aufnahmezustand gesperrt. Originalantworten werden nach Commit vor jeder inhaltlichen Prüfung gespeichert.

Eine getrennte, strikt lesende Nachprüfung rekonstruiert die erwartete Befehlsfolge aus unverändertem Zwischenbeleg und ursprünglichen Zielwerten, prüft jede positive Antwort sowie die referenzierten vollständigen Historien. Ein neuerer originaler Einstellungsbeleg nach Abschluss kann bei strikter Übereinstimmung ohne BLE genutzt werden; andernfalls nur Getter über neue Verbindung. Sie ergänzt ausschließlich den bestehenden Auftragsbeleg und ändert weder ursprüngliche Schreib-CSV noch Messdaten. Keine Wiederholung mutierender Befehle. Der Zeitpunkt der bestätigten Originalbeobachtung bleibt sichtbar. Dekoderversion 2 kann alte abgeleitete Nullstatus-Zusammenfassungen anhand ihrer unveränderten CSV im Speicher aktualisieren, ohne einen schreibenden GET einzuführen.
