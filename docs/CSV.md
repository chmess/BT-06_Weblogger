# CSV-Vertrag · V0.4.4-dev · Schema 1 (Simulation) und 2 (BLE-Empfang)

Originalformat: UTF-8, Semikolon, Dezimalkomma, LF, Header. Browserexport zusätzlich mit UTF-8-BOM für Excel. Zeitstempel in V0.1 explizit UTC (`+00:00`); Anzeige in konfigurierter Zeitzone. Monatsdateien folgen UTC, daher stabile Dateigrenzen auch bei Sommerzeitwechsel. Leere Batterie/RSSI-Felder bedeuten unbekannt.

V0.4.1-Konfigurationsaufträge: `data/device-settings/changes/<Auftragskennung>.csv` enthält `Hostzeit;Phase;Richtung;DatenHex` für die möglicherweise verändernden Befehle und deren Antworten. UTF-8, Semikolon, UTC mit Offset. TX wird vor dem Senden fsync-gesichert; RX vor der weiteren Verarbeitung. Zugehöriges JSON referenziert reguläre Historien-/Einstellungsstände und den Zustand (`checking`, `writing`, `blocked`, `uncertain`, `verified`). Kein zusätzliches Messdatenarchiv, keine Reset-/Restore-Datei und keine automatische Befehlswiederholung.

| Feld | Bedeutung |
|---|---|
| Schema | `1` |
| DatensatzID | Testprofil-ID und UTC-Sekunde; innerhalb eines Laufs eindeutig |
| Zeitstempel | ISO-8601 mit Offset |
| Temperatur | °C, zwei Dezimalstellen |
| Feuchte | relative Luftfeuchte in %, zwei Dezimalstellen |
| Batterie | leer; nicht erfunden |
| RSSI | leer; nicht erfunden |
| Quelle | `Simulation` |
| Messstelle | stabile synthetische Profil-ID |
| Qualitaet | `SYNTHETISCH` |

```csv
Schema;DatensatzID;Zeitstempel;Temperatur;Feuchte;Batterie;RSSI;Quelle;Messstelle;Qualitaet
1;demo-room-1795215600;2026-11-21T00:00:00+00:00;20,10;57,20;;;Simulation;demo-room;SYNTHETISCH
```

Die Beispielkennung ist illustrativ; der Generator berechnet sie aus dem tatsächlichen Zeitstempel. `manifest.json` dokumentiert Seed, Szenario, Endzeit, Intervall und Messwertanzahl. Private Vorlagenparameter sind nicht im öffentlichen Repository. Simulationen ersetzen keine echten BT06-Historien und liefern keine Geräteidentifikation. Das spätere Echtdatenschema wird nach Protokollprüfung um Geräteindex/Aufnahmeperiode/Originalzeit ergänzt, versioniert und dokumentiert.

## Schema 2: tatsächlicher BLE-Advertising-Empfang

Separate Dateien unter `data/bt06-<id>/<UTC-jahr>/<UTC-monat>.csv`, gleiche ersten zehn Spalten. `Schema=2`, `Quelle=BLE-Advertising`, `Qualitaet=OK` oder `SENSOR_UNGUELTIG`. Unbekannte Sensorwerte bleiben leer; RSSI ist der tatsächliche Empfangswert, `Batterie` bleibt leer. Zusätzliche Spalten: `Batteriespannung` (V), `Firmware`, `Zeitbasis` (`Host-Empfang`), `Aufzeichnungsstatus`, `SpeicherVoll` (0/1). DatensatzID ist eine Host-UUID, **kein** Geräte-Historienindex. Der Zeitstempel dokumentiert die Hostbeobachtung, nicht einen behaupteten Originalmesszeitpunkt im Logger.

Jedes empfangene Paket aktualisiert die Anzeige; dauerhafte Stichproben werden höchstens nach Ablauf des ausdrücklich gewählten Speicherabstands geschrieben. Ein wiederholter Zahlenwert zu einem späteren Empfang ist eine neue Hostbeobachtung. Fehlende Aussendungen werden nicht aufgefüllt. Erfolg wird erst nach fsync bestätigt. Bei unvollständiger Endzeile/abweichendem Header wird das weitere Anhängen blockiert, der Bestand bleibt erhalten und der Fehler erscheint in der Oberfläche. Die Historien-Recovery und Zusammenführung mit Original-Geräteaufzeichnungen gehören zu V0.3.

