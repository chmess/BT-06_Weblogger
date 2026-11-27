# Änderungen

## 0.8.1-dev · 2026-11-27

- Save Settings lädt Programmeinstellungen, Messstellen und Zuordnungshistorie als gemeinsame JSON-Datei herunter. Load Settings zeigt Änderungen vorab; erst Save Settings übernimmt sie. Alte Einstellungsdateien bleiben ladbar, Messstellen können beim Import abgewählt werden.
- Gemeinsame atomare Ablage unter config/application.json; vorhandene settings.json/sites.json werden beim ersten Speichern übernommen. Bestehende Zuordnungshistorie bleibt erhalten; importierte offene Intervalle enden am Dateistand und aktivieren keine Loggerbindung. Änderungen aktueller Messstellen gelten erst ab Übernahme.
- Vorschau mit einmaligem, zehn Minuten gültigem Token und Revisionsprüfung. Konflikte, ungültige Dateien und unbestätigte Schreibabschlüsse blockieren Änderungen; kein automatischer Wiederholungsversuch. Keine BLE-/Uhränderungen oder Aktivierung von Empfang/Autosync.
- Gesamtsuite 191 Tests bestanden; nach abschließenden Fehler-/Datenschutzkorrekturen alle 12 Konfigurations-Kerntests bestanden. Vollständige Chromium-Prüfung einschließlich Vorschau, Abbrechen, Einstellungen ohne Messstellen und bearbeitetem Import bestanden. V0.8.0 im Dienst bestätigt.

## 0.8.0-dev · 2026-11-27

- Messstellenverwaltung mit stabiler ID, Name, Raum, Beschreibung, individuellen Feuchte-/Dauerkriterien und optionaler Oberflächenannahme. Kriterien bewusst in die manuelle Auswertung übernehmbar; kein neuer automatischer Alarmdienst.
- Loggerzuordnung ab Hostzeit mit historisierten Intervallen und damaligen Angaben. Standort-/Loggerwechsel schließen alte Intervalle, Änderungen aktiver Messstellen versionieren Angaben/Kriterien ohne rückwirkende Umbenennung. Veraltete Entwürfe/Revisionen und rückwärts laufende Hostzeit blockieren Änderungen.
- Künftig gespeicherte Host-Empfänge tragen die stabile Messstellen-ID. Originalzeilen und ungeprüfte Gerätehistorien werden nicht rückwirkend geändert oder anhand ihres Datums geraten zugeordnet. Simulation bleibt getrennt.
- 179 Tests der Gesamtsuite sowie Browserprüfung bestanden. V0.7.2 im Dienst bestätigt. Gemeinsames Save/Load und messstellenbezogene Auswahl/Auswertung folgen; aktuelle Diagramme bleiben loggerbezogen.

## 0.7.2-dev · 2026-11-27

- Zusätzlicher Auswahl-CSV-Export mit Originalspalten und optional Taupunkt, absoluter Feuchte sowie Sättigungs-/Partialdruck. Originalauflösung; Standard-Originalexport bleibt bytegleich. Quellen-, Zeit-, Qualitäts- und Exportkennzeichnung sind Pflichtspalten.
- Berechnete Werte mit vier Nachkommastellen/Dezimalkomma und verpflichtendem Modell-/Statusfeld. Fehlende oder nicht vom Modell abgedeckte Ergebnisse bleiben leer; ungeprüfte Gerätezeit und getrennte zugeordnete Zeitfelder bleiben erhalten.
- Neue Exportseite für gewählten Zeitraum, sichtbaren Ausschnitt oder Statistikbericht. Vorbereitung bindet die Auswahl an Quelle/Logger/Zeitfenster; späte oder nicht passende Vorbereitungen werden verworfen. Downloadfehler bleiben in der Oberfläche, kein versehentlicher Wechsel zur Fehler-JSON.
- 5 Export- und 20 API-Tests sowie Browserprüfung bestanden. V0.7.1 läuft; erste echte Betriebsereignisse ohne Protokollfehler geprüft. Keine Geräteänderung.

## 0.7.1-dev · 2026-11-27

