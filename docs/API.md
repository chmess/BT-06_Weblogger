# HTTP-API · V0.8.3-dev

Alle Routen relativ zum konfigurierten Basispfad (z. B. `/klima`). JSON, keine CORS-Freigabe. Host muss zu Loopback-Port oder ausdrücklich konfigurierter Proxy-Origin passen. Alle POSTs benötigen `Content-Type: application/json`, passende `Origin` und `X-CSRF-Token` aus der Sitzung. JSON-Limit 16 KiB; nur die Einstellungsimport-Vorschau erlaubt 8 MiB plus 8 KiB Hülle. Fehler: `{ "error": "..." }`.

| Methode | Route | Zweck |
|---|---|---|
| GET | `/api/session` | temporäres CSRF-Token |
| GET | `/api/status` | Version, Laufzeit, freier Platz, BLE-Grenzen |
| GET | `/api/settings` | validierte Programmeinstellungen |
| GET | `/api/settings/download` | Gemeinsame Programmeinstellungen/Messstellen als BT06_SETTINGS-Schema 2 |
| POST | `/api/settings` | sieben allgemeine Programmeinstellungsfelder speichern, Messstellen erhalten |
| POST | `/api/settings/preview` | Datei und Änderungen validieren, einmaliges Importtoken erzeugen |
| POST | `/api/settings/apply` | geprüften Import atomar übernehmen |
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

Noch nicht implementiert: bestätigte tatsächliche UTC-Zuordnung, vollständige Gerätekonfiguration, Messstellenhistorie, Klimaberechnungen, Risikostatistik und dauerhafte Ereignisse. Historie/Nachladen, opt-in Automatik und Geräteeinstellungen sind unten beschrieben; unbeaufsichtigter Gerätezugriff und der neue gezielte Schreibweg sind noch nicht am realen Gerät erfolgreich geprüft.


## Manuelle Historie · V0.3.0-dev

- `GET /api/sync`: Zustand `idle/running/done/error`, Phase, empfangene/erwartete Anzahl, Ergebnis und Fehler. Ein Fehler bei Wiederaufnahme des Liveempfangs steht separat in `resume_error`.
- `POST /api/sync` mit `{}`: ausschließlich den eingerichteten BT06 2.05 vollständig lesen. Der Hostempfang wird ohne Änderung des gespeicherten Aktivierungswunsches pausiert und danach wiederhergestellt. Andere BLE-Steuerungen liefern währenddessen 409. Kein Pairing, kein Logger-Start/Stop, keine Zeitänderung. Timeout begrenzt; Fortschritt pollen. Phase `connecting` ist das Signal für das kurze Standard-BLE-Tastenfenster.
- `GET /api/snapshots`: vollständige veröffentlichte Historienstände einschließlich Anzahl, Geräte-Kalendergrenzen, Importzeit, Integritätsinformationen und `clock_verified=false`. Unvollständige `.pending-*` werden nicht angeboten.
- `GET /api/history?source=device&logger=bt06-<id>&snapshot=<Inhaltskennung>`: geprüfte Originalhistorie fürs Diagramm. `axis_basis=device_calendar`, `clock_verified=false`. Numerische Millisekunden sind ausschließlich Kalenderkoordinaten ohne bestätigte UTC-Entsprechung. UI muss sie in UTC formatieren, um die Kalenderfelder unverändert wiederzugeben; **nicht** in der normalen Anzeigezeitzone umrechnen.
- `GET /api/export` mit denselben Identitätsparametern: Schema 3, Originalauflösung, `Zeitstempel` leer, `Geraetekalender` ohne Offset, `GeraeteSekunden` unverändert.

Optionale `start/end` verwenden bei `source=device` dieselben Kalenderkoordinaten (offsetfähiges ISO-Format zur bestehenden API-Kompatibilität; kein Nachweis der realen Zeitzone). Bereich inklusive. CSV gibt weiterhin Originalfelder aus. Bei rückwärts laufender Uhr gibt es einen sichtbaren Diagrammfehler; der ungefilterte Originalexport bleibt möglich. Veränderte Stände werden nicht automatisch zusammengeführt. `duplicate=true` bestätigt einen bereits vorhandenen unveränderten Inhalt nach erneuter Integritätsprüfung.


## Nachladen und fortgesetzte Reihen · V0.3.1-dev

`GET /api/series` bietet pro Logger die längsten exakt belegten Rohdatenfortsetzungen an. `member_ids`/`member_count` nennen die enthaltenen Einzelstände; `separate_series` kennzeichnet mehrere nicht eindeutig zusammenführbare Reihen. `/api/snapshots` bleibt als vollständige Archivauswahl erhalten. Chart und Export verwenden weiterhin die unveränderte Inhaltskennung des gewünschten Standes. Die Auswahl im UI zeigt zuerst gemeinsame Verläufe und danach frühere Einzelstände.

`POST /api/sync` mit `{"mode":"incremental"}` fordert Nachladen an. `{}` oder `{"mode":"full"}` liest weiter vollständig. Nur der bewusst ausgewählte Live-Logger wird verwendet. Existiert genau eine geeignete Reihe mit mindestens 16 Werten und streng aufsteigender Gerätezeit, werden zuerst aktuelle Gesamtmetadaten gelesen und auf kompatible Grenzen, Zähler, Einheit und Intervall geprüft. Bei einer vorab ungeeigneten/veränderten Basis wird vollständig gelesen. Bei einem Widerspruch nach Bereichsübertragung wird abgebrochen und eine Vollauslesung verlangt, nicht still gemischt.