Fehlende Zeitabschnitte bleiben fehlend. Grafikverdichtung fügt für die Darstellung Nullmarkierungen ein; sie werden nicht in CSV-Originaldaten geschrieben. Zeitbereichsfilter sind an beiden Grenzen inklusiv und verlangen einen Offset. Beschädigte Header oder unvollständige Zeilen erzeugen einen sichtbaren Fehler statt stiller Reparatur. V0.1 liest nur vollständige veröffentlichte Testläufe.


## Schema 3: Loggerhistorie mit ungeprüfter Zeitbasis

`data/history/bt06-<id>/<sha256>/<Gerätejahr>/<Gerätejahr-Gerätemonat>.csv`. Ein Verzeichnis enthält einen vollständig geprüften Historienstand, keine fortlaufende Datensatz-ID des Geräts. Gleicher Inhalt wird wiedererkannt; verschiedene Stände werden getrennt ausgewählt und nicht übereinander geplottet. Noch keine automatische Zusammenführung überlappender Messreihen oder Host-Empfänge.

Erste zehn Felder wie zuvor, danach `GeraeteSekunden;Geraetekalender;Sequenz;RohwerteHex;Zeitbasis;Firmware`. `Schema=3`, `Quelle=BT06-Historie`. `Zeitstempel`, Batterie und RSSI bleiben leer. Es wird kein UTC-Offset erfunden. Der naive Gerätekalender wird aus den unveränderten epochförmigen Geräte-Sekunden dargestellt; dies behauptet keine tatsächliche UTC-Zeit. `Qualitaet=ZEIT_UNGEPRUEFT`, gegebenenfalls zusätzlich `SENSOR_UNGUELTIG`. `Sequenz` identifiziert nur die Position innerhalb des vollständigen Standes; identische Zeiten bleiben erhalten. `RohwerteHex` bewahrt die vier Originalwertebytes.

`capture.csv` bewahrt Original-GATT-Übertragung als `Hostzeit;Richtung;DatenHex`, Hostzeit mit echtem Offset. `manifest.json` enthält ausschließlich abgeleitete Anzahl, Zeitgrenzen, Einheit, Intervall, Firmware, Transportprüfung und Datei-Prüfsummen. Keine Originalmesswerte in JSON. Der Gerätezeit-Chart verwendet intern separate Kalenderkoordinaten; diese werden niemals als verifizierter Zeitstempel exportiert.

CSV-Dateien und Manifest werden vor Veröffentlichung fsync-gesichert; ein exklusiver flock serialisiert Importe auch gegenüber dem Offlinewerkzeug. Atomare Verzeichnisumbenennung veröffentlicht alle Monatsdateien gemeinsam. Nach Abbruch/Schreibfehler bleiben bestehende Stände erhalten. Erneuter Vollimport rekonstruiert einen neuen vollständigen Stand; unveröffentlichte Staging-Dateien werden nicht als erfolgreich angeboten. Beschädigte bestehende Dateien blockieren Lesen und die Bestätigung eines doppelten Imports; keine automatische Reparatur/Überschreibung. Inhaltskennung folgt Firmware, Einheit und geordneter Folge von Rohzeiten/Rohwerten, nicht allein Zeitstempeln.


## V0.3.1: Fortsetzungen und Bereichsübertragung

Schema 3 der Messwerte bleibt unverändert. Die längste exakt passende Folge enthält vorhandene Messungen nur einmal im ausgewählten Verlauf. Frühere Einzelstände und ihre CSV bleiben erhalten; der gemeinsame Verlauf ist eine Auswahl des längsten passenden Standes, keine ungeprüfte Vereinigung nach Zeitstempeln. Raw-Gerätesekunden und Rohwertebytes einschließlich Reihenfolge müssen für ein Präfix identisch sein. Abweichende oder verschobene Reihen bleiben getrennt.

Beim Nachladen enthält `capture.csv` den aktuellen Metadaten-/Bereichstransfer. Die früheren Originalmessungen stammen aus `base_snapshot`; die CSV des resultierenden Standes enthält weiterhin den gesamten unveränderten Bestand plus neue Messungen. Das Manifest ergänzt `transfer_scope=range`, `base_snapshot`, `received_count`, `new_count` und `full_read_verified=false`. Der gesamte aktuell vorhandene Gerätespeicher wurde bei dieser Übertragung **nicht** erneut gelesen. Die Metadaten und 16 Vergleichswerte reduzieren Verwechslungsrisiken, beweisen jedoch keine Unverändertheit aller nicht übertragenen Gerätebereiche.