- Dauerhafte monatliche Ereignis-CSV unter data/events mit privater Ablage, Dateisperren und fsync. Dienststart/-ende, Hostempfang, aktuelle/veraltete Aussendungen, empfangener Aufzeichnungsstatus, Speichervollkennzeichnung, Empfangs-/CSV-Fehler und Auftragsergebnisse protokollieren. Keine nachträglich erfundenen Vorgänge.
- Neue Ereignisseite mit Hostzeit-, Logger-, Stufen- und Typfiltern. Begrenzte Anzeige bis 500 Einträge, vollständiger gefilterter CSV-Export. Echtbetrieb bleibt von der gewählten Messdaten-/Simulationsquelle getrennt.
- Wiederholte identische Empfangsfehler und unveränderte Advertising-Zustände nicht pro Paket protokollieren. Interne Empfangspausen erzeugen keinen falschen Verlust-/Gerätestoppnachweis. Unbestätigte Startaufträge bleiben Warnungen. Ereignisschreibfehler sind separat sichtbar und verhindern weder primäre Messwertspeicherung noch Auftragserholung; keine automatische Wiederholung von Aktionen.
- Gesamtsuite mit 163 Tests bestanden, zusätzlich neuer Test für unbestätigte Starts/fehlerhafte Ereignisablage und 11 Ereignistests separat bestanden; Browserprüfung einschließlich mobiler Ereignistabelle erfolgreich. V0.7.0 im Dienst bestätigt. Automatische Klima-/Batterieereignisse und erweiterte Exporte bleiben offen.

## 0.7.0-dev · 2026-11-27

- Grundstatistik aus Originalzeilen: Min/Max mit Zeitpunkt, Stichprobenmittel, zeitgewichtetes Mittel und Datenabdeckung für Temperatur, relative Feuchte, Taupunkt und absolute Feuchte. Fehlende Werte und Zeiten bleiben je Größe getrennt sichtbar. Keine Statistik aus verdichteten Grafikpunkten.
- Zeitmittel mit linearer Verbindung ausschließlich benachbarter gültiger Messpaare bis zum 1,5-fachen Messintervall; kein Brückenbau über Lücken und keine Extrapolation. Einzelwerte erhalten kein Zeitmittel. Laufende Aggregation ohne zusätzliche Messdatenkopie.
- Neue Statistikseite für gewählten Zeitraum oder sichtbaren Ausschnitt, Original-CSV exakt für den Bericht, mobile Tabelle und Schutz vor überholten Antworten. Kriterien und Gerätezeitwarnungen bleiben sichtbar.
- 7 Statistik- und 18 API-Tests sowie Browserprüfung bestanden. V0.6.1 im Dienst bestätigt. Ereignisprotokoll und erweiterte Exporte innerhalb V0.7 noch offen.

## 0.6.1-dev · 2026-11-27

- Zeitabhängige Feuchteindikatoren aus Originalzeilen: einstellbare Luft-/Oberflächenschwellen, Hysterese und Mindestphasendauer. Zeit ab Schwelle getrennt von Phasendauer einschließlich Hysterese. Lücken, ungültige Werte und unbelegte Bereichsränder zählen als unbekannt; keine Brücke über fehlende Zeit.
- Oberflächenmodell nur nach ausdrücklicher Auswahl: konstante Temperatur oder Differenz unter Lufttemperatur. Separater Bericht für Luft, angenommene Oberfläche und Kondensationsbedingung. Ohne Annahme keine Oberflächenbewertung. Keine Schimmelwahrscheinlichkeit oder pauschale Entwarnung.
- Gewählten Zeitraum oder sichtbaren Diagrammausschnitt auswerten; exakte Quellen-/Zeithinweise und Kennzeichnung veralteter Berichte. Kriterien gelten für die jeweilige Auswertung, kein automatischer Alarmdienst. Höchstens 100 Phasendetails je Kanal, Zähler berücksichtigen alle Phasen.
- 8 Algorithmus- und 17 API-Tests sowie Browserprüfung bestanden. Synthetische Laufzeitmessung dokumentiert; V0.6.0 im Dienst bestätigt. Keine Geräteänderungen oder neue Messdatenablage.

## 0.6.0-dev · 2026-11-27