Ergebniszusätze: `last_transfer_scope` (`full/range`) beschreibt den aktuellen Auftrag; `received_count` die tatsächlich übertragenen Messungen einschließlich Vergleichswerten, `new_count` die ergänzten Werte. `count` ist weiterhin die Gesamtzahl im resultierenden Stand. `transfer_scope`, `base_snapshot` und `full_read_verified` dokumentieren die ursprüngliche Herkunft des gespeicherten Standes; sie sind kein Nachweis eines frischen Vollabrufs bei späteren Wiederholungen. Ein Bereichstransfer darf keine destruktive Geräteänderung freigeben. Nachladen ist manuell, kein automatischer Zeitplan.


## V0.3.2: optionale Automatik und historische Zeitzone

`GET /api/autosync` liefert gespeicherte Aktivierung, gebundenes Ziel, Intervall, letzten Versuch/Erfolg, Wartezeit, Fehler und Pausengrund. `POST /api/autosync` mit `{"enabled":false,"interval_minutes":30}` speichert diese Auswahl. Nur 15–1440 ganze Minuten erlaubt; das Ziel stammt ausschließlich aus dem eingerichteten Liveempfang. Aktivierung benötigt einen gewählten Logger und gespeicherten Empfangswunsch. Eine Änderung der Geräteauswahl verhindert Versuche bis zur erneuten bewussten Aktivierung. Ausschalten bleibt während eines Auftrags möglich; der laufende Auftrag endet geordnet. Alle bisherigen Origin-/Host-/CSRF-Regeln gelten.

Automatische Aufträge nutzen `mode=incremental` und `trigger=automatic`. Ohne geeignete Basis oder nach widersprüchlichen Gesamtmetadaten wird nicht automatisch vollständig gelesen. Verbindungsaufbau ist auf ungefähr neun Sekunden begrenzt, gesamte Lesesequenz auf 70 Sekunden zuzüglich begrenzter Trennung. Manuelle Aufträge behalten ihre bisherigen Zeitlimits. Bereits belegtes Bluetooth, pausierter/unfrischer Empfang oder geändertes Ziel verhindern den Start. Fehler verdoppeln die Wartezeit bis sechs Stunden, mindestens jedoch bis zum gewählten Grundintervall. Persistenzfehler pausieren weitere automatische Versuche.

`GET /api/time-assignment?logger=...&snapshot=...` liefert bestätigte Zeitzone, Anzahl zugeordneter/unbestätigter Werte und ausdrücklich `clock_verified=false`, `date_verified=false`. `POST /api/time-assignment` benötigt `logger`, `snapshot`, `timezone` und exakt `timezone_confirmed:true`. Die Bestätigung gilt für den gewählten Stand und exakt passende frühere Präfixe, nicht ungefragt für spätere Messungen oder abweichende Reihen.

`GET /api/export?source=device&logger=...&snapshot=...&time_basis=assigned` ergänzt `ZugeordneteZeit`, `BestaetigteZeitzone`, `Zeitzuordnung`. Originalfelder bleiben erhalten, `Zeitstempel` bleibt leer. Datum ist nicht bestätigt; zugeordnete Kalenderzeiten sind kein Beweis für tatsächliche Messzeitpunkte. Ohne passende Bestätigung wird abgewiesen. Nicht bestätigte spätere Zeilen erhalten leere Zusatzzeit und `BEREICH_NICHT_BESTAETIGT`. Der normale Export bleibt unverändert; Kalenderdiagramme verwenden weiter die ausdrücklich gekennzeichnete Gerätezeitachse.


## V0.4: ausschließlich lesende Geräteeinstellungen

`GET /api/device-settings` liefert `read_only=true` für diesen reinen Lese-/Cachepfad, ob ein Gerät gewählt ist, und den letzten geprüften Einstellungsbeleg oder `settings=null`. GET löst keine Verbindung aus. `POST /api/device-settings/read` mit `{}` startet bewusst die feste Lesesequenz für das eingerichtete Gerät. Fortschritt bleibt unter `/api/sync` (`mode=settings`); Ergebnis ist mit `kind=device-settings` von Messwertimporten getrennt. Abfragekonflikte liefern 409, keine automatischen parallelen BLE-Zugriffe. Konfiguration ist ausschließlich über den unten beschriebenen zweistufigen Pfad möglich.

### Änderungsvorschau ohne Gerätezugriff

`POST /api/device-settings/preview` benötigt `{"base_capture":"<capture aus GET /api/device-settings>","changes":{"broadcast_interval_seconds":1}}`. Kein Client-Gerät/Adapter oder Bytekommando: Auswahl kommt serverseitig aus der Empfangskonfiguration. Nur Firmware 2.05; Originalbeleg wird vor Vergleich wie beim GET anhand CSV und Prüfsumme geprüft. Ersetzter oder zum gewählten Logger unpassender Stand ergibt 400, laufender Leseauftrag 409. CSRF/Origin-Regeln gelten auch für die Vorschau.

Erlaubte Felder: `name` (1–15 UTF-8-Bytes, keine Steuerzeichen oder äußeren Leerzeichen, keine Kürzung), `broadcast_interval_seconds` (0,5–30 s, exakte 0,1-s-Schritte), `transmit_power_dbm` (Ganzzahl aus -20/-16/-12/-8/-4/0/4/6/8), `record_interval_seconds` (Ganzzahl 10–64.800 s als konservativer Implementierungsbereich; tatsächliche Firmwaregrenzen noch nicht abgenommen). Die UI zeigt das Aufzeichnungsintervall in Minuten, die API verwendet ganze Sekunden. Keine Typumwandlung, Rundung oder unbekannten Zusatzfelder. Ein unverändertes Feld erscheint nicht in `changes`; für den gemeinsamen Funkparameterblock müssen beide bisherigen Werte bekannt und plausibel sein. Der nicht bearbeitete Gegenwert wird erhalten.

