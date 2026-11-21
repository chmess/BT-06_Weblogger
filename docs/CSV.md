# CSV-Vertrag · V0.2.0 · Schema 1 (Simulation) und 2 (BLE-Empfang)

Originalformat: UTF-8, Semikolon, Dezimalkomma, LF, Header. Browserexport zusätzlich mit UTF-8-BOM für Excel. Zeitstempel in V0.1 explizit UTC (`+00:00`); Anzeige in konfigurierter Zeitzone. Monatsdateien folgen UTC, daher stabile Dateigrenzen auch bei Sommerzeitwechsel. Leere Batterie/RSSI-Felder bedeuten unbekannt.

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
