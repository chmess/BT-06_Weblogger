# BT-06_Weblogger – Entwicklungsauftrag für Codex

Entwickle einen portablen, vollständig lokalen Klimamonitor für schimmelgefährdete Messstellen mit BT06 BLE Temperatur-/Feuchtigkeitslogger. Projektname BT-06_Weblogger (bisheriger Arbeitsname KlimaMonitor_BT06).

Verbindliche Spezifikation: [PROJEKTBESCHREIBUNG.md](PROJEKTBESCHREIBUNG.md). Prioritäten und Versionsplan: [ROADMAP.md](ROADMAP.md). P0 = Muss für Linux V1.0; P1 = Wunsch nach V1.0; P2 = spätere Erweiterung, einschließlich verbindlicher Windows-Portierung. Bei Konflikten hat die Priorisierung in ROADMAP.md Vorrang; Sicherheitsanforderungen bleiben verbindlich.

## Arbeitsregeln
- Linux ist führende Entwicklungsversion; später portable PowerShell-Version aus dieser ableiten. Keine zwei unabhängigen Anwendungen.
- Vorhandenen ESPA-Monitor sofern zugänglich als Architektur- und Bedienreferenz analysieren; kompakte Growbox-Weboberfläche als Gestaltungsreferenz, sofern verfügbar. Referenzprojekte nicht verändern.
- Originalmessdaten ausschließlich in CSV, keine SQLite oder andere Datenbank. Einstellungen JSON. Gemeinsame Weboberfläche und API.
- Stabilität, Messdatensicherheit, verifizierte BLE-Kommunikation und korrekte Klimaberechnung haben Vorrang. Keine Wunschfunktionen vorziehen, keine geratenen Gerätebefehle.
- Keine Konfigurationsänderung oder Speicherlöschung ohne ausdrückliche Nutzeraktion; potenziell destruktive Änderungen nur nach vollständigem verifiziertem Historienbackup und Bestätigung.
- Wiederkehrende Aufgaben möglichst durch wiederverwendbare Skripte automatisieren. Keine unnötigen permanenten Hilfsdienste. Keine unnötigen Root-/Administratorrechte.
- Öffentlicher Quellcode: keine realen Messdaten, Zugangsschlüssel, privaten Referenzquellcode oder persönlichen Gerätekennungen committen. Testdaten synthetisch und getrennt halten.
- Kleine überprüfbare Versionsschritte, Tests, konsistente Versionsangaben, CHANGELOG und offene Punkte pflegen. Keine funktionierenden Bereiche ohne Grund umbauen.
- Hardwaregrenzen und nicht verfügbare Referenzen transparent dokumentieren; keine Testergebnisse vortäuschen.
- V1.0 erst nach Abnahme aller hardwareseitig realisierbaren P0-Funktionen. Prioritätsänderungen mit Auftraggeber abstimmen.

## Erster Auftrag
Lies alle drei Dokumente. Untersuche Herstellerunterlagen und tatsächliche Firmware, prüfe Lizenz und Machbarkeit, analysiere ESPA-Referenz falls verfügbar. Erstelle README, Architektur, CSV-/API-Spezifikation, Protokolldokumentation, Projektstruktur und Skripte. Beginne mit V0.1 und ausschließlich lesender BLE-Diagnose. Keine vorhandenen Loggerdaten oder Einstellungen verändern. Windows-Machbarkeit früh prüfen, Portierung erst nach Linux-Freigabe.