Antwort `kind=device-settings-preview`: aktuelle Basis und Beobachtungszeit, `changes` mit `field/label/before/after/unit`, optional `broadcast_after`, Hinweise und erforderliche Schutzschritte. **`write_available=false` für die Vorschau immer**; eine Vorschau ist weder Bestätigung noch aktuelle Vollständigkeitsprüfung. Sie startet kein BLE, pausiert keinen Empfang, speichert keine Einstellungen und führt keinen Setter/Save aus. Neu ausgelesene Stände machen einen alten Entwurf ungültig, auch bei identischen Einstellungswerten.

### V0.4.1: expliziter Konfigurationsauftrag (noch kein realer Schreibtest)

`POST /api/device-settings/prepare` nimmt dieselben Optionen wie die Vorschau. Es liest Einstellungen und gesamte Historie in einer GATT-Verbindung, prüft alte/neue Rohparameter und legt beide Originalbelege dauerhaft ab. Unbekannte Nichtnullfelder außerhalb Intervall/Einheit im 15-Byte-Aufzeichnungsblock sperren das Schreiben. Keine Setter bei Vorbereitung. `202`, Fortschritt unter `/api/sync` als `configuration_prepare`; andere BLE-Aufträge/Automatik teilen dieselbe Sperre.

`GET /api/device-settings/configuration` liefert `prepared` oder null, den letzten Auftragsbeleg, `automatic_retry=false` und `reset_available=false`. Eine Vorbereitung enthält konkrete Änderungen, frühere Werte, vollständig gelesenen Historienstand, Folgen, Einmaltoken und Restgültigkeit (maximal zehn Minuten). Gerät/Adresse/Firmware/Adapter und aktueller Einstellungsbeleg sind gebunden. Neustart, Ersetzung, Auswahlwechsel, Ablauf oder `POST /api/device-settings/cancel` mit `{}` verwerfen die Vorbereitung. Cancel verwirft nur eine wartende Vorbereitung; laufende Aufträge lassen sich darüber nicht abbrechen.

`POST /api/device-settings/apply` verlangt exakt `{"token":"<vorbereitet>","confirm_history_loss":true,"confirm_stop":true}`. Boolesche Werte müssen echte `true` sein; keine Zusatzfelder, neuen Werte oder Rohbytes. Beide Bestätigungen schließen möglichen Historienverlust beim Speichern und anschließenden gestoppten Aufzeichnungszustand ein. Token wird einmalig verbraucht, auch bei Timeout oder Startfehler. Ergebnis `202`, Fortschritt `configuration_write`.

Der Auftrag vergleicht aktuelle Einstellungen und Aufzeichnungszustand erneut. Vor dem ersten verändernden Befehl erfolgt immer ein neuer vollständiger, dauerhaft gespeicherter Historienabruf; vorhandene Teilstände genügen nicht. Bei laufender Aufzeichnung: Stop, Status prüfen und vollständige Historie erneut dauerhaft speichern. Dann gestoppten Zustand nochmals prüfen, nur konkrete Änderungen schreiben, alle Parameter vor Save zwischenprüfen und als neuen Beleg sichern, Save/Abschluss ausführen und Einstellungen abschließend zurücklesen. Fremde/ungeänderte Parameter müssen erhalten sein. Leere, widersprüchliche oder unvollständige Historie und Speicherfehler blockieren den nächsten Schritt. Kein Reset, Unlock, Uhrsetzen oder Aufzeichnungsstart.

Erfolg ausschließlich `kind=configuration-verified`. Jeder möglicherweise verändernde Befehl wird **vor dem Senden** dauerhaft protokolliert. Fehler danach: Auftragsbeleg `uncertain`, Zustand neu lesen, keine Wiederholung oder automatischer Rollback. Ein ACK alleine gilt nicht als Gesamterfolg. Vor dem ersten Befehl blockierte Aufträge heißen `blocked`; nach Prozessabbruch wird ein begonnenes Schreiben nicht erneut gestartet. Keine Wiederverwendung eines Tokens. `POST /api/sync` darf diese internen Modi nicht starten. Es gibt keine generische Write-/Save-/Reset-Route.

V0.4.2: Die Zwischenprüfung vor Save akzeptiert bei jedem konkret geänderten Parameterblock exakt dessen Ausgangs- oder Zielbytes. Ein Getter darf vor Commit noch den gespeicherten Ausgangswert zeigen. Ungeänderte Blöcke müssen weiterhin exakt passen; ein dritter Wert verhindert Save. `precommit_visibility` im Auftragsbeleg nennt pro geändertem Block `previous_visible` oder `target_visible`. `staged_settings_capture` wird bereits vor dieser Prüfung dauerhaft gespeichert, auch wenn die Prüfung scheitert. Nach Save/Abschluss müssen alle Zielwerte strikt zurückgelesen sein; ein unveränderter alter Wert ist dann ein Fehler. `stopped_settings_capture` hält den Zustand nach Stop auch bei einer später scheiternden Vollauslesung fest.

### V0.4.3: Status ohne Details und rein lesende Nachprüfung