- Taupunkt und absolute Feuchte aus gültigen Temperatur-/Feuchtepaaren berechnen. Dokumentiertes Magnus-Modell über Wasser mit Bereich −45 bis +60 °C; keine Extrapolation, fehlende Werte und 0 % rF ohne erfundenen Taupunkt. Originalmessdaten bleiben unverändert.
- Taupunktkurve im gemeinsamen °C-Diagramm, berechnete Werte in Live-/Testdatenkarten. Ableitung vor Verdichtung, Extrema sämtlicher Größen und Datenlücken erhalten; ursprüngliche dreispaltige Punktantwort bleibt kompatibel.
- Neue Seite Taupunkt/Feuchte mit Rechner für Sättigungs-/Partialdruck, absolute Feuchte, kritische Oberflächentemperaturen bei 70/80 % rF, angenommene Oberflächenfeuchte und Taupunktabstand. Herkunft übernommener Werte und manuelle Oberflächenannahme sichtbar; überholte Berechnungsantworten werden verworfen. Keine zeitabhängige Schimmelbewertung.
- 32 gezielte Python-Tests und Browserprüfung bestanden; Performance mit synthetischen Daten gemessen. V0.5.1 im Dienst bestätigt; keine Geräteänderungen.

## 0.5.1-dev · 2026-11-27

- Temperatur- und Feuchteachse unabhängig automatisch oder mit festen Grenzen darstellen. Fehlerhafte/unvollständige Grenzen verändern das Diagramm nicht; Standardachsen und Zoom lassen sich getrennt zurücksetzen.
- Diagrammansicht mit exaktem Zeitraum, Zoom, Achsen und Kurvenauswahl im Browser speichern/laden. Bis zu 20 Ansichten getrennt nach Quelle, Logger und Testlauf/Historienstand; keine Messdatenkopie. Laden stellt den gespeicherten Zeitraum wieder her und pausiert Live-Follow. Beschädigte Ansichten werden nicht angewendet, überholte Ladeaufträge übernehmen keinen Zoom.
- V0.5.0 im Dienst bestätigt. Keine Geräteänderungen und keine neue API.

## 0.5.0-dev · 2026-11-27

- Diagrammbedienung: Zeiträume 1/6/12/24/48 Stunden, 7/14/30/90/180/365 Tage und alles; Monatsnäherungen ausdrücklich als solche beschriftet. Vorherigen/nächsten sichtbaren Zeitraum laden, auch in Bereichen ohne Messwerte. Gerätezeit weiterhin als ungeprüften Kalender behandeln.
- Eigener CSV-Export des sichtbaren Zoomfensters in Originalauflösung. Export des gewählten Gesamtzeitraums bleibt separat verfügbar; keine Änderung an Originaldaten oder Zeitzuordnungen.
- Vollbild umfasst Diagramm und Bedienelemente; Zeitraum bleibt sichtbar. Exakte Zeitpunkte beim Blättern auch während der herbstlichen Zeitumstellung erhalten. Eingaben nach manueller Bearbeitung wieder als freie Ortszeit behandeln.
- V0.4.8 im Dienst bestätigt; keine Gerätewerte verändert. Weitere V0.5-Punkte wie manuelle Achsengrenzen und persistente Ansichten bleiben offen.

## 0.4.8-dev · 2026-11-27

- Unter-/Obergrenzen und Aktivierung für Temperatur- und Feuchtealarme als Entwurf, Vorschau und geschützte Geräteänderung ergänzt. Originale Alarmtypen und Verzögerungen bleiben bytegenau erhalten; unbekannte Formate blockieren. Grenzen in exakten 0,1-Schritten, untere Grenze kleiner als obere.
- Temperaturalarm vorerst ausschließlich bei unverändertem °C-Modus: keine ungeprüfte Umrechnung und kein gleichzeitiger Wechsel auf °F. Feuchtealarm unabhängig davon. Vollständige Historienprüfung, Bestätigung, Stopp, Save/Abschluss und striktes Rücklesen weiterhin erforderlich. Kein realer Alarmwert verändert.

## 0.4.7-dev · 2026-11-22

- Temperatureinheit °C/°F als Entwurf, Vorschau und geschützte Geräteänderung ergänzt. Einheit und Intervall teilen den belegten 15-Byte-Aufzeichnungsblock; unveränderte Felder bleiben erhalten, unbekannte Zusatzfelder sperren das Schreiben. Gemeinsame Änderungen erzeugen nur einen Setter.
- Bestehender Schutzablauf bleibt erhalten: vollständige Historie in bisheriger Einheit vor/nach Stopp prüfen und speichern, Bestätigung, Save/Abschluss, striktes Rücklesen. Kein automatischer Neustart. Keine reale Einheitenänderung ausgeführt; laufender Logger unverändert.

