# BLE-Protokollstand · V0.4.2-dev

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
| Historienblöcke/Index/Uhrbasis | Streamparser, sicherer CSV-Import und UI in V0.3.0-dev | vollständige Übertragung geprüft; Gerätezeit versetzt, Offset nicht verifiziert |
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

Der installierte Dienst läuft jetzt mit V0.3.0-dev. In V0.3.0-dev sind geprüfter Monats-CSV-Import, identische Wiederholungen ohne Kopie, getrennte Historienstände, Gerätezeit-UI und manuelles Sync implementiert. Der Web-GATT-Diagnosepfad bleibt ein Inventartest. Die integrierte BLE-/API-Strecke wurde automatisiert mit simuliertem BLE und anschließend im installierten Dienst am realen BT06 erfolgreich geprüft. Erwartete/empfangene Anzahl, gespeicherte CSV-Prüfsummen und Originalexport stimmen. Der frühere Stand bleibt erhalten und ist unverändert im neueren Transfer enthalten; neue Messwerte folgen dem konfigurierten Intervall. Der aktivierte Hostempfang läuft danach wieder mit aktuellen Werten, ohne Sync-/Wiederaufnahmefehler. Automatischer Sync, zusammengeführte Langzeithistorie, UTC-Zuordnung und unbeaufsichtigte Wiederverbindung bleiben offen. Die März-Historie ist laut Nutzer mit der ersten Inbetriebnahme plausibel; diese Aussage bestätigt keinen UTC-Offset.