Ein `4C01`-Payload aus exakt acht Nullbytes ist als `status_variant=zero_summary` bekannt. `recording_code=null`, keine Ableitung eines Stopp-/Aufnahmezustands oder Historienzählers. Andere neue Längen/Inhalte bleiben ungültig. Ein solcher Zustand erlaubt keine neue Vorbereitung/Schreibfreigabe; nur nach Commit darf die reine Parameterprüfung unabhängig davon erfolgreich sein: `kind=configuration-parameters-verified`, Auftragsstatus `parameters_verified`, `recording_state_verified=false`. Ein bewiesener Stopp bleibt separat `configuration-verified`/`verified`. Alter Zielwert nach Save ist weiterhin Fehler.

`POST /api/device-settings/verify` mit exakt `{}` startet `configuration_verify` unter der gemeinsamen Sperre. Keine neuen Zielwerte, Tokens oder Frames zulässig. Zulässiger Ausgang ist ein passender unklarer/parameterbestätigter Auftrag mit vollständigen, positiven Setter-/Save-/Abschlussantworten, ursprünglichem Zwischenbeleg und prüfbaren vollständigen Historienreferenzen. Fehlende/widersprüchliche ACKs, beschädigte Referenzen und andere Geräte blockieren vor einem BLE-Auftrag. Es werden keine Setter, Save, Stop, Start oder Reset gesendet.

Falls der letzte geprüfte Einstellungsbeleg zeitlich nach dem belegten Abschluss liegt und alle Ziel-/Gegenwerte strikt bestätigt, wird ausschließlich dieser Originalbeleg verwendet: `verification_source=stored_postcommit_capture`. Andernfalls neue lesende Verbindung mit fester Getterliste (`fresh_read`). `verification_observed_at` kennzeichnet den Zeitpunkt des Originalbelegs; es ist keine Garantie gegen spätere externe Änderungen. Erfolg ergänzt `reconciled_read_only=true` und den Bestätigungszeitpunkt im bestehenden Auftrags-JSON. Ursprüngliche Schreib-CSV und Messdaten werden nicht geändert. Der Modus ist nicht über `/api/sync` aufrufbar.

Zusammenfassungen vor Dekoderversion 2 mit diesem bisher unbekannten Nullstatus werden nur dann als abgeleitete Ansicht aktualisiert, wenn CSV-Prüfsumme und sämtliche alten Zusammenfassungsfelder exakt zum Original passen. GET schreibt dabei keine Dateien. Änderungen anderer Werte oder unbekannte Dekoderversionen werden weiterhin abgewiesen.

Die Zusammenfassung zeigt nur belegte Felder. Abgewiesene Antworten stehen in `read_errors`, unbekannte Formate in `decode_errors`. `unverified` kennzeichnet noch nicht belegte Parameter. `transmit_rate_code` ist ein Rohcode, `long_range=null`; keine geratene Bool-Zuordnung. Gerätezeitfelder sind ungeprüft, keine automatische Jahres-/UTC-Korrektur. Name, Intervalle und Hardware-Alarme sind keine Programmeinstellungen oder Software-Klimagrenzen.

Für fehlende ungekoppelte BlueZ-Einträge gibt es eine frische Suche am ausgewählten Adapter, beschränkt auf Adresse, Gerätekennung und verifiziertes Firmwareformat. Automatische Verbindungen zu vorhandenen Einträgen warten bis 35 Sekunden; nach frischer Entdeckung acht Sekunden. Gesamtlimit bleibt begrenzt; dies ist kein Nachweis eines zuverlässig connectablen Gerätemodus.


## V0.4.4: Aufzeichnungsstart

`GET /api/recording`: wartende Vorbereitung und letzter Startauftrag. `POST /api/recording/prepare` mit `{}` liest Einstellungen und den gesamten Historienumfang. Nichtleere Historie wird vollständig geprüft gespeichert; Leerstand erfordert exakt zehn Nullbytes aus der vollständigen Historienauswahl, separat mit Rohbeleg gespeichert. Acht Statusnullbytes sind kein Leerstandsnachweis. Bereits aktive Aufnahme/Startverzögerung, unbekannte Zustände oder widersprüchliche Daten blockieren.

`POST /api/recording/start` verlangt exakt `{"token":"<Vorbereitung>","confirm_history_loss":true,"confirm_start":true}`. Gerät/Adapter/Firmware, letzter Einstellungsbeleg, Zustand und Umfang müssen passen; Token maximal zehn Minuten und einmalig. Vor dem einzigen `52A0` werden aktuelle Originale nochmals dauerhaft gesichert. Keine Parameter-/Uhränderung, Stop-, Save- oder Resetfolge. Aktiver Zustand 16 ergibt `recording-started`; ACK ohne Aufnahmenachweis bleibt `recording-start-pending`. Fehler nach Sendeversuch bleiben unklar, niemals automatisch wiederholen.

`POST /api/recording/verify` mit `{}` prüft ausschließlich lesend. Vollständiger Sicherungs-/Leerstandsbeleg und gesendeter Startframe müssen vorliegen. Ein frischer Advertising-Übergang von initialisiert/gestoppt zu Aufnahme nach dem Sende-/Antwortzeitpunkt kann mit unveränderten nachgelesenen Parametern bestätigen; andernfalls neue Getterverbindung. Auch ein verlorener ACK berechtigt nie zu einem erneuten Start. `POST /api/recording/cancel` mit `{}` verwirft nur wartende Vorbereitungen. Alle POSTs: Origin/CSRF und gemeinsame BLE-Sperre. Interne Modi `recording_prepare/start/verify` sind nicht über `/api/sync` zugänglich. Originale unter `data/recording/`; keine zusätzlichen Messdatenbackups.