## 0.4.6-dev · 2026-11-22

- Ausdrückliche Ausnahme für den bestätigten Neustart bei unbekanntem Gerätebestand: nur Initialzustand, exakt belegte negative Umfangsantwort und geprüfte vollständige Alt-CSV. Zusatzbestätigung des möglichen Verlusts noch nicht ausgelesener Werte erforderlich. Bestand bleibt unbekannt; Status 3 wird weiterhin nicht als leer interpretiert. Genau ein Start, keine automatische Wiederholung. Real ausgeführt: genau ein Start mit positiver Antwort, unverändertes Intervall anschließend zurückgelesen, Aufzeichnung durch GATT-Status 16 bestätigt. Archivierte Originalhistorie erhalten.
- Rechnerische Speicherdauer aus Herstellerkapazität 32.000 Werte und ausgelesenem Intervall anzeigen: bei 25 Minuten etwa 556 Tage. Tatsächlich freie Restdauer bleibt unbekannt.
- Geräteuhr bleibt vorerst unverändert: Jahreskodierung des Schreibbefehls noch nicht für diese Firmware belegt.

## 0.4.5-dev · 2026-11-22

- Historienumfang jetzt wie im Hersteller-SDK unmittelbar nach einer Statusabfrage lesen. Geänderter Status blockiert Start. Ob dies die reale Ablehnung behebt, ist noch offen; Status 3 bleibt Fehler und kein Leerstandsbeleg.
- Abgewiesene/ungültige Umfangsantworten inklusive vorangehendem Status nun dauerhaft als separate Diagnose-CSV/JSON sichern. Kein zusätzlicher Messdatenbestand, keine Startfreigabe durch Diagnosebelege.
- 28 gezielte Tests bestanden (Aufzeichnungs- und Konfigurationsablauf); keine erneute vollständige Browserprüfung, da Oberfläche unverändert. Hardwareprüfung der neuen Reihenfolge steht aus.

## 0.4.4-dev · 2026-11-22

- Aufzeichnungsstart mit eigener lesender Vorbereitung, zwei Bestätigungen und einmaligem, gerätegebundenem Zehn-Minuten-Token. Vorhandene Historie vollständig sichern; leeren Speicher ausschließlich durch vollständige zehnbyteige Nullmetadaten belegen, keine erfundenen Messwert-CSV. Statusnullen allein genügen nicht.
- Vor Start Einstellungen, Identität, Zustand und Umfang erneut prüfen und Belege dauerhaft speichern. Genau ein belegter Startbefehl, keine Parameter-/Uhränderung, kein Save/Reset. Aktive Aufnahme nur durch Status 16 oder frischen Advertising-Übergang nach Start bestätigen; ACK allein bleibt unbestätigt. Bei unklarer Antwort ausschließlich lesend nachprüfen, keine Wiederholung.
- 119 Tests und Browserprüfung bestanden. Dienst aktiviert; erster Leseversuch Timeout, zweiter verbindet erfolgreich, erhält auf Historienumfang Status 3. Kein Leerstandsbeleg, keine Vorbereitung freigegeben, kein Startbefehl. Hostempfang wieder frisch; Interpretation von Status 3 offen.

## 0.4.3-dev · 2026-11-21