BlueZ-Suche und Liveempfang setzen ausdrücklich `DuplicateData=True`, weil Bleak sonst identische Meldungen unterdrückt. Das erhält Empfangszeit und Frischeprüfung auch bei gleichbleibenden Messwerten; es erzwingt keine Funkpakete und löst das kurze Verbindungsfenster nicht. Referenzen: [BlueZ Adapter API](https://bluez.readthedocs.io/en/latest/adapter-api/), [Bleak Linux backend](https://bleak.readthedocs.io/en/latest/backends/linux.html).


## V0.3.1: reale Bereichsabfrage

Die unabhängig aus der Herstellerreferenz abgeleitete Bereichsauswahl wurde am realen BT06 2.05 mit einem kleinen bekannten Datenbereich geprüft: angekündigte/empfangene Anzahl und sämtliche Rohwerte stimmen mit dem gespeicherten Ausschnitt überein. `6C00` verwendet weiterhin elf Nutzdatenbytes; im Bereichsmodus `02 00 00`, gefolgt von Beginn/Ende als uint32 LE. Das sind rohe Geräte-Sekunden, keine automatisch umgerechnete Hostzeit. Die Grenzinklusion genau auf einem Messzeitpunkt wird nicht vorausgesetzt: der geprüfte Pfad verwendet eine Sekunde Abstand um die gewünschten Vergleichs-/Endewerte. Bereichsmetadaten liefern Anzahl, ersten und letzten tatsächlichen Wert wie bei Vollauswahl.

Der neue Treiber liest vor einer Bereichsauswahl die Gesamtmetadaten und Einstellungen. Eine geeignete eindeutige Basis benötigt mindestens 16 streng zeitlich aufsteigende Werte. Gesamter Anfang, Endgrenze, Anzahl, Einheit und Intervall müssen passen. Der Bereich beginnt eine Sekunde vor dem ersten der letzten 16 Basiswerte und endet eine Sekunde nach der aktuellen Endgrenze. Anzahl entspricht neuen Werten plus 16; Endemarkierung und vollständiger Vergleich der Überlappung sind Pflicht. Widersprüche blockieren die Übernahme. Keine pauschale Freigabe für andere Firmware oder Speicherumlauf.

Anschließend wurde der neue Nachladepfad selbst am Gerät geprüft: ausgewählter kleiner Bereich vollständig übertragen, Vergleichswerte unverändert, neue Messungen ergänzt, ursprünglicher Bestand unverändert und zu einer Reihe zugeordnet. Der Hostempfang wurde wieder gestartet. Die neue UI/API ist erst nach Dienstneustart aktiv; automatische Synchronisation, bestätigte UTC-Zuordnung und Zusammenführung verschobener Reihen sind weiter offen.


## V0.3.2: Zugriff ohne Tastendruck noch nicht erfolgreich

Der neue automatische Verbindungsablauf wurde einmal am ausgewählten BT06 ohne Tastenaktion geprüft. Er endete im kurzen Verbindungszeitlimit, es kam kein erfolgreicher Transfer zustande. Historien wurden nicht verändert; der aktivierte Advertising-Empfang wurde wieder gestartet. Dieser Versuch belegt keinen zuverlässig unbeaufsichtigten GATT-Zugriff im aktuellen Gerätemodus. Die neue Automatik ist daher standardmäßig ausgeschaltet und verändert weder Long Range noch andere Loggerparameter. Der Verbindungsmodus muss bei der späteren kontrollierten Konfiguration geprüft werden.

Die Nutzerbestätigung von Europe/Berlin betrifft die bisherige historische Aufzeichnung. Sie bestätigt weder die aktuelle Geräteuhr noch das Datum neuer Messungen. Eine separate, begrenzte Zeitzonenzuordnung erlaubt einen transparent gekennzeichneten Zusatzexport, keine automatische Uhrkorrektur oder Freigabe destruktiver Aktionen.


## V0.4: Einstellungs-Getter und Verbindungsprüfung

Am realen BT06 2.05 rein lesend erfolgreich: Name `7233`, Kalender `7251`, Aufzeichnungsstatus `4C01`, Aufzeichnungsparameter `7202`, Funkparameter `7235`, Funkmoduscode `7237`, Temperatur-/Feuchtealarm `7220/7223`. `7235` und `7237` verwenden drei Nullbytes als Leseparameter; keine Loggeränderung. Funkparameterantwort: drei Bytes, Leistungscode und Intervall uint16 LE in 100-ms-Schritten. Die verifizierte Leistungstabelle ordnet Codes 1–9 den Werten -20, -16, -12, -8, -4, 0, 4, 6, 8 dBm zu. Codebedeutung der separaten einbyteigen Funkmodusantwort bleibt unbelegt; nicht als Long-Range-Schalter freigeben.

Aufzeichnungsantwort: 15 Bytes; nur Intervall uint16 LE und Temperatureinheit Byte 6 (0/1) sind hier belegt. Andere Felder werden nicht aus SDK-Defaultwerten abgeleitet. Die untersuchte SDK-Implementierung belegt mehrere Parameter ihrer allgemeinen Methodensignatur nicht vollständig. Alarmantworten: je zwölf Bytes; Enable-/Typmarker, uint16-Verzögerungsrohdaten und **signed int16**-Grenze in Zehnteln je Unter-/Obergrenze. Das Alarm-Vorzeichenformat unterscheidet sich vom sign/magnitude der Messwert-Historie. Typ-/Verzögerungsbedeutung wird nicht geraten.

Die neuen Getter wurden am Gerät geprüft und ihre Rohbelege separat gespeichert; kein Setter oder Save-Changed gesendet. [Hersteller-SDK-Referenz](https://github.com/TZONE-Team/BTLogger-Android) und [BT06-Handbuch V1.4](https://d.tzonedigital.com/f/d/BT%20Series/User%20Manual/BT06-User%27s%20Manual%20V1.4.pdf) bleiben Quellen. Handbuch warnt vor Historienlöschung bei Konfigurations-Save und App-Start der Aufzeichnung. Schreibfunktionen bleiben daher bis belegter Implementierung, aktueller vollständiger Auslesung und ausdrücklicher Bestätigung gesperrt.

Die Verbindung gelang auch bei einem gesonderten Test mit nur kurzem STOP, ohne vorherigen START. Das belegt noch keine dauerhafte Funkmoduszuordnung. Ein ungekoppelter BlueZ-Eintrag war bei einem anderen Versuch nach Pausieren des Scans verschwunden; das ist nun ein expliziter Wiedererkennungsfall mit passender Identitätsprüfung. Das zuvor kurze automatische Zeitlimit war gegenüber dem beobachteten 30-Sekunden-Advertising unzureichend bemessen. Auch der korrigierte Versuch mit 35 Sekunden Wartezeit blieb jedoch ohne Tastenaktion erfolglos. Weder allein das Sendeintervall noch Long Range werden als abschließend belegte Ursache behauptet.

Die Änderungsvorschau verwendet keine Set-Befehle. Die privat ausgewertete Herstellerreferenz belegt für einen Namen 15 UTF-8-Bytes und für gemeinsame Funkparameter Leistungscode plus Intervall in 100-ms-Schritten. Für die Vorschau wird der im Handbuch genannte Bereich 0,5–30 s verwendet, ohne Rundung oder Abschneiden. Diese statischen Belege sind keine am Gerät verifizierte Schreib-/Save-Sequenz. Der separate Funkmoduscode und unbekannte Aufzeichnungsfelder werden nicht übernommen. Eine spätere Ausführung erfordert einen eigenen kontrollierten Ablauf einschließlich aktueller vollständiger Historie, Folgenbestätigung und Rücklesen; insbesondere kein probeweises Save.

## V0.4.1: statisch belegter Schreibpfad, Hardwareprüfung ausstehend

Erneut geprüfte Fakten aus derselben privaten Herstellerreferenz: App-Stopp `52A1`, Name `4333` mit 15 UTF-8-Bytes und FF-Padding, gemeinsame Funkparameter `4335` mit Leistungscode und uint16-Intervall in 100 ms, Aufzeichnungsblock `4302` mit 15 Bytes. Dort sind nur Sekundenintervall in Byte 0–1 (uint16 LE) und Einheit in Byte 6 (0/1) hinreichend belegt; die SDK-Implementierung belegt weitere Argumente ihrer Signatur nicht. Der eigene Pfad ändert das Intervall und erhält die Einheit, blockiert jedoch Nichtnullwerte in anderen Positionen, statt diese blind zu überschreiben. Der konservative implementierte Intervallbereich 10–64.800 s ersetzt keinen Firmware-Grenztest.

Wichtige Verkettung: `SetSaveChanged` sendet `52A3` ohne Payload und nach erfolgreicher Antwort zusätzlich `43FF` ohne Payload. Sein boolescher SDK-Parameter wird nicht zur Schonung der Historie genutzt. Der eigene Treiber bildet diese feste belegte Sequenz ab; Rolle und Nebenwirkungen des Abschlusses werden nicht als am Gerät abgenommen behauptet. Jede Antwort muss im ersten Hardwaretest exakt zum erwarteten Opcode passen, Status 1 haben und einen leeren Payload enthalten; abweichende Antworten blockieren alle weiteren Schreibschritte und werden als unklar protokolliert.

Statusbelegung laut SDK: 5 = App-Stopp, 17 = Startverzögerung; bisher nur Aufzeichnungscode 16 am realen Gerät bestätigt. Der Schreibablauf akzeptiert nur belegte gestoppte Zustände 1/2/4/5 oder zuvor explizit zu stoppenden Zustand 16; Verzögerung/Initialisierung/Unbekannt blockieren. Er startet die Aufzeichnung nicht selbst. Start `52A0` ist in der Referenz identifiziert, bleibt aber außerhalb der implementierten Befehlsliste. Keine Reset- oder Unlock-Sequenz wird geraten oder gesendet. Ein Reset ist vom Nutzer nur nach vollständiger Sicherung sämtlicher Daten und Einstellungen erlaubt; diese Vollständigkeit ist für bislang unbekannte Felder nicht nachgewiesen.

### Erster realer Schreibtest / V0.4.2-Korrektur

Nach ausdrücklich bestätigtem konkretem Auftrag: vollständige Historie vor Stopp und danach nochmals gespeichert. Reale Antworten auf `52A1` und `4302`: jeweils Opcode-Echo, Status 1, leerer Payload. Der nachfolgende Zwischenvergleich scheiterte; `52A3` und `43FF` wurden nicht gesendet. Reines erneutes Auslesen nach Disconnect zeigt bisherigen Intervallwert, unveränderte übrige Parameter und Status 5 (App-Stopp). Damit ist Code 5 nun auch am Gerät bestätigt. Ein erfolgreicher Setter-ACK belegt keinen dauerhaft gespeicherten Zielwert. Die ursprüngliche abweichende Zwischenantwort wurde nicht separat gespeichert; aus ihr wird keine zusätzliche Protokollbedeutung behauptet.

V0.4.2 lässt vor Save nur den vollständigen alten oder den angeforderten Zielblock zu, während alle ungeänderten Blöcke exakt bleiben müssen. Das unterstützt bis Save verzögerte Getter-Sichtbarkeit, ohne sie als bereits real belegtes Verhalten zu behaupten. Alle Zwischenantworten werden nun vor Prüfung gespeichert. Nach Save bleibt das exakte Ziel Pflicht. Reales Save-/Abschluss-/Rückleseverhalten ist weiterhin nicht abgenommen; kein blindes Wiederholen.