## V0.4.6: ausdrücklich bestätigter unbekannter Gerätebestand

`POST /api/recording/prepare` kann alternativ exakt `{"allow_unread_history_loss":true}` erhalten. Nur im Initialzustand und bei unverändertem Nullstatus, exakt belegter Umfangsablehnung `266c000323` und bereits geprüfter vollständiger Alt-CSV wird ein unbekannter Bestand akzeptiert. `protection.count` bleibt `null`, `archived_reference` benennt den gesicherten Altbestand. Start benötigt zusätzlich `confirm_unread_history_loss:true`. Normale Vorbereitung bleibt strikt; Zeitüberschreitung, andere Fehler oder fehlendes Archiv sperren weiterhin. Einmaliger Start, keine automatische Wiederholung.

`GET /api/device-settings` ergänzt `memory_estimate`: nominelle Kapazität 32.000 Werte, rechnerische Sekunden/Tage aus ausgelesenem Intervall, `remaining_seconds:null`. Keine Aussage über aktuellen Füllstand oder Batteriehaltbarkeit.

## V0.4.7: Temperatureinheit

Die Änderungsvorschau und Konfigurationsvorbereitung akzeptieren zusätzlich `temperature_unit` mit exakt `"C"` oder `"F"`. Vorschau ergänzt `logging_after` mit Einheit und Intervall; bei Änderungen müssen beide Ausgangswerte verifiziert sein. Gemeinsamer Setter für Einheit/Intervall, alle anderen Rohfelder bleiben erhalten. Unbekannte Zusatzfelder blockieren weiterhin. Bestehende Historienprüfung, Bestätigungen, Stopp, Save/Abschluss und striktes Rücklesen gelten unverändert. Kein automatischer Aufzeichnungsstart. Archivierte Daten behalten ihre ursprüngliche Einheit und normalisierte Celsiuswerte.

## V0.4.8: Alarmgrenzen und Aktivierung

Vorschau/Vorbereitung unterstützen flache Änderungsfelder nach dem Muster `temperature_alarm_low_limit`, `temperature_alarm_high_limit`, `temperature_alarm_low_enabled`, `temperature_alarm_high_enabled`; entsprechend `humidity_alarm_…`. Aktivierung verlangt JSON-Bool, Grenzen exakte 0,1-Schritte. Temperaturbereich -20 bis 60 °C, Feuchte 0 bis 100 % rF, Untergrenze strikt kleiner als Obergrenze. Unveränderte Gegenwerte werden aus dem vollständig gelesenen Alarmblock übernommen, niemals durch Defaults ersetzt. Temperaturänderungen benötigen ausgelesenes C und dürfen keinen Wechsel nach F enthalten; Feuchteänderungen sind auch bei F möglich. Typcodes und Verzögerung sind nicht über diese Felder änderbar. Die gespeicherte Werteantwort bleibt strukturiert (`temperature_alarm`/`humidity_alarm`, jeweils `low`/`high`); Originalbelege werden nicht umgeschrieben. Bestehender Schutzablauf unverändert.

## V0.5.0: Diagrammzeitraum

Keine neue API. Die Oberfläche nutzt die vorhandenen `start`/`end`-Filter für Vor-/Zurücknavigation und den Export des sichtbaren Zoomfensters. Export bleibt in Originalauflösung, unabhängig von der Grafikverdichtung. Gerätehistorien verwenden weiterhin ungeprüfte Kalenderkoordinaten für Bereichsfilter und exportieren originale Gerätesekunden; dadurch entsteht keine neue UTC-/Zeitzonenbestätigung. Die zusätzliche Exportfunktion mit bestätigter Zeitzuordnung bleibt separat.

## V0.5.1: browserlokale Diagrammansichten

Keine neue API und keine Änderung am Programmeinstellungs-JSON. Achsen und gespeicherte Ansichten werden im Browser verwaltet, getrennt nach tatsächlicher Quelle und Logger sowie Testlauf oder Historienstand. Höchstens 20 Ansichten; Speichern einer weiteren entfernt den ältesten anderen Eintrag. Gespeichert werden exakte Bereichszeitpunkte, prozentualer Zoom, Achsengrenzen und Kurvenauswahl. Laden verwendet die bestehenden Historienfilter und pausiert Live-Follow; keine Änderung der Originalwerte oder ihrer Zeitzuordnung. Ansichten werden ausdrücklich geladen, nicht automatisch auf andere Datenstände übertragen. Temperaturdarstellungsgrenzen liegen aus technischen Gründen zwischen −1000 und 1000 °C, Feuchte zwischen 0 und 100 %; dies sind Diagramm-, keine Sensorgrenzen.

## V0.6.0: berechnetes Klima

`POST /api/climate/calculate` mit exakt `temperature_c`, `humidity_pct`, `surface_temperature_c` (Zahl oder `null` für die Oberfläche). Origin und Sitzungstoken wie bei anderen POSTs erforderlich; rein rechnend, keine Datei-/BLE-Aktion. Strikte endliche Zahlen, keine Bool-/Textkonvertierung, Luft/Oberfläche −45 bis +60 °C, rF 0 bis 100 %. Ergebnis: Modell und Eingaben, Taupunkt, absolute Feuchte, Sättigungs-/Partialdruck, 70-/80-%-Oberflächentemperaturen, rechnerische Oberflächen-rF, Taupunktabstand und optionale Kondensationsbedingung. Nicht verfügbare Größen sind `null`, niemals NaN oder ein erfundener Taupunkt.

