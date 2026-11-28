# Betrieb und Wiederanlauf · V0.9.3

Linux ist die führende Version. Die folgenden portablen Befehle benötigen keine Systeminstallation oder Administratorrechte. Die aktive Systemd-Installation auf dem DeskPi bleibt getrennt zu verwalten. Windows und eine SMApi-Installation sind weiterhin zurückgestellt.

## Portabler Vordergrundbetrieb

```sh
./start.sh --port 8766
./status.sh
./stop.sh
```

Start läuft im Vordergrund; Strg+C bleibt möglich. Status meldet den nachgewiesenen Prozess bzw. eine freie Instanzsperre, nicht die HTTP-/BLE-Funktionsfähigkeit. Ohne anderen Pfad liegen Daten und Konfiguration im Programmverzeichnis. Loopback-Bindung bleibt erhalten; eine 127.0.0.1-Adresse des DeskPi ist nicht automatisch im Browser des SSH-Clients erreichbar. Für den bestehenden LAN-Zugang weiterhin die eingerichtete Proxy-Adresse verwenden.

## Separates Datenverzeichnis

```sh
./start.sh --root "/absoluter/pfad/BT06 Daten" --port 8767
./status.sh --root "/absoluter/pfad/BT06 Daten"
./stop.sh --root "/absoluter/pfad/BT06 Daten"
```

Alle drei Aufrufe müssen dieselbe Datenwurzel meinen. Die Shellskripte wechseln ins Programmverzeichnis; bei relativen Pfaden ist das ihre Bezugsbasis. Absolute Pfade vermeiden Verwechslungen. `app.py --root <pfad> serve` und `app.py serve --root <pfad>` bleiben beide möglich, ebenso beim Generator-Unterbefehl.

Die Datenwurzel enthält Konfiguration, runtime, Messdaten, Ereignisse und Simulation; Webassets/Quellcode bleiben beim Programm. Ohne vorhandene Empfangs-/Autosync-Aktivierung beginnen neue Verzeichnisse offline. Getrennte Datenverzeichnisse sind keine Isolation oder Freigabe für parallele Bluetooth-Nutzung desselben Adapters.

## Prozessidentität und Stoppen

Die Linux-Instanzsperre gilt pro Datenverzeichnis. Die private Datei `runtime/app.lock` enthält Schema 2, PID, Prozessstart-Ticks, Programm-/Datenpfad und Modus. Die Datei ist 600, symbolische Sperrdateien werden abgewiesen. Misslingt ein Belegschreiben, wird der gehaltene Flock sofort durch Schließen freigegeben. Ein alter ungesperrter Beleg verhindert keinen Neustart. Der Beleg ist Laufzeitmetadatum, keine Sicherung oder Messdatenquelle.

Status/Stop gleichen PID und tatsächlich im Kernel gehaltenen Flock sowie Python-Skriptpfad und Datenverzeichnis ab. Neue Belege müssen zusätzlich zum Startzeit-/Pfad-/Modusfingerabdruck passen. Ein alter reiner PID-Beleg wird nur mit diesen übrigen Nachweisen akzeptiert. Bloßer Skriptname in `python -c`-Argumenten reicht nicht. Bei unbekannter Belegform, widersprüchlichen Angaben oder nicht prüfbarer Identität kein Signal.

Stop sendet ausschließlich SIGTERM über den geöffneten pidfd an den identifizierten Server und wartet höchstens zehn Sekunden auf sein Ende. Kein SIGKILL, keine PID-Raterei, kein automatischer Abbruch einer Generator-CLI. Benötigt Linux-/proc, Kernel-Flock und pidfd-Unterstützung. Ungewöhnliche/unbekannte Python-Aufrufvarianten werden sicherheitshalber nicht als nachgewiesener Server akzeptiert; die dokumentierten Startskripte verwenden die unterstützte Form.

## Systemd auf dem DeskPi

Der bestehende rootverwaltete Dienst wird aus der normalen SSH-Sitzung über systemctl bedient, z. B. für eine ausdrücklich gewünschte Aktivierung:

```sh
sudo systemctl restart bt06-weblogger.service
```

`stop.sh` signalisiert keinen als Systemd-MainPID nachgewiesenen Dienst. Es unterscheidet diesen von einem portablen Kindprozess innerhalb einer anderen Service-Cgroup. Die MainPID-Abfrage ist rein lesend; wenn eine relevante Dienstzuordnung nicht prüfbar ist, wird nicht signalisiert. Kein Ändern von Units, Mounts oder Systemdateien durch die portablen Steuerbefehle.

## Update

