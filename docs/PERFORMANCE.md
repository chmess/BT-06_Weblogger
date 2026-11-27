# Performanceabnahme · erster Schritt V0.9.0

Messung am DeskPi am 27.11.2026, aarch64, Python 3.13.5. Kein Paket installiert, keine Logger-/Systemkonfiguration geändert. Alle Lastdaten sind synthetisch und entstehen ausschließlich in einem automatisch entfernten temporären Verzeichnis. Lokale JSON-Berichte unter `test-results/` bleiben außerhalb des Repositorys.

## Laufender Dienst

V0.8.7, zehn Sekunden Beobachtung ohne zusätzlich erzeugte HTTP-Last: 33,19 MiB RSS/Spitzen-RSS, 0,9 % eines CPU-Kerns und drei Threads. Momentaufnahme des realen Dienstes, keine Aussage über Tageslast, andere Rechner oder V0.9 nach Aktivierung. Beim anfänglichen Statusabruf keine Konfigurations-/Ereignisfehler.

## Eine Million Originalzeilen im isolierten Funktionsbenchmark

Deterministischer CSV-Bestand: 1.000.000 Zeilen, 96.888.482 Bytes, eine Minute Abstand, fehlende Temperaturwerte und eine Zeitlücke. Frische Prozesse seriell, warmer Dateibestand im temporären Speicher; höchstens 768 MiB virtueller Speicher und 120 CPU-Sekunden je Prozess. Gemessen werden CSV-Lesen, Verarbeitung und Ergebnisaufbereitung, keine tatsächlichen HTTP-Transfers oder Browserzeichnungen. Spitzen-RSS umfasst jeweils den gesamten Worker einschließlich Python.

| Vorgang | Laufzeit | Spitzen-RSS | Ergebnis |
|---|---:|---:|---|
| Diagramm vorher, V0.8.7 | 41,237 s | 309,6 MiB | 1.396 Grafikpunkte |
| Diagramm V0.9.0 | 36,923 s | 57,2 MiB | dieselben 1.396 Grafikpunkte |
| Statistik, unveränderter Algorithmus | 51,115 s | 19,9 MiB | 1.000.000 Originalzeilen |
| Feuchteauswertung, unveränderter Algorithmus | 28,422 s | 19,9 MiB | 1.000.000 Originalzeilen |
| Original-CSV aufbereiten, unverändert | 25,707 s | 294,9 MiB | 96.888.485 Bytes mit BOM |

Diagramm: etwa 10,5 % kürzere Laufzeit und 81,5 % geringeres Spitzen-RSS. Jeder Wert ist ein einzelner Lauf, keine statistisch abgesicherte Verteilung. Nebenlast, Cache und Taktregelung können Laufzeiten beeinflussen. Eingabedatei und normalisierte vollständige Diagrammantwort haben vor/nach Änderung identische SHA256-Prüfsummen. Die Verdichtung erhält dieselben Extrempunkte, fehlenden Werte und Lücken; Original-CSV wird nicht verändert. Modellgrenzen behalten auch ihre bisherige JSON-Zahlendarstellung.

Der Speichergewinn entsteht durch kompakte Zeit-/Wertspalten statt einer Python-Liste pro Messpunkt. Min/Max werden aus den vorhandenen Verdichtungsblöcken übernommen, ohne zusätzliche vollständige Datenkopie. Das Verfahren hält weiterhin Spalten für den gesamten abgefragten Bestand; es ist keine unbegrenzt speicherkonstante Diagrammverarbeitung.

## Begrenzung zusätzlicher Last

Die vorhandene periodische Hauptaktualisierung im Browser startet erst eine neue Runde, wenn die vorige beendet ist. Das verhindert eine Auftragskette bei langsamer Antwort. Nach einem Fehler wird die Laufzeitsperre freigegeben; Aktualisierungsintervall und Pause in unsichtbaren Tabs bleiben erhalten. Manuelle Benutzerabfragen und separate Auftragsanzeigen sind dadurch nicht generell serialisiert.

## Noch offen

- 37 Sekunden für eine Million Zeilen sind für interaktives Nachladen weiterhin zu lang. Monats-/Zeitbereichsauswahl begrenzt kleinere Abfragen, ersetzt aber keine weitere Optimierung großer Zeiträume.
- Statistik und Feuchteanalyse laufen mit geringem RAM, benötigen für große Bereiche jedoch erhebliche CPU-Zeit. Unveränderte Bereiche wurden nach der Diagrammänderung nicht erneut gemessen.
- Der bestehende CSV-Download puffert die fertige Ausgabe; sein hoher RAM-Verbrauch bleibt offen. Ein künftiger Streaming-/Spool-Pfad muss unvollständige Downloads zuverlässig kennzeichnen und Originalbytes erhalten.
- HTTP-Gleichzeitigkeit, Browserreaktion, kalte Datenträgerzugriffe, große reale Historienketten, Wiederanlauf und längerfristiger Betrieb stehen noch aus.
- Keine Messung oder Installation auf SMApi; dessen CPU/RAM und gemeinsamer Bluetooth-Adapter brauchen eine eigene Prüfung.
- V1.0 ist damit nicht abgenommen.

## Reproduzieren

```sh
python3 tools/benchmark_large.py --rows 1000000 --output test-results/benchmark-large.json
python3 tools/benchmark_large.py --rows 1000000 --modes chart --output test-results/benchmark-chart.json
node tools/check_background_refresh.mjs
```

Der Benchmark erzeugt ungefähr 93 MiB temporäre CSV und prüft vorher den freien Platz. Seine Berichte enthalten nur künstliche Daten/technische Aggregate. Der Vorher-Lauf entstand gegen den damaligen V0.8.7-Code; die obigen Befehle messen jeweils den aktuell vorliegenden Quellstand. Keine Notwendigkeit, den laufenden Dienst für den isolierten Werkzeuglauf anzuhalten.