Auch ein Bereich wird vollständig über Endemarkierung und Anzahl geprüft, bevor er veröffentlicht wird. Die 16 Vergleichswerte müssen bytegenau stimmen und werden nicht doppelt eingefügt. Wiederholte Zeitstempel, Rücksprünge oder uneindeutige Basis verhindern diesen Nachladepfad. Originaldateien werden nicht gelöscht. Aktuell werden vollständige resultierende Monats-CSV-Stände gespeichert; Nachladen spart Funkübertragung, ist noch keine Optimierung des Archivspeicherverbrauchs. Kein automatischer Sync in dieser Entwicklungsfassung.


## V0.3.2: zusätzliche Zeilen und Manifestversion 2

Messwert-CSV bleibt Schema 3. Bei einer Fortsetzung enthalten neue Monatsdateien nur zusätzliche Messungen, nicht erneut die Vergleichswerte oder den ganzen Basisbestand. Sequenznummern setzen die Basis fort, bestehende Datensatz-IDs bleiben beim Rekonstruieren erhalten. Manifestversion 2 beschreibt `storage=delta`, `base_snapshot`, `delta_depth`, Gesamtanzahl und neue Anzahl. Vorhandene Manifestversion 1 wird weiterhin als vollständiger Stand gelesen.

Die Rekonstruktion prüft CSV-Prüfsummen, Sequenzen und Inhaltskennungen jedes benötigten Glieds. Fehlende/beschädigte Basis blockiert Lesen und Bestätigung eines Wiederimports. Spätestens nach 32 Fortsetzungen wird ein vollständiger Zwischenstand geschrieben (`storage=full`, Tiefe 0). Dies begrenzt die Lesekette, bestätigt jedoch keinen neuen vollständigen Geräteabruf. Alte Stände werden nicht gelöscht. Dateiveröffentlichung bleibt atomar mit fsync. Ältere Programmversionen können Manifestversion 2 nicht lesen.

Bestätigte historische Zeitzonen liegen als reine Zuordnung unter `config/history-timezones.json`. Ein optionaler abgeleiteter Export ergänzt drei Spalten: `ZugeordneteZeit` als ISO-8601 mit Offset, `BestaetigteZeitzone`, `Zeitzuordnung=ZEITZONE_BESTAETIGT_DATUM_UNGEPRUEFT`. Original-CSV und Originalfelder werden nicht ersetzt. Eine bestätigte Zeitzone macht ein falsches Gerätedatum nicht richtig. Ungeprüfte spätere Teile bleiben ohne Zusatzzeit; unklare oder fehlende Zeitumstellungsstunden werden nicht geraten.


## V0.4: Einstellungsbelege, getrennt von Messungen

`data/device-settings/bt06-<id>/<zufällige-kennung>.csv` enthält reinen Konfigurations-Leseverkehr mit `Hostzeit;Richtung;DatenHex`. Es enthält keine neu erzeugte Messreihe und ist kein Historienstand. `latest.json` enthält die daraus abgeleiteten Geräteeinstellungen sowie SHA-256, Erfassungszeit und Speicherzeit. Die Erfassungszeit stammt aus dem Original-Capture. Rohbeleg wird vor der Zusammenfassung fsync-gesichert, die Zusammenfassung atomar veröffentlicht. Ein gescheiterter neuer Speicherlauf lässt den bisherigen Beleg erhalten.

Beim Lesen werden Rohdatei-Prüfsumme, erlaubte Lesebefehle, Antworten und daraus erneut abgeleitete Werte gegen die Zusammenfassung geprüft. Bei Widerspruch bleibt das Original erhalten und die Ansicht zeigt einen Fehler. Persönliche Gerätekennungen und reale Einstellungen bleiben außerhalb des öffentlichen Git-Bestands. Zugriffsschlüssel werden nicht ausgelesen oder gespeichert.

## Betriebsereignisse V0.7.1

Ablage `data/events/YYYY/YYYY-MM.csv`, UTF-8, Semikolon, Schema 1. Bewusst innerhalb des bereits freigegebenen Datenverzeichnisses, ohne Änderung der systemd-Schreibpfade. Verzeichnisse privat (700), neue Dateien 600. Originalfelder: `Schema;EreignisID;Zeitstempel;Typ;Stufe;Logger;Quelle;Nachricht;DetailsJSON`. UUID pro Eintrag, Hostzeit in UTC mit Offset; keine Übernahme ungeprüfter Gerätezeit als Ereigniszeit. Details enthalten begrenzte Auftragsmetadaten, keine Rohmessdaten oder Zugangsschlüssel.