`GET /api/history` ergänzt `climate`: Modell, letzter abgeleiteter Wert, Min/Max-Taupunkt und `points` als `[Zeitkoordinate, Taupunkt_C, absolute_Feuchte_g_m3]`. Zeitkoordinaten sind exakt mit den bisherigen Grafikpunkten ausgerichtet. Ableitungen entstehen aus Originalpaaren vor Verdichtung; bestehende `points`, `latest` und Original-CSV bleiben in ihrem bisherigen Format. `GET /api/live` ergänzt `latest_climate` für exakt die mitgelieferte aktuelle Aussendung; deren Datenalter bleibt separat im bisherigen Status. Modellgrenzen/Quellen: [KLIMA.md](KLIMA.md).

## V0.6.1: Feuchtephasen aus Originalzeilen

`GET /api/risk` verwendet dieselben Quellen-/Logger-/Lauf-/Historienstand- und Zeitraumparameter wie `/api/history`, zusätzlich genau diese Kriterien: `air_threshold`, `surface_threshold` (je >0 bis 100 %), `hysteresis` (≥0 und kleiner als beide Schwellen), `minimum_minutes` (0 bis 43.200), `surface_mode` (`none`, `fixed`, `delta`) und `surface_value` (bei none leer; fixed −45 bis +60 °C, delta 0 bis 50 K). Beispielzusatz: `&air_threshold=70&surface_threshold=80&hysteresis=2&minimum_minutes=60&surface_mode=none&surface_value=`. Unbekannte/mehrfache Parameter und ungültige Zahlen werden abgewiesen. Kein Zugriff auf Bluetooth und keine Dateischreibaktion.

Die Antwort enthält Quellen-/Zeitbasis, Kriterien, exakten Bereich und die Berichte `air`, `surface`, `condensation`. Ohne Annahme sind die letzten beiden `null`. Je Bericht: Schwelle/Rücksetzgrenze, Mindestdauer, auswertbare Messpaarzeit, unbekannte Zeit, Abdeckung, Zeit ab Schwelle, gültige/ungültige Stichproben, gesamte/qualifizierte Phasen und längste Phase. `phases` enthält höchstens die letzten 100 Details mit Zeitkoordinaten, Dauer, Spitze, Qualifikation und Randkennzeichnung; `omitted_phases` nennt ausgelassene Details. Status `insufficient_data`, `incomplete` oder `evaluated` bewertet ausschließlich die Datenabdeckung, keine Schimmelfreiheit.

Details zu Paarintervallen, Hysterese, Bereichsrändern und Kondensationsmodell: [KLIMA.md](KLIMA.md). Gerätehistorien behalten ungeprüfte Kalenderkoordinaten; die Auswertung bestätigt weder Datum noch UTC-Offset.

## V0.7.0: Grundstatistik

`GET /api/statistics` akzeptiert dieselben Quellen-/Logger-/Lauf-/Historienstand- und Zeitraumparameter wie `/api/history`, keine Feuchtekriterien oder abgeleitete Zeitbasis. Berechnung aus Originalzeilen, nicht Grafikpunkten. Keine Schreib- oder BLE-Aktion.

Antwort: Quellen-/Zeitbasis, Modell, Originalzeilenanzahl, nominales Intervall, Anzahl größerer Zeitlücken, größter Stichprobenabstand, genauer Bereich und `metrics` für `temperature_c`, `humidity_pct`, `dew_point_c`, `absolute_humidity_g_m3`. Je Größe: gültige/fehlende Zeilenwerte, Minimum/Maximum mit Zeitpunkt, `sample_mean`, `time_weighted_mean`, letzter gültiger Wert, bekannte/unbekannte Sekunden, Abdeckung und Status. Ohne benachbarte gültige Messpaare bleibt Zeitmittel `null`, auch bei einem gültigen Einzelwert. Zeitgewichtung linear zwischen gültigen Endpunkten, maximal 1,5 nominale Intervalle Abstand. Bereichsränder außerhalb gültiger Messpaare sind unbekannt. Ursprüngliche Gerätezeit bleibt ungeprüft.

Die Statistikseite bindet den vorhandenen Original-CSV-Export an exakt dieselbe Berichtsabfrage. Geänderte Ansicht kennzeichnet einen bestehenden Bericht; Export bleibt explizit dem alten Bericht zugeordnet. Noch kein Export der statistischen Zusammenfassung und keine zusätzliche Datenablage.

## V0.7.1: Betriebsereignisse

`GET /api/events`: optionale Filter `start`, `end` (ISO mit Offset, Hostzeit), `logger`, `type`, `level` (`info`, `warning`, `error`), `limit` (1–500, Standard 100). Unbekannte/mehrfache Filter werden abgewiesen. Antwort: Originalereignisse, `truncated`, Typbezeichnungen und `log_status` mit Fehler/Bestätigungszählern dieser Sitzung. Begrenzte Anzeige behauptet keine vollständige Trefferzahl. `GET /api/events/export` akzeptiert dieselben Filter außer limit und exportiert sämtliche passenden Originaleinträge als UTF-8-BOM-CSV. Keine freie Schreib-API für Ereignisse.

`GET /api/status` ergänzt `event_log` mit derselben Sitzungsdiagnose. Ereignisprotokollierung ist fehlertoleranter Nebenkanal: fehlgeschlagene Ereignisablage darf weder Messwertspeicherung noch Auftragsabschluss-/Scheduler-Callback verhindern.

