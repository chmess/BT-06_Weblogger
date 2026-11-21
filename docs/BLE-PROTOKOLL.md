# BLE-Protokollstand · V0.2.0

## Belege

Herstellerreferenz: [TZONE-Team/BTLogger-Android](https://github.com/TZONE-Team/BTLogger-Android), untersuchter Git-Baum `7a0a96f64aea40aadb5c4a980b45da6412f66d56`. Entwicklungsunterlage: [DevelopDoc v3.0](https://github.com/TZONE-Team/BTLogger-Android/blob/master/Bluetooth%20Temperature%20Data%20Logger%20(Android)-DevelopDoc_v3.0.pdf). Android-Beispiele `Config.java` und `Scan.java` geprüft. PDF lokal ausgewertet, nicht ins Repository kopiert.

Die SDK-Dokumentation nennt BT06 neben mehreren anderen Modellen. Sie beschreibt getrennte Android-DataManager/ConfigManager, Unlock, Start/Stop, Alarm-/Aufzeichnungs-/Broadcastparameter. Die Funktionstabelle unterscheidet Modellfamilien; z. B. ist PDF-Parametrierung für BT06 dort nicht unterstützt. Eine SDK-Funktion ist kein Beweis für die konkrete Firmware und liefert allein keine verifizierte rohe BLE-Befehlsfolge.

Im untersuchten Repository-Baum wurde keine explizite Wiederverwendungslizenz gefunden. SDK-Binärdateien und Beispielcode werden deshalb weder übernommen noch ausgeliefert. Ein eigener, auf überprüften Protokollbelegen beruhender Treiber ist vorzusehen. Private Referenzprojekte sind ebenfalls nicht enthalten.

## Fähigkeitsmatrix

Lokale Gerätefotos vom 21.11.2026 zeigen die Modellaufschrift BT06 und „BLE Temp & RH Data Logger“. Der QR-Code führt zu `http://www.tzonedigital.com/app_download/btlogger_en-us.html`, das auf `https://d.tzonedigital.com/` weiterleitet. Ein 30-Sekunden-Scan auf dem DeskPi fand `TempHumLogger` mit der Aufkleber-Kennungsfolge in den Manufacturer-Daten. Serienkennung, BLE-Adresse und Rohdaten bleiben unter `private/`; Fotos am Originalort. Frühe GATT-Versuche endeten mit Timeout; später gelang das Inventar im dokumentierten kurzen Standard-BLE-Fenster. Kein Pairing ausgeführt; Advertising kündigt Firmware 2.05 an.

| Funktion | Softwarestand | Konkreter BT06 |
|---|---|---|
| Advertising-Inventar, UUID/Rohfelder/RSSI | optionales Bleak-Werkzeug vorhanden | am lokalen BT06 erfolgreich |
| GATT-Services/Properties | explizite kurzzeitige Verbindung implementiert | im Standard-BLE-Fenster erfolgreich, ohne Pairing |
| Betriebssystem-Kopplung | nur ausdrücklicher `pair=True`-Auftrag | Notwendigkeit/Agent/PIN offen |
| Geräte-ID/Modell/Firmware | Advertising-Decoder 2.05 | ID zu Foto passend, angekündigte Firmware 2.05 |
| Live T/rF | belegter Advertising-Decoder | realer Empfang dekodiert und als CSV gespeichert |
| Historienblöcke/Index/Uhrbasis | eigenständiger Streamparser, noch kein produktiver Import | vollständige Übertragung geprüft; Gerätezeit versetzt, Offset nicht verifiziert |
| Zugangsschlüssel/Unlock | keine Befehle | offen |
| Gerätekonfiguration/Start/Stop/Löschen | keine Befehle | offen |

Die GATT-Diagnose liest keine Characteristic-Inhalte, registriert keine Notifications und sendet keine Logger-Konfigurationsbefehle. Die Suche verwendet den normalen BlueZ-Scan (kann Scan Requests senden), keine stille passive Erfassung. „Lesend“ bezeichnet hier die nicht veränderten Loggerparameter und Historien. Betriebssystem-Kopplung ist eine gesonderte, ausdrücklich angeforderte Aktion und kann Bondingdaten im OS/Peripheriegerät hinterlassen.

## Nächste Hardwareprüfung

1. Exaktes Modell und Firmware belegen, Gerät bewusst auswählen; kein Name-/USB-ID-Raten.
2. Advertising und GATT-Inventar privat dokumentieren.
3. Verbindungs-/Kopplungsverhalten prüfen, ohne Reset, Zeitänderung oder Logger-Konfiguration.
4. Messwertformat, Geräteuhr, Historienindizes und Vollständigkeitsnachweise mit kontrollierten Testmessungen verifizieren.
5. Erst danach Parser, reproduzierbare anonymisierte Testvektoren und Historienimport entwickeln. Gerätedaten oder Zugangsschlüssel nicht veröffentlichen.

Bluetooth-Kopplung, BLE-Verbindung und BT06-Anwendungszugang sind verschiedene Ebenen. Ein erfolgreicher GATT-Aufruf wird in der UI ausdrücklich als abgeschlossene Diagnose und nicht als laufende Messung ausgewiesen.

## Herstellerhandbuch des fotografierten Gerätetyps

Über den QR-Link erreichbar: [BT06 User Manual V1.4](https://d.tzonedigital.com/f/d/BT%20Series/User%20Manual/BT06-User%27s%20Manual%20V1.4.pdf). Es beschreibt Advertising, Verbindung, Zugangsschlüssel und Long-Range-Betrieb. Besonders relevant: Gerätekonfiguration speichern sowie ein Start der Aufzeichnung über die App können laut Handbuch bestehende Historie löschen. Diese Funktionen bleiben bis zum vollständigen verifizierten Historienauslesen und ausdrücklicher Zustimmung gesperrt.

Das Handbuch enthält widersprüchliche Intervallgrenzen (Spezifikationstabelle gegenüber Konfigurationsabschnitt). Deshalb keine vermeintlichen Grenzwerte als verifizierte Firmwareeigenschaften übernehmen. Für Long Range und temporär schnellere Advertising-Intervalle gibt es dokumentierte Tastenaktionen; Das Programm führt diese nicht aus und fordert keine unkontrollierten Tasten-/Resetversuche an.

## V0.2 Advertising

Das in [BT06-ADVERTISING.md](BT06-ADVERTISING.md) dokumentierte 2.05-Layout wurde anhand des öffentlichen Hersteller-SDKs statisch geprüft und eigenständig implementiert. Der reale Prüfpfad empfing ein zum Foto zugeordnetes Gerät und schrieb einen vollständigen Datensatz dauerhaft in eine private CSV. Diese Datenquelle benötigt keine GATT-Verbindung und verändert keine Loggerparameter.

Früherer GATT-Stand: Ein detaillierter Versuch fand das Gerät nach etwa 28 Sekunden, erhielt während des anschließenden 20-Sekunden-Verbindungsfensters aber keinen erfolgreichen Verbindungsabschluss. Der nachfolgende V0.3-Test war erfolgreich (siehe unten). Kein geratenes Pairing-/Unlock-/Historienkommando wird als Workaround gesendet.

Die installierte V0.2 wurde anschließend erfolgreich geprüft: laufender Advertising-Empfang, mehrere Pakete und mindestens zwei dauerhaft gespeicherte Stichproben mit dem gewählten 60-Sekunden-Abstand. Die reale Browseransicht zeigt aktuelle Daten, Kurven und Original-CSV-Export. Private Prüfberichte und Screenshots enthalten keine öffentlich versionierten Gerätekennungen.


## V0.3: verifizierter GATT-/Historienlesetest

Der reale BT06 2.05 stellt Service `6c400001-b5a3-f393-e0a9-e50e24dcca9e`, TX `6c400002-b5a3-f393-e0a9-e50e24dcca9e` (Write) und RX `6c400003-b5a3-f393-e0a9-e50e24dcca9e` (Notify) bereit. Verbindung und Notifications ohne Pairing erfolgreich. Der private Test pausiert den Hostempfang und stellt dessen vorherige Aktivierung anschließend wieder her; Loggeraufzeichnung, Uhr und Einstellungen werden nicht geändert.

Protokollfakten wurden aus der privat ausgewerteten Herstellerreferenz abgeleitet und unabhängig implementiert; SDK und dekompilierter Code werden nicht verteilt. Request: `2A`, Länge von Opcode + Nutzdaten + 1, zweibyteiger Opcode, optionale Nutzdaten, `23`. Reply: `26`, Opcode, Status (`01` = Erfolg), Nutzdaten, `23`. Der Parser verwirft unpassende/negative Antworten.

Erfolgreich belegte Leseabfragen: `7233` Gerätename, `7251` sechs Kalenderfelder, `4C01` Aufzeichnungsstatus, `7202` Aufzeichnungseinstellungen (Intervall uint16 LE, Einheit Byte 6). `7233` allein ist kein Nachweis für Serienkennung oder Firmware. Die ältere SDK-Kalenderauswertung verwendet Jahresbasis 1980; die reale 2.05-Historienmetadatenlage deutet auf 2000. Deshalb keine automatische Jahres-/UTC-Korrektur.

Der historische Lesebereich wird mit `6C00` und elf Nullbytes auf die gesamte Historie gestellt. Das ist eine Auswahl für die Übertragung, kein Speichern der Loggerkonfiguration. Antwort: zehn Bytes, Anzahl uint16 LE sowie Anfang und Ende uint32 LE. Anschließend startet `6C01` die reine Datenübertragung. Beide Operationen wurden am realen Gerät erfolgreich geprüft. Ein irrtümlich vorgesehener zusätzlicher `7203`-Aufruf wurde mit Status 5 abgewiesen; er ist nicht Bestandteil des unterstützten Lesepfads.

Historienrahmen: uint16 LE Nutzlänge, Typbyte und Nutzdaten. Typ 0 enthält eine uint32-Anzahl. Typ 1 enthält vollständige 8-Byte-Werte (Gerätesekunden uint32, Temperatur/RH je uint16). Typ 3 setzt Gerätesekunden und Intervall (je uint32) und liefert kompakte 4-Byte-Werte; Typ 2 setzt solche Werte fort. Zahlen sind sign/magnitude in Zehnteln, Highbyte FE ist ungültig. Die reale 2.05-Endemarkierung hat Typ FF, Anzahl uint32 und Anzahl vorheriger Rahmen uint32. Diese Struktur ist nicht für andere Firmwareversionen freigegeben.

Die erfasste vollständige Historie wurde unabhängig dekodiert: angekündigte und dekodierte Anzahl, Endezähler, Anfang/Ende sowie alle Zeitabstände stimmen überein. Originalantworten und dekodierte Werte bleiben private CSV. Vollständige Übertragung bedeutet noch keine verifizierte UTC-Zeitbasis: Gerätezeit ist gegenüber Hostzeit versetzt. Keine Verschmelzung mit Live-CSV, keine Uhreinstellung und keine automatische Freigabe destruktiver Aktionen.

Der Produktionsdienst bleibt V0.2. Der Web-GATT-Diagnosepfad bleibt ein Inventartest; der neue Lesetest ist noch kein UI-Sync. Wiederholter Import, Dedupe, Recovery, Benutzerführung für das kurze Funkfenster und unbeaufsichtigte Wiederverbindung sind ausstehend.

BlueZ-Suche und Liveempfang setzen ausdrücklich `DuplicateData=True`, weil Bleak sonst identische Meldungen unterdrückt. Das erhält Empfangszeit und Frischeprüfung auch bei gleichbleibenden Messwerten; es erzwingt keine Funkpakete und löst das kurze Verbindungsfenster nicht. Referenzen: [BlueZ Adapter API](https://bluez.readthedocs.io/en/latest/adapter-api/), [Bleak Linux backend](https://bleak.readthedocs.io/en/latest/backends/linux.html).
