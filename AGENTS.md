# BT-06_Weblogger – Entwicklungsauftrag für Codex

Entwickle einen portablen, vollständig lokalen Klimamonitor für schimmelgefährdete Messstellen mit BT06 BLE Temperatur-/Feuchtigkeitslogger. Projektname BT-06_Weblogger (bisheriger Arbeitsname KlimaMonitor_BT06).

Verbindliche Spezifikation: [PROJEKTBESCHREIBUNG.md](PROJEKTBESCHREIBUNG.md). Prioritäten und Versionsplan: [ROADMAP.md](ROADMAP.md). P0 = Muss für Linux V1.0; P1 = Wunsch nach V1.0; P2 = spätere Erweiterung. Windows erst behandeln, wenn Linux funktioniert. Bei Konflikten hat die Priorisierung in ROADMAP.md Vorrang; ausdrückliche Benutzeranweisungen haben Vorrang.

## Bestätigte Anpassungen vom 21.11.2026
- Windows-Umsetzung und Machbarkeitsprüfung vollständig zurückstellen.
- Kein gesondertes Backup-/Restore-System. Programmeinstellungen per Save Settings / Load Settings als JSON sichern und laden.
- Am 22.11.2026 bestätigt der Nutzer, dass alle Daten gesichert sind, und autorisiert ausdrücklich das Wiederherstellen der Werkseinstellungen. Kein bloßer Aufzeichnungsneustart als Ersatz. Nur belegte Herstellerprozedur verwenden; aktuell kein verifizierter Werksreset implementiert.
- Am 22.11.2026 anschließend bestätigt: ohne Werksreset fortfahren. Einmaliger Aufzeichnungsstart mit 25 Minuten trotz unbekanntem aktuellem Gerätebestand und möglichem Verlust verbliebener Gerätedaten ausdrücklich freigegeben; gesicherte Originalhistorie erhalten. Geräteuhr darf bei belegtem Verfahren aktuell gesetzt werden. Keine geratenen Uhrbefehle.
- Potenziell destruktive Geräteänderungen weiterhin nicht automatisch ausführen. Vorher Historie regulär auslesen und Vollständigkeit prüfen; kein zusätzlicher Backupdienst oder doppeltes Archiv nötig.
- Testdaten reproduzierbar generieren. Private Zigbee-Geräte können lokale Vorlagen liefern; Kennungen und Parameter bleiben unter `private/`, generierte Daten unter `simulation/`. Keine dieser Dateien veröffentlichen.
- SMApi-Verträglichkeit berücksichtigen: sparsame Laufzeit, getrennte Umgebung, gemeinsamer Bluetooth-Adapter als zu prüfende Ressource. Keine ungefragte Installation auf SMApi.

## Arbeitsregeln
- Tests nach Änderungsumfang auswählen: standardmäßig nur betroffene Funktionen und Schnittstellen prüfen. Gesamtsuite bei breiten Änderungen, gemeinsamen Kernfunktionen oder vor größeren Freigaben; vollständige Browserprüfung nur bei entsprechend breiten UI-Änderungen. Bestehende Tests behalten, keine unnötigen neuen Tests oder Wiederholungen. Sicherheits- und Datenintegritätsprüfungen nicht auslassen.
- Linux ist führende Entwicklungsversion; Windows bleibt bis zur funktionierenden Linux-Version zurückgestellt.
- Vorhandenen ESPA-Monitor sofern zugänglich als Architektur- und Bedienreferenz analysieren; kompakte Growbox-Weboberfläche als Gestaltungsreferenz, sofern verfügbar. Referenzprojekte nicht verändern.
- Originalmessdaten ausschließlich in CSV, keine SQLite oder andere Datenbank. Einstellungen JSON. Gemeinsame Weboberfläche und API.
- Stabilität, Messdatensicherheit, verifizierte BLE-Kommunikation und korrekte Klimaberechnung haben Vorrang. Keine Wunschfunktionen vorziehen, keine geratenen Gerätebefehle.
- Keine Logger-Konfigurationsänderung oder Speicherlöschung ohne ausdrückliche Nutzeraktion; potenziell destruktive Änderungen erst nach vollständigem verifiziertem Historienauslesen und Bestätigung.
- Wiederkehrende Aufgaben möglichst durch wiederverwendbare Skripte automatisieren. Keine unnötigen permanenten Hilfsdienste. Keine unnötigen Root-/Administratorrechte.
- Öffentlicher Quellcode: keine realen Messdaten, Zugangsschlüssel, privaten Referenzquellcode oder persönlichen Gerätekennungen committen. Testdaten synthetisch und getrennt halten.
- Kleine überprüfbare Versionsschritte, Tests, konsistente Versionsangaben, CHANGELOG und offene Punkte pflegen. Keine funktionierenden Bereiche ohne Grund umbauen.
- Hardwaregrenzen und nicht verfügbare Referenzen transparent dokumentieren; keine Testergebnisse vortäuschen.
- V1.0 erst nach Abnahme aller hardwareseitig realisierbaren P0-Funktionen. Prioritätsänderungen mit Auftraggeber abstimmen.

## Erster Auftrag
Lies alle drei Dokumente. Untersuche Herstellerunterlagen und tatsächliche Firmware, prüfe Lizenz und Machbarkeit, analysiere ESPA-Referenz falls verfügbar. Erstelle README, Architektur, CSV-/API-Spezifikation, Protokolldokumentation, Projektstruktur und Skripte. Beginne mit V0.1 und BLE-Diagnose ohne Logger-Schreibbefehle. Keine vorhandenen Loggerdaten oder Einstellungen verändern. Betriebssystem-Kopplung nur auf ausdrücklichen Klick/CLI-Option. Aktuellen Stand und Hardwaregrenzen in README und CHANGELOG dokumentieren.