Das vorhandene `update.sh` prüft vor `git pull --ff-only` weiterhin sauberen Git-Stand und gestoppte Instanzen. Seit V0.9.2 berücksichtigt die Vorprüfung sichtbare eigene Python-Skriptinstanzen des betreffenden Programmverzeichnisses auch bei anderen Datenwurzeln. Zusätzlich darf die Standard-Datensperre nicht belegt sein. Diese Prozesssicht ersetzt keine systemweite Prüfung fremder Benutzer oder beliebiger Python-Modul-/Sonderaufrufe.

Während des Updates keine neue Instanz starten; die Vorprüfung ist eine Momentaufnahme, keine atomare Sperre über den gesamten Updateablauf. Systemd-Dienst vorher regulär stoppen, danach bewusst wieder starten. Das Skript startet/stoppt den Dienst nicht selbst. Seine vollständige Testsuite bleibt für einen möglicherweise umfangreichen Versionssprung sinnvoll; laufende Entwicklung verwendet gezielte Prüfungen. Kein Update wurde in dieser Abnahme ausgeführt.

## Nachweisstand

Sechs isolierte Betriebsprüfungen verwenden ausschließlich eine temporäre Kopie des veröffentlichten Codes/Webverzeichnisses, neue Datenpfade und synthetische Originaldateien. Geordnetes Stoppen/Wiederanlauf erhält Originalbytes und gespeicherte Programmeinstellungen. Zwei Datenwurzeln werden korrekt zugeordnet, doppelte Instanzen blockiert, manipulierte Belege nicht signalisiert und Fehler-/Symlinkfälle erhalten vorhandene Testdaten.

Der echte Dienst wurde für V0.9.3 nur auf V0.9.2/Fehlerstatus gelesen, nicht für die Tests angehalten; kein Bluetooth-/Gerätebefehl. Zusätzliche Prozessabbruchprüfungen siehe unten. Stromausfall, längerer Echtbetrieb und vollständige Wiederanlaufprüfung laufender Hardwareaufträge bleiben eigene Abnahmepunkte.


## Unerwarteter Prozessabbruch · V0.9.3

Zwei zusätzliche Integrationsprüfungen beenden ausschließlich zuvor selbst gestartete Prozesse in der temporären Programmkopie mit SIGKILL. Vor dem Signal werden Herkunft des Popen-Objekts und tatsächliches Arbeitsverzeichnis der Testkopie geprüft. Das ist kein Befehl für den realen Dienst oder Logger und keine Empfehlung für den regulären Betrieb.

Nach dem abrupten Ende ist die Kernel-Instanzsperre frei. Ein zurückgebliebener PID-Beleg verhindert keinen erneuten Start. Bestätigte Programmeinstellungen und synthetische Original-Historienarchive bleiben bytegleich und lassen sich nach Neustart auslesen/exportieren. In den neuen Prozess werden weder alte Vorbereitungstokens noch laufende Feuchte-Warnphasen übernommen.

Bereits gespeicherte Testjournale mit Status `writing` simulieren unterbrochene Einstellungen/Aufzeichnungsstarts. Bei ruhendem Auftrag zeigt der Status ausdrücklich `interrupted=true` und verlangt eine erneute lesende Zustandsprüfung; `automatic_retry=false`, keine vorbereitete Schreibfreigabe, kein automatischer Aufzeichnungsstart. Die Statusabfrage verändert die Originaljournale nicht. Aktive Aufträge oder bestätigte Endzustände werden nicht fälschlich als unterbrochen beschriftet.

Ein zweiter Test unterbricht den tatsächlichen atomaren JSON-Schreibhelfer nach Schreiben/fsync seiner Pending-Datei, aber vor `os.replace`. Der veröffentlichte alte Gesamtstand bleibt maßgeblich, die nicht veröffentlichte Datei wird beim Neustart nicht übernommen oder ungefragt entfernt. Ein künstlicher versteckter `.generating-*`-Zwischenstand wird nicht als vollständiger Testlauf angeboten.

Grenzen: SIGKILL beendet Prozesse, aber weder Kernel noch Datenträger. Diese Prüfungen ersetzen daher keinen Stromausfall-/Hardware-/Dateisystemnachweis. Gerätejournale sind Testbelege, keine real abgebrochenen BLE-Schreibtransaktionen; mehrdeutige ACK-/Gerätezustände müssen am Gerät separat beurteilt werden. Ein Abbruch nach tatsächlich erfolgtem rename mit unbestätigtem Verzeichnis-fsync wird bereits separat durch die Konfigurations-Fehlertests behandelt; kein automatischer Rollback.
