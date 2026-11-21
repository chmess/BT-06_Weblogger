# HTTP-API · V0.2.0

Alle Routen relativ zum konfigurierten Basispfad (z. B. `/klima`). JSON, keine CORS-Freigabe. Host muss zu Loopback-Port oder ausdrücklich konfigurierter Proxy-Origin passen. Alle POSTs benötigen `Content-Type: application/json`, passende `Origin` und `X-CSRF-Token` aus der Sitzung. JSON-Limit 16 KiB. Fehler: `{ "error": "..." }`.

| Methode | Route | Zweck |
|---|---|---|
| GET | `/api/session` | temporäres CSRF-Token |
| GET | `/api/status` | Version, Laufzeit, freier Platz, BLE-Grenzen |
| GET | `/api/settings` | validierte Programmeinstellungen |
| GET | `/api/settings/download` | JSON als Download |
| POST | `/api/settings` | vollständige Programmeinstellungen atomar speichern |
| GET | `/api/runs` | vollständige synthetische Testläufe |
| POST | `/api/simulation` | neuen isolierten Testlauf erzeugen |
| GET | `/api/history?run=...&logger=...&start=...&end=...` | Grafikwerte, Min/Max und Rohanzahl |
| GET | `/api/export?run=...&logger=...&start=...&end=...` | CSV in Originalauflösung |
| GET | `/api/ble` | letzter Diagnoseauftrag, Verfügbarkeit, Adapter |
| POST | `/api/ble` | explizite Suche oder GATT-/Kopplungsprüfung starten |
| GET | `/api/live` | Empfangszustand, Datenalter, letzter Livewert und Schreibstatus |
| GET | `/api/loggers` | lokal vorhandene echte BT06-Datenquellen |
| POST | `/api/live/start` | Advertising-Empfang eines bewusst ausgewählten, verifizierten Kandidaten starten |
| POST | `/api/live/stop` | Host-Empfang pausieren, keine Änderung am Logger |

Simulation: `{ "days": 7, "interval_minutes": 5, "seed": 42, "scenario": "humidity" }`, optional `end` als ISO-8601 mit Offset. Szenarien: `daily`, `humidity`, `ventilation`, `gaps`. Antwort 201 mit Manifest. Paralleler Auftrag: 409. Diagrammwerte: `[epoch_ms, temperatur, feuchte]`; `null` kennzeichnet eine Lücke. `start`/`end` optional, inklusive; Zeitzonenoffset im Query korrekt URL-encodieren.

BLE-Suche: `{ "command": "scan", "adapter": "hci0", "seconds": 10 }` → 202. Poll `/api/ble` bis `done`/`error`. Verbindung nur zu einer zuvor auf demselben Adapter gefundenen Kennung: `{ "command": "gatt", "adapter": "hci0", "seconds": 10, "device": "<aus Suche>", "pair": false }`. Nur `pair: true` fordert eine Betriebssystem-Kopplung an. Keine direkten UUID-/Byte-Schreibschnittstellen. Ein Auftrag gleichzeitig, Timeout begrenzt. Ergebnis bleibt im Arbeitsspeicher und kann private Gerätekennungen enthalten; nicht veröffentlichen.

Echte Daten: `/api/history?source=live&logger=bt06-<id>&start=...&end=...`, Export entsprechend. `source=simulation` ist der abwärtskompatible Standard und benötigt weiterhin `run`. Simulations- und Echtdatenpfade werden nicht miteinander vermischt. Quelle echter Zeilen ist `BLE-Advertising`, Zeitbasis `Host-Empfang`.

Empfangsstart: `{ "device": "<aus letzter Suche>", "adapter": "hci0", "save_interval_seconds": 60 }`. Der Server übernimmt Identität/Firmware aus seinem eigenen verifizierten Suchergebnis, nicht aus vom Browser gelieferten Identitätsfeldern. Leeres `{}` setzt ein bereits bewusst gewähltes Gerät fort. Stop benötigt `{}`. Die Entscheidung wird lokal gespeichert und nach Neustart wieder aufgenommen. Alle POST-Regeln einschließlich CSRF gelten unverändert. Liveempfang und Diagnose teilen eine exklusive Adaptersperre; Konflikte ergeben 409.

Noch nicht implementiert: BT06-Historienprotokoll, Geräteeinstellungen, Messstellenhistorie, Klimaberechnungen, Risikostatistik und dauerhafte Ereignisse. Entsprechende API-Routen werden erst mit verifizierter Funktion eingeführt.