Automatische Typen: Dienststart/-ende, Hostempfang gestartet/pausiert, erste/wieder aktuelle Aussendung, nach gültigem Empfang über 90 Sekunden veraltetes Advertising, Fehler/Erholung, beobachteter Aufzeichnungsstatus und Speichervollkennzeichnung sowie abgeschlossene/fehlgeschlagene Aufträge. Advertising-Frische ist keine GATT-Verbindung; veraltete Aussendung kein Gerätestopp. Interne Pausen erzeugen keinen Verlustalarm. Aufhebung der Speichervollkennzeichnung behauptet keinen leeren Speicher. Abgeschlossener Auftrag bedeutet nicht automatisch aktive Aufnahme; unbestätigter Start wird als Warnung protokolliert.

Die Ereignisseite verwendet ausschließlich Hostzeitfilter und ist von der globalen Simulations-/Historienauswahl getrennt. CSV enthält auch Detailsmetadaten; die normale Tabelle zeigt verständliche Meldungen. Automatische zeitabhängige Klima-/Batteriewarnungen sind in dieser Version noch nicht angebunden.

## V0.7.2: Exportoptionen und Klimakopie

`GET /api/export/options` akzeptiert dieselbe Quellauswahl/Zeitraumfilterung wie der Originalexport, optional dessen bestätigte separate Zeitzuordnung. Liefert Originalspalten, Pflichtspalten, Export-/Berechnungsmetadaten, berechnete Spaltenbezeichnungen und Modell. Die Vorschau erzeugt noch keine CSV-Kopie und keine Klimaberechnung. Quelle, Bereich und gegebenenfalls der bestehende Zeitzuordnungsnachweis werden geprüft.

`GET /api/export` ergänzt optional `fields` als kommaseparierte Spaltennamen und `climate=1`. Andere climate-Werte, unbekannte/doppelte/leere Spaltennamen und berechnete Spalten ohne Klimamodus werden abgewiesen. Ohne fields im Klimamodus: alle Originalspalten und berechneten Größen. Mit fields: gewählte Spalten plus verpflichtende Metadaten; mindestens eine berechnete Größe bei climate=1. Bestehende Originalexports ohne diese Parameter bleiben bytegleich. Details der Spalten und Kennzeichnung: [CSV.md](CSV.md).

Die neue Exportseite verwendet gewählten Zeitraum, sichtbaren Ausschnitt oder exakt die Abfrage des Statistikberichts. Abweichende Quellen-/Loggerauswahl verlangt neue Vorbereitung. Das vorbereitete Zeitfenster bleibt fest; zusätzliche Klimagrößen werden bewusst gewählt. Downloads werden per gleicher Origin abgerufen, Fehler als Meldung behandelt und erfolgreiche Antworten als lokale Browser-Blobs heruntergeladen. Die bestehende Sicherheitsrichtlinie wurde dafür nicht erweitert.

## V0.8.0: Messstellen

`GET /api/sites`: Revision, aktuelle Messstellen, aktive Zuordnungen, gesamte Intervallanzahl und bekannte Logger. Keine Filter. `GET /api/sites/assignments`: optionale Filter `logger`, `site_id`, `limit` (1–500, Standard 100), neueste Intervalle zuerst mit `truncated`-Hinweis.

`POST /api/sites/save`: exakt `{revision,id,values}`; id `null` für neue Messstelle, sonst vorhandene stabile ID. values enthält exakt `name`, `room`, `description`, `criteria`. Kriterien entsprechen den sechs Feldern der Feuchteauswertung. Namen bis 80, Raum bis 80, Beschreibung bis 2.000 Zeichen. Keine äußeren Leerzeichen/Steuerzeichen; Beschreibung darf interne Zeilenumbrüche enthalten.

`POST /api/sites/assign`: exakt `{revision,logger,site_id}`. Logger muss verifiziert bekannt sein; site_id ist vorhandene Messstelle oder `null` zum Beenden. Keine rückdatierbaren Zeitparameter. Änderungen gelten ab erzeugter Hostzeit; bestehende Belegungen von Logger/Zielmessstelle werden geschlossen, historische Snapshots bleiben bestehen. Beide POSTs erfordern gleiche Origin und Sitzungstoken; keine Bluetooth-Steuerung.

Konfigurationsschema, Integrität und aktuelle Auswertungsgrenzen: [MESSSTELLEN.md](MESSSTELLEN.md). Betriebsereignisse ergänzen `site.created`, `site.updated`, `site.assigned`, `site.unassigned`.


## Gemeinsame Einstellungen V0.8.1

Download: `{format:"BT06_SETTINGS",schema_version:2,exported_at:<Host-ISO-Zeit>,settings:<bisherige sieben Felder>,sites:<vollständige Messstellenregistratur>}`. GET `/api/settings` bleibt unverändert. Alte reine Einstellungsdateien bleiben gültig. Empfang, Autosync, Zugangsschlüssel und Geräteparameter sind nicht Bestandteil dieses Imports.

Vorschau-POST: `{document:<Dateiobjekt>,include_sites:<bool>,settings:<sieben Formularfelder>}`. Die Formularwerte dürfen die Dateiwerte bewusst überschreiben. Antwort enthält `token`, Ablaufzeit, Einstellungs-/Messstellenänderungen und Zähler. Keine Speicherung. Ein Token gilt einmalig für zehn Minuten und die aktuelle globale Konfigurationsrevision; eine neue Vorschau ersetzt es. Apply-POST: `{token:<Token>}`; Antwort ist der neue gemeinsame Exportstand. Beide POSTs unterliegen dem bestehenden CSRF-/Origin-Schutz.