Append mit Prozess-/Dateisperre, Header-/Endprüfung, flush/fsync und Verzeichnissynchronisation bei Neuanlage. Leser prüfen Schema und Datensätze. Beschädigte Header, Zeilen oder unvollständige Enden werden nicht still repariert, überschrieben oder übersprungen. Ereignisfehler beeinflussen keine Wiederholung von Geräteaktionen. Fehler beim dauerhaften Bestätigen bleiben in Sitzungsdiagnose und Ereignisanzeige sichtbar; ein fehlgeschlagenes fsync bedeutet nicht zwingend, dass keine Bytes geschrieben wurden. Keine automatische Wiederholung unbestätigter Ereignisse.

Die Anzeige zeigt bis zu 500 neueste passende Einträge je Monatsablage, der CSV-Export alle passenden Originalereignisse in Monats-/Ablagefolge. Bei Hostuhrkorrekturen ist diese Reihenfolge kein Beweis tatsächlicher zeitlicher Reihenfolge. Historische Vorgänge vor Einführung des Protokolls werden nicht rekonstruiert. Kein zusätzliches Backup-System, keine Datenbank, keine automatische Löschung.

## Auswahl- und Klimaexport V0.7.2

Zusätzliche CSV-Kopie, UTF-8-BOM, Semikolon. Der Standardexport ohne neue Parameter bleibt unverändert. Auswahl-Exporte erhalten `ExportSchema=1` und `Exporttyp=Spaltenauswahl` bzw. `AbgeleitetesKlima`; die ursprüngliche Schemaangabe bleibt separat erhalten. Kein Ersatz einer Originaldatei und kein neues Originalmessdatenformat. Reihenfolge der Spalten ist kanonisch nach Quellschema, Exportmetadaten und Berechnungsfeldern.

Quellen-/Zeit-/Qualitätskennzeichnungen sind Pflicht: ursprüngliche Schema-/Datensatzkennung, Zeitstempel, Quelle, Messstelle und Qualität; soweit in der Quelle vorhanden auch Geräte-Sekunden, Gerätekalender, Zeitbasis, Firmware und sämtliche zusätzlichen Zeitzuordnungsfelder. Insbesondere bleibt ein unbekannter UTC-Zeitstempel leer. Ein bestätigter Zeitzonenbezug bestätigt weiterhin kein Gerätedatum.

Optionale berechnete Spalten: `Taupunkt_C`, `AbsoluteFeuchte_g_m3`, `Saettigungsdampfdruck_hPa`, `WasserdampfPartialdruck_hPa`. Vier Nachkommastellen mit Dezimalkomma. Mindestens eine berechnete Spalte bei aktiviertem Klimamodus; `Berechnungsmodell` und `Berechnungsstatus` werden dann immer ergänzt. Ergebnis unbekannt/außerhalb Modell: leeres Zahlenfeld statt Null. Bei gültiger 0-%-Feuchte sind absolute Feuchte und Partialdruck tatsächlich null; Taupunkt bleibt leer. Quellen und Modellgrenzen: [KLIMA.md](KLIMA.md).

Originalwerte bleiben in Originalauflösung und ursprünglicher Textdarstellung. Berechnung erfolgt aus jedem vollständigen Originalpaar, auch wenn die Eingabespalten selbst abgewählt wurden. Keine Ablage der Kopie im Messdatenbestand. Automatische Dateinamen enden auf `_auswahl.csv` bzw. `_klima.csv`.

## Messstellen-ID in neuen Hostwerten V0.8.0

Die bestehende Spalte `Messstelle` enthält für neue, ab Hostzeit zugeordnete BLE-Empfänge die stabile Messstellen-ID. Ohne passende Zuordnung bleibt die bisherige Loggerkennung erhalten. Dateipfad, Zeilen-ID, Empfangszeit und übriges Quellschema unverändert. Bestehende Originaldateien werden nicht rückwirkend umgeschrieben. Historische Namens-/Kriterienauflösung liegt in den Intervallsnapshots unter config/sites.json. Ungeprüfte Gerätehistorie und Simulation werden nicht aus einer aktuellen Hostzuordnung abgeleitet.