- Reale Parameteränderung nach erneuter vollständiger Historienprüfung: Setter, Save und Abschluss jeweils mit Status 1 bestätigt; anschließende neue Leseverbindung zeigt gewünschten Aufzeichnungswert bei unveränderten übrigen Parametern. Kein Reset oder Aufzeichnungsstart. Advertising meldet initialisiert; bisherige Original-CSV bleiben erhalten.
- Ursache der verbleibenden Fehlermeldung: nach Save liefert `4C01` acht Nullbytes statt des bisherigen 30-Byte-Status. Neues, eng begrenztes Antwortformat als „keine Aufzeichnungsdetails“ erkannt; weder Aufnahme, Stopp noch leere Historie daraus abgeleitet. Parameterprüfung separat vom Aufnahmezustand. Finale Originalantworten werden vor inhaltlicher Prüfung gespeichert.
- Rein lesende Nachprüfung unklarer Aufträge: vollständige positive Setter-/Save-/Abschlussbelege und geprüfte Historienreferenzen Pflicht, Zielwerte strikt prüfen, niemals Schreibbefehle wiederholen. Bereits vorhandener originaler Lesebeleg nach Abschluss kann ohne neue Bluetooth-Kommunikation verwendet werden; sonst neuer Leseauftrag. Ergebnis `parameters_verified` bei fehlenden Statusdetails ausdrücklich vom bestätigten Stopp unterschieden. Alte abgeleitete Statuszusammenfassungen werden nur nach Originalprüfung im Speicher aktualisiert, ohne Originaldateien umzuschreiben.
- 110 Python-Tests und Browserprüfung einschließlich alter Zusammenfassungen, unbekannter Statusvarianten, fehlender ACKs, beschädigter Belege, altem Zielwert und Nachprüfung ohne weitere BLE-Anfrage. V0.4.3 im Dienst aktiviert und Nachprüfung mit echten Originalbelegen bestätigt: keine weiteren BLE-Anfragen, Schreib-CSV unverändert, Liveempfang wieder frisch. Vollständige V0.4, Aufzeichnungsstart, Reset und zuverlässiger unbeaufsichtigter Zugriff bleiben offen.

## 0.4.2-dev · 2026-11-21

- Erste integrierte Gerätevorbereitung erfolgreich: vollständige Historie und alle acht unterstützten Einstellungsabfragen dauerhaft geprüft gespeichert, Hostempfang wieder aufgenommen. Nach konkreter Nutzerbestätigung bestätigte der BT06 App-Stopp und Aufzeichnungs-Setter. Zweite vollständige Historie nach Stopp ebenfalls gesichert. Zwischenprüfung brach anschließend vor Save/Abschluss ab. Erneutes reines Auslesen: bisheriger Intervallwert, App-Stopp, keine Historienlöschung.
- Die Vor-Save-Prüfung verlangte bereits den endgültigen Zielwert. Korrigiert: nur bei konkret geänderten Blöcken sind vor Commit exakt Ausgangs- oder Zielblock erlaubt; jeder dritte Wert und jede Abweichung ungeänderter Felder blockieren Save. Nach Commit bleibt ausschließlich der Zielwert zulässig. Getrennte Protokollierung der Sichtbarkeit vor Commit; Zwischenbeleg auch bei Abweichung dauerhaft erhalten, ebenso Stoppbeleg vor zweiter Vollauslesung.
- 103 Python-Tests einschließlich verzögert sichtbarer Setter, unverändertem Wert trotz Save-ACK, unzulässigem Zwischenwert und bereits gestopptem Gerät; Browserprüfung. Korrigierter Save-Ablauf noch nicht am realen Gerät abgenommen. Keine automatische Wiederholung, kein Start und kein Reset. Aktivierung der Korrektur erfordert Dienstneustart.

## 0.4.1-dev · 2026-11-21

- Kontrollierter, expliziter Schreibablauf für Name, gemeinsame Funkparameter und Aufzeichnungsintervall vorbereitet. Getrennte Geräte-/Historienvorbereitung und Bestätigung; einmalige, zehn Minuten gültige Vorbereitung an Identität/Firmware/Adapter und aktuellen Einstellungsbeleg gebunden. Keine generische Byte-, Reset-, Unlock-, Uhr- oder Start-Route.
- Vor jedem Schreibauftrag aktuelle Einstellungen vergleichen und gesamte Historie dauerhaft prüfen/speichern. Bei laufender Aufzeichnung erst danach explizit bestätigter Stopp; anschließend nochmals gesamte Historie sichern. Unbekannte Nichtnullfelder im Aufzeichnungsblock sperren Änderungen; keine SDK-Null-Defaults. Zwischenprüfung vor Commit, danach Rücklesen aller Einstellungen und Prüfung unveränderter Gegenwerte. Aufzeichnung bleibt gestoppt.
- Herstellerreferenz auf verketteten Abschluss nach Save geprüft; Stop-, Set-, Save- und Abschlusssequenzen unabhängig implementiert. Dauerhafter CSV-/JSON-Auftragsbeleg vor jedem möglicherweise wirksamen Befehl; unklare Ergebnisse ohne automatische Wiederholung oder Rollback. Vorbereitungen werden nach Neustart nicht wiederaufgenommen. Gemeinsame BLE-Sperre, bisheriger Hostempfang nach jedem Ausgang wiederhergestellt.
- 99 Python-Tests und Browserprüfung bestanden: simulierter vollständiger Ablauf, Fehler vor/nach Stopp, negative/unklare Antworten, Schreib-/Rücklesefehler, einmalige Bestätigung, Ablauf/Ersetzung/Neustart, CSRF/Sperre, zwei Bestätigungen und Entwurfsänderung. **Noch kein realer Geräteschreibtest**, Dienstaktivierung erforderlich. Vollständige V0.4-Konfiguration und unbeaufsichtigter Zugriff weiterhin offen.

