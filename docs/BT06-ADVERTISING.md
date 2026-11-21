# BT06 Advertising · verifiziertes Datenlayout 2.05

Primärquelle: öffentliche Herstellerreferenz [TZONE-Team/BTLogger-Android, SDK](https://github.com/TZONE-Team/BTLogger-Android/tree/master/SDK). Untersuchte JAR-Prüfsumme SHA-256: `782db6dace718b82fba3ac009a8e0d419a5299639935557ddddd4b38545afe7d`. Die lokalen SDK-Dateien und statischen Analysedateien werden nicht ausgeliefert. Es wurden Datenformat-Fakten dokumentiert und ein eigener Decoder geschrieben, kein SDK-Implementierungscode übernommen. Wiederverwendungslizenz des SDK weiterhin ungeklärt.

Bleak liefert Manufacturer Data als Dictionary. Der Schlüssel `0xFF23` entspricht den ersten beiden On-Air-Bytes `23 FF`; diese Bytes gehören bei Bleak **nicht** mehr zum Payload. Alle folgenden Offsets beziehen sich auf diesen Bleak-Payload.

| Byteoffset | Bedeutung |
|---|---|
| 0 | Modelltyp `09`: BT06 |
| 1–2 | hier unterstütztes Firmwareformat `02 05`, Anzeige 2.05 |
| 4–7 | achtstellige Kennung als Ziffernfolge aus vier Hex-Bytes |
| 11 | Spannung in V: `(Byte + 200) / 100` |
| 12, Bits 0–1 | 0 initialisiert, 1 Startverzögerung, 2 Aufzeichnung, 3 gestoppt |
| 12, Bit 2 | Speicher voll |
| 12, Bits 4–5 | Sperrstufe |
| 13, Bits 0–1 / 2–3 | Temperatur- / Feuchtealarm, jeweils 0 keiner, 1 hoch, 2 niedrig, 3 beide |
| 14, Bits 0–1 | 0 Celsius, 1 Fahrenheit, 3 Sensor deaktiviert; 2 nicht unterstützt |
| 15–16 | Temperatur, Little Endian, Vorzeichen/Betrag, Zehntel |
| 17–18 | relative Feuchte, Little Endian, Vorzeichen/Betrag, Zehntel |

Das höchstwertige Bit des 16-Bit-Werts ist ein Vorzeichenbit, kein Zweierkomplement. Das obere Byte `FE` wird als fehlender Messwert behandelt. Deaktivierte, fehlende oder unplausible Werte bleiben leer bzw. `null`. Eine Fahrenheit-Anzeige wird für die Anwendung nach Celsius umgerechnet. Aus einer Spannung wird **keine** prozentuale Batterieladung erfunden.

Unbekannte Modell-/Firmwarelayouts werden abgewiesen. Nur das belegte 2.05-Layout ist freigegeben; keine Vermutung anhand eines ähnlichen Gerätenamens. Der Empfänger prüft zusätzlich die bewusst gewählte BLE-Adresse und die im Paket enthaltene stabile Kennung. Geänderte Kennung, unbekannte Firmware oder fremde Geräte werden nicht gespeichert.

## Zeitbasis und Abnahme

Ein Advertising-Empfang enthält hier keinen verifizierten Original-Messzeitstempel oder Historienindex. CSV-Zeitbasis ist deshalb ausdrücklich `Host-Empfang`, Quelle `BLE-Advertising`. Der wählbare CSV-Speicherabstand betrifft nur den Host. Die Aufzeichnungseinstellung im BT06 wird nicht verändert. Wiederholte Pakete aktualisieren den Livezustand, werden aber innerhalb dieses Abstands nicht erneut als CSV-Stichprobe gespeichert.

Der Decoder wurde anhand synthetischer Testvektoren (negative Temperaturen, Fahrenheit, Sensorfehler, Statusbits, falsche Identität/Firmware) und eines real empfangenen BT06-2.05-Pakets geprüft. Ein realer Empfang wurde mit fsync dauerhaft in einer privaten Prüfdatei gespeichert. Das belegt den Empfangs-/Dekodier-/Speicherweg, keine metrologische Kalibrierung oder erfolgreiche GATT-/Historienkommunikation.
