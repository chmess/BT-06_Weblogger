# HTTP-API · V0.4.4-dev

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