## 0.4.0-dev · 2026-11-21

- Änderungsvorschau für Gerätename, Sendeintervall und Sendeleistung mit strengem Wertevergleich und Bezug auf den aktuellen Originalbeleg. Erhält ungespeicherte Eingaben bei neuer Auslesung; veraltete Entwürfe und unbekannte Funk-Gegenwerte blockiert. Keine Gerätebefehle, keine Schreibfreigabe; Warnung vor möglichem Historienverlust und notwendige Vollauslesung/Bestätigung/Rücklesen sichtbar. 88 Python-Tests bestanden.
- Fortschritt, Tastensignal und Fehler eines Einstellungs-Leseauftrags direkt bei den Geräteeinstellungen angezeigt. Fehlgeschlagene Aufträge ausdrücklich ohne neuen Stand; bisherige Werte bleiben sichtbar. Installierter Leseweg mit acht erfolgreichen Geräteabfragen und neuem dauerhaftem Stand geprüft.
- Erste lesende Geräteeinstellungsansicht: belegte Name-/Zeit-/Status-/Aufzeichnungs-/Funk-/Alarmabfragen, neue Anzeige, verifizierter CSV-Rohbeleg und JSON-Zusammenfassung. Kein Setter, Speichern am Logger, Start/Stop oder Uhränderung.
- Neue Abfragen am realen BT06 erfolgreich; unbekannter Funkmoduscode wird ausdrücklich nicht als Long-Range-Zustand interpretiert. Weitere SDK-Parameter bleiben unbekannt statt auf Standardwerte gesetzt.
- BlueZ-Cacheverlust nach Stop der Suche durch erneute Auswahl mit Adresse, Gerätekennung und Firmware abgedeckt. Automatisches Verbindungsfenster für vorhandene Einträge auf 35 Sekunden erweitert, um ein 30-Sekunden-Sendeintervall zu berücksichtigen; nach frischer Suche kurzes Fenster.
- Verbindung mit nur kurzem STOP erfolgreich. Längerer Versuch ganz ohne Tastenaktion weiterhin Timeout; Automatik bleibt aus und wird nicht als zuverlässig abgenommen dargestellt.
- 82 automatisierte Tests und synthetische Browserprüfung erfolgreich; gespeicherte Originale zusätzlich nur lesend geprüft. Lese-UI/API im installierten Dienst bestätigt; die verbesserte lokale Fehler-/Fortschrittsanzeige erfordert einen weiteren Dienstneustart. Kontrollierte Schreibfunktionen bleiben offen.

## 0.3.2-dev · 2026-11-21

- Optionale automatische Nachladeversuche innerhalb des bestehenden Prozesses: standardmäßig aus, explizite Gerätebindung, 15–1440 Minuten Intervall, frischer Liveempfang erforderlich, kein automatischer Vollabruf. Begrenzte Verbindungsdauer, längere Wartezeiten bei Fehlern und dauerhafter Versuchszustand.
- Neue Messungen platzsparend als CSV-Fortsetzung gespeichert, vollständiger Zwischenstand spätestens nach 32 Schritten. Manifestversion 2, vorhandene Version 1 weiter lesbar. Keine Änderung alter Originaldateien.
- Ausdrücklich bestätigte historische Zeitzone pro Datenstand; zusätzlicher CSV-Export mit abgeleiteten Kalenderzeiten und Offset, Originalzeitstempel unverändert. Datum bleibt ungeprüft, spätere Werte werden nicht ungefragt zugeordnet; problematische Zeitumstellungsstunden blockiert.
- Gesamte Automatik einschließlich Wiederaufnahme und Speicherschutz synthetisch geprüft. Hardwareversuch ohne Tastendruck im aktuellen BT06-Modus: Timeout, keine Historienänderung, Hostempfang wieder gestartet. Automatik bleibt aus; unbeaufsichtigtes Auslesen nicht als erfolgreich behauptet.
- Neue UI/API erfordert Dienstneustart. Der bestätigte historische Zeitbezug ist separat hinterlegt; tatsächliche Geräteuhrkorrelation und geeigneter Verbindungsmodus bleiben offen.