Messstellenimport ergänzt Historie, entfernt keine vorhandenen Intervalle und bewahrt aktuelle Loggerbindungen. Offene importierte Intervalle werden am Dateistand geschlossen, nie aktiviert. Geänderte Metadaten einer aktuell belegten Messstelle werden erst zum Übernahmezeitpunkt versioniert. Widersprüche/Überlappungen blockieren den Messstellenimport; reine Programmeinstellungen können separat geladen werden. Dateizeit nach Hostzeit blockiert den Messstellenimport.

Gemeinsame Ablage `config/application.json`, maximal 8 MiB, private Datei und atomarer Ersatz. Ohne diese Datei werden alte `settings.json`/`sites.json` eingelesen; die erste Änderung erzeugt den gemeinsamen Stand. Danach sind Altdateien nicht maßgeblich. Beschädigte gemeinsame Dateien werden nicht durch Altstände ersetzt. `/api/status.configuration` meldet Ablage, Revision und Schreibfehler. Nach unbestätigtem Schreibabschluss folgt der Prozess einer gültigen sichtbaren Gesamtdatei, meldet den Fehler und sperrt weitere Änderungen bis zum Neustart. Kein automatischer Retry/Rollback.


## Messstellenfilter V0.8.2

Optionaler Queryparameter `site=site-<UUID>` für `/api/history`, `/api/statistics`, `/api/risk`, `/api/export` und `/api/export/options`, ausschließlich mit `source=live` und weiterhin erforderlichem `logger`. Unbekannte/ungültige IDs oder mehrfache Parameter werden abgewiesen. Ohne `site` bleibt die bestehende Strecke unverändert.

Der Filter verwendet Original-Messstellen-ID UND historisches Host-Zuordnungsintervall. Anfang einschließlich, Ende ausschließlich; keine nachträgliche Umzuordnung von Altzeilen. JSON-Berichte ergänzen `site_selection` mit `site_id`, `current_name` (ausdrücklich aktueller Name), `logger`, Messstellen-`revision`, `assignment_intervals`, `basis=stored_id_and_host_assignment`, `criteria_automatic=false`. Keine passenden Zeilen ergibt einen regulären leeren Bericht.

Zuordnungsgrenzen unterbrechen Grafiklinien, Zeitmittel und Feuchtephasen unabhängig vom zeitlichen Abstand; in Phasendetails heißt der Abschluss `assignment_boundary`. Statistik-`gap_count` zählt bei gefilterten Daten auch Zuordnungsgrenzen zwischen ausgewerteten Zeilen. Die bisherige Berichtsspanne/Abdeckungsdefinition bleibt erhalten. Kriterien bleiben explizite API-Eingaben. CSV enthält ausschließlich die originalen Zeilen bzw. ausdrücklich gewählten Ableitungen, keine internen Segmentspalten. Dateinamen ergänzen die stabile Messstellen-ID. Mehrere Logger werden in dieser Version nicht zusammengeführt.


## Empfangsdateidiagnose V0.8.3

`GET /api/diagnostics/storage` ohne Parameter startet eine rein lesende Prüfung nativer Hostdateien unter `data/bt06-<Kennung>/<Jahr>/*.csv`. Bestehender Hostschutz, kein CORS. Unbekannte Parameter: 400; weitere Prüfung während eines laufenden Auftrags: 409. Keine BLE-Kommunikation, automatische Wiederholung oder Reparatur. Die Oberfläche ruft diesen Endpunkt nur auf ausdrücklichen Klick auf, nicht im Aktualisierungstakt.

Antwort enthält `scope=host_csv_only`, Host-Prüfzeit `checked_at`, `state` (`empty`, `ok`, `partial`, `error`), `complete`, `files_checked`, `rows_checked`, `bytes_checked`, `elapsed_seconds`, `limits`, `errors` und `skipped`. Fehler/übersprungene Dateien nennen nur relative Pfade und feste Ursachen, keine Originalwerte oder absoluten Hostpfade. `complete` bezeichnet das Abarbeiten des erfassten Umfangs, nicht die Fehlerfreiheit; bei `state=error` liegt auch bei abgeschlossenem Durchlauf ein Befund vor. Zeilenzähler zählen bis dahin erfolgreich validierte Zeilen, Dateizähler nur vollständig validierte Dateien; Bytes zählen berücksichtigte Dateigrößen.

Prüft pro Datei Schema/Kopf, vollständigen Dateischluss, Spaltenzahl, Schema 2/Advertising/Hostzeitbasis, gültigen Offsetzeitstempel im Dateimonat, streng aufsteigende Zeitfolge, nicht leere/eindeutige Datensatzkennungen und endliche Temperatur-/Feuchtewerte (Feuchte 0–100, fehlende Werte zulässig). Nur ein gemeinsamer nicht blockierender Leselock je Datei; wird geschrieben, bleibt sie übersprungen. Keine zeitübergreifende Transaktionssicht sämtlicher Dateien. Symbolische Links werden nicht gelesen, Zugriffsfehler nicht als leerer Bestand gewertet.

Limits: 100 Dateien, 32 MiB, 250.000 Zeilen, 10.000 Verzeichniseinträge, etwa fünf Sekunden. Erreichte Grenzen ergeben Teilprüfung; kein stilles Auslassen mit Erfolgsbehauptung. Blockierende Betriebssystemzugriffe können die Zeitgrenze überschreiten. Die Prüfung ersetzt weder Historien-Vollständigkeitsbelege noch eine Prüfung von Historienarchiven, Simulation, Ereignis-CSV oder geräteseitiger Messrichtigkeit.
