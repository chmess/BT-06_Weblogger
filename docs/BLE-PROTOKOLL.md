# BLE-Protokollstand · V0.2.0

## Belege

Herstellerreferenz: [TZONE-Team/BTLogger-Android](https://github.com/TZONE-Team/BTLogger-Android), untersuchter Git-Baum `7a0a96f64aea40aadb5c4a980b45da6412f66d56`. Entwicklungsunterlage: [DevelopDoc v3.0](https://github.com/TZONE-Team/BTLogger-Android/blob/master/Bluetooth%20Temperature%20Data%20Logger%20(Android)-DevelopDoc_v3.0.pdf). Android-Beispiele `Config.java` und `Scan.java` geprüft. PDF lokal ausgewertet, nicht ins Repository kopiert.

Die SDK-Dokumentation nennt BT06 neben mehreren anderen Modellen. Sie beschreibt getrennte Android-DataManager/ConfigManager, Unlock, Start/Stop, Alarm-/Aufzeichnungs-/Broadcastparameter. Die Funktionstabelle unterscheidet Modellfamilien; z. B. ist PDF-Parametrierung für BT06 dort nicht unterstützt. Eine SDK-Funktion ist kein Beweis für die konkrete Firmware und liefert allein keine verifizierte rohe BLE-Befehlsfolge.

Im untersuchten Repository-Baum wurde keine explizite Wiederverwendungslizenz gefunden. SDK-Binärdateien und Beispielcode werden deshalb weder übernommen noch ausgeliefert. Ein eigener, auf überprüften Protokollbelegen beruhender Treiber ist vorzusehen. Private Referenzprojekte sind ebenfalls nicht enthalten.

## Fähigkeitsmatrix

Lokale Gerätefotos vom 21.11.2026 zeigen die Modellaufschrift BT06 und „BLE Temp & RH Data Logger“. Der QR-Code führt zu `http://www.tzonedigital.com/app_download/btlogger_en-us.html`, das auf `https://d.tzonedigital.com/` weiterleitet. Ein 30-Sekunden-Scan auf dem DeskPi fand `TempHumLogger` mit der Aufkleber-Kennungsfolge in den Manufacturer-Daten. Serienkennung, BLE-Adresse und Rohdaten bleiben unter `private/`; Fotos am Originalort. Der GATT-Inventarversuch endete mit Timeout. Kein Pairing ausgeführt; Advertising kündigt Firmware 2.05 an.

| Funktion | Softwarestand | Konkreter BT06 |
|---|---|---|
| Advertising-Inventar, UUID/Rohfelder/RSSI | optionales Bleak-Werkzeug vorhanden | am lokalen BT06 erfolgreich |
| GATT-Services/Properties | explizite kurzzeitige Verbindung implementiert | erster Versuch Timeout |
| Betriebssystem-Kopplung | nur ausdrücklicher `pair=True`-Auftrag | Notwendigkeit/Agent/PIN offen |
| Geräte-ID/Modell/Firmware | Advertising-Decoder 2.05 | ID zu Foto passend, angekündigte Firmware 2.05 |
| Live T/rF | belegter Advertising-Decoder | realer Empfang dekodiert und als CSV gespeichert |
| Historienblöcke/Index/Uhrbasis | nicht implementiert | offen |
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

GATT bleibt offen: Ein detaillierter Versuch fand das Gerät nach etwa 28 Sekunden, erhielt während des anschließenden 20-Sekunden-Verbindungsfensters aber keinen erfolgreichen Verbindungsabschluss. Kein geratenes Pairing-/Unlock-/Historienkommando wird als Workaround gesendet.

Die installierte V0.2 wurde anschließend erfolgreich geprüft: laufender Advertising-Empfang, mehrere Pakete und mindestens zwei dauerhaft gespeicherte Stichproben mit dem gewählten 60-Sekunden-Abstand. Die reale Browseransicht zeigt aktuelle Daten, Kurven und Original-CSV-Export. Private Prüfberichte und Screenshots enthalten keine öffentlich versionierten Gerätekennungen.