## 0.3.1-dev · 2026-11-21

- Zeitbereichsabfrage am realen BT06 mit bekannten Rohwerten verifiziert und als begrenzter, reiner Lesepfad implementiert. „Neue Werte nachladen“ prüft 16 gespeicherte Vergleichswerte sowie Zähler und Grenzen, bevor neue Messungen übernommen werden. Keine Loggeränderungen.
- Exakte Rohdatenfortsetzungen werden als gemeinsamer Verlauf angeboten; abweichende Reihen bleiben getrennt, frühere Einzelstände bleiben erreichbar. Regenerierbarer Index im Arbeitsspeicher, keine Datenbank und kein zusätzlicher Dienst.
- Herkunft unterscheidet Vollauslesung und aus Basis plus Bereich fortgesetzten Stand. Ein Nachladebereich gilt ausdrücklich nicht als frischer Vollständigkeitsnachweis des gesamten Gerätespeichers. Gerätezeit bleibt ungeprüft.
- Neuer Nachladepfad mit realem BT06 erfolgreich geprüft: Vergleichswerte stimmen, neue Messungen übernommen, frühere Werte unverändert und Liveempfang wieder gestartet. 56 automatisierte Tests und synthetische Browserprüfung bestanden; fortgesetzter Originalverlauf nur lesend geprüft.
- Aktivierung der neuen UI/API erfordert noch Dienstneustart. Automatischer Sync, tatsächlicher UTC-Offset und uneindeutige/verschobene Historien bleiben offen.

## 0.3.0-dev · 2026-11-21

- Auf DeskPi aktiviert und manuelle integrierte BLE-/API-Strecke am realen BT06 erfolgreich geprüft: erwartete und empfangene Anzahl gleich, CSV-Prüfsummen und Originalexport stimmen; bisherige Werte unverändert enthalten, zusätzliche Messungen im konfigurierten Intervall. Liveempfang anschließend wieder aktuell, kein Sync-/Wiederaufnahmefehler.

- Vollständige Historien als unveränderliche Monats-CSV-Stände; Veröffentlichung erst nach CSV-/Manifest-fsync und atomarer Umbenennung. Inhaltskennung verhindert identische Kopien auch nach Neustart. Veränderte/überlappende Stände bleiben ausdrücklich getrennt; keine geratenen stabilen Geräteindizes.
- Manuelles lesendes GATT-Sync mit Fortschritt, begrenztem Empfang, gemeinsamer Adaptersperre, Abbruch beim Beenden und Wiederaufnahme des vorher aktivierten Hostempfangs. Keine automatische Kopplung oder Loggeränderung.
- Datenquelle Loggerhistorie mit Gerätezeitachse, freier Kalenderauswahl, Historienstandwahl und Original-CSV. UTC-Zeitstempel bleiben bei ungeprüfter Zeitbasis leer; Original-Gerätesekunden bleiben erhalten. Rückwärts laufende Gerätezeit blockiert eine irreführende Kurve, Originalexport bleibt möglich.
- Offline-Capture-Import und reproduzierbarer Historien-Performancecheck. Original-Capture erfolgreich importiert und wiederholt ohne Kopie geprüft; echte Historienansicht nur lesend geprüft.
- 49 automatisierte Tests bestanden; synthetische Browserprüfung einschließlich Historie, Export und mobiler Ansicht erfolgreich. Die anschließende Geräteprüfung im installierten Dienst war erfolgreich (siehe oben). Automatischer Sync, inkrementelles Nachladen und UTC-Zuordnung noch offen.

### Vorangegangene Protokollprüfung

- Reale GATT-Verbindung ohne Pairing, reine Geräte-/Uhrzeit-/Statusabfragen und vollständiger Historientransfer geprüft. Private Roh- und dekodierte CSV bleiben außerhalb des Repositorys. Noch kein produktiver Historienimport oder automatischer Sync.
- Unabhängiger, begrenzter Historienparser für Rahmenfragmentierung, vollständige und kompakte Messwerte, Anzahl-/Ende-/Rahmenzählerprüfung. Fehler sperren die Vollständigkeitsbestätigung; Gerätezeiten erhalten keinen erfundenen UTC-Offset. Jahresbasis der Kalenderantwort muss ausdrücklich festgelegt werden.
- BlueZ-Scans fordern wiederholte identische Advertising-Meldungen an, damit unveränderte Messwerte nicht durch Bleaks Duplicate-Filter als ausgefallener Empfang erscheinen. CSV-Speicherabstand bleibt bestehen. Laufender V0.2-Dienst noch nicht aktualisiert.
- 37 automatisierte Tests bestanden, einschließlich abgeschnittener/fehlerhafter Historien, Zeitkontext, Überlauf, wiederholter Zeitstempel und abgewiesener Leseantworten.

## 0.2.0 · 2026-11-21

- Auf dem headless DeskPi aktiviert: realer BT06-Empfang und wiederholte CSV-Speicherung im Dienst, tatsächliche Browseransicht samt Verlauf/Export geprüft. 28 automatisierte Tests bestanden.

- Lesender BT06-Advertising-Decoder für das belegte Firmwareformat 2.05; Temperatur, Feuchte, Spannung, RSSI und Status. Keine Gerätebefehle oder Kopplung für den Liveempfang.
- Eigene Datenquelle für echte Empfänge, monatliche CSV-Dateien mit Host-Zeitbasis, wählbarer Speicherabstand, sichtbare Datenalter-/Schreibfehler, Start/Pause und Wiederaufnahme nach Neustart.
- Gemeinsame Adaptersperre verhindert parallelen Liveempfang und Diagnose. Unbekannte Firmware/Identitäten werden abgewiesen.
- Diagramme/Export wechseln zwischen echten Empfängen und Simulation; manueller Zoom pausiert die Liveaktualisierung. UI und API bleiben während Updates bis zum Prozessneustart zusammen.
- Taupunkt und Klimaberechnungen bleiben gemäß Benutzerkorrektur bei V0.6. Historienimport bleibt V0.3 und benötigt eine funktionierende GATT-Verbindung.

## 0.1.0 · 2026-11-21

- Headless-Betrieb: mehrere ausdrücklich freigegebene Proxy-Adressen und systemd-Beispiel. Auf dem DeskPi unter `/klima/` hinter dem vorhandenen Login mit Dashboard-Kachel eingerichtet; Start nach Neustart als normaler Benutzer. Host- und Sandbox-Mountansichten müssen bei der Installation unterschieden werden.

- Portable Linux-Grundversion, Standardbibliotheks-HTTP-Server, Prozesssperre, Start/Stop/Status/Install/Update.
- Lokale responsive Weboberfläche mit eigenem SVG-/ICO-Favicon, ECharts 6.0.0, optionalem `/klima`-Basispfad und Proxy-Origin.
- Validierte Programmeinstellungen mit Save Settings / Load Settings. Keine gesonderte Backupfunktion; Windows zurückgestellt.
- Getrennte synthetische Testdaten, Seed, Szenarien, Monats-CSV, Originalexport und Min/Max-erhaltende Grafikverdichtung.
- Private ioBroker-Vorlagen über bewusst gestartetes lesendes CLI-Werkzeug; keine Gerätekennungen oder echten Vorlagen im Git-Bestand.
- Explizite BLE-Suche und GATT-Inventar als CLI und Webauftrag. Optionale Betriebssystem-Kopplung; kein automatischer Verbindungsaufbau oder Logger-Schreibbefehl.
- Automatisierte Tests für Einstellungen, Dateifehler, CSV, Reproduzierbarkeit, Zeitumstellung, Lücken, Einzelinstanz, HTTP, CSRF und Datenisolation.
- Grenzen: echte BT06-Kommunikation und SMApi-Betrieb noch nicht geprüft; keine produktive Historie, Klimarisikobewertung oder Windows-Version.

Nächster fachlicher Schritt: konkretes BT06-Modell/Firmware identifizieren und Advertising-/GATT-Belege prüfen; daraus Messwertparser und Historienprotokoll ableiten.
