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
| Original-CSV aufbereiten, V0.9.0 | 25,707 s | 294,9 MiB | 96.888.485 Bytes mit BOM |

Diagramm: etwa 10,5 % kürzere Laufzeit und 81,5 % geringeres Spitzen-RSS. Jeder Wert ist ein einzelner Lauf, keine statistisch abgesicherte Verteilung. Nebenlast, Cache und Taktregelung können Laufzeiten beeinflussen. Eingabedatei und normalisierte vollständige Diagrammantwort haben vor/nach Änderung identische SHA256-Prüfsummen. Die Verdichtung erhält dieselben Extrempunkte, fehlenden Werte und Lücken; Original-CSV wird nicht verändert. Modellgrenzen behalten auch ihre bisherige JSON-Zahlendarstellung.

Der Speichergewinn entsteht durch kompakte Zeit-/Wertspalten statt einer Python-Liste pro Messpunkt. Min/Max werden aus den vorhandenen Verdichtungsblöcken übernommen, ohne zusätzliche vollständige Datenkopie. Das Verfahren hält weiterhin Spalten für den gesamten abgefragten Bestand; es ist keine unbegrenzt speicherkonstante Diagrammverarbeitung.

## Begrenzung zusätzlicher Last

Die vorhandene periodische Hauptaktualisierung im Browser startet erst eine neue Runde, wenn die vorige beendet ist. Das verhindert eine Auftragskette bei langsamer Antwort. Nach einem Fehler wird die Laufzeitsperre freigegeben; Aktualisierungsintervall und Pause in unsichtbaren Tabs bleiben erhalten. Manuelle Benutzerabfragen und separate Auftragsanzeigen sind dadurch nicht generell serialisiert.

## Noch offen

- 37 Sekunden für eine Million Zeilen sind für interaktives Nachladen weiterhin zu lang. Monats-/Zeitbereichsauswahl begrenzt kleinere Abfragen, ersetzt aber keine weitere Optimierung großer Zeiträume.
- Statistik und Feuchteanalyse laufen mit geringem RAM, benötigen für große Bereiche jedoch erhebliche CPU-Zeit. Unveränderte Bereiche wurden nach der Diagrammänderung nicht erneut gemessen.
- Der V0.9.0-CSV-Download puffert die fertige Ausgabe. V0.9.1 ersetzt diesen Weg wie unten beschrieben; reale Datenträger-/HTTP-Last und Speicherbedarf der jeweiligen Quelldaten bleiben zu prüfen.
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


## CSV-Vorbereitung V0.9.1

Derselbe Million-Zeilen-Bestand und dieselbe Dateilänge einschließlich BOM (96.888.485 Bytes):

| Verfahren | Laufzeit | Spitzen-RSS |
|---|---:|---:|
| Bisheriger String-/Bytepuffer | 25,707 s | 294,9 MiB |
| Private temporäre Datei und blockweises Lesen | 27,647 s | 19,8 MiB |

93,3 % weniger Spitzen-RSS, dafür in diesem Einzellauf rund 7,5 % bzw. 1,94 Sekunden längere Vorbereitung/Weiterverarbeitung. Gleicher Eingabebestand und identische CSV-Inhaltsprüfsumme; UTF-8-BOM und Länge zusätzlich geprüft. Kein schnellerer Export behauptet. Eine Million Zeilen bleiben eine merkliche Wartezeit.

Der Vergleich verwendet den temporären Speicher unter `/tmp` (tmpfs). Der tatsächliche Dienst verwendet eine automatisch entfernte Datei unter `runtime` auf der vorhandenen ext4-Ablage; diese Schreibfreigabe ist bereits vorhanden. Reale SSD-Schreib-/Lesekosten und HTTP-Transfer wurden nicht gemessen. Dateisystemcache und tmpfs-Dateiinhalte belegen zusätzlich Speicher außerhalb des Worker-RSS. Die Verbesserung bezieht sich daher auf Prozess-RAM und vermeidbare vollständige String-/Bytekopien, nicht auf entsprechend gesunkenen gesamten System-RAM.

Maximal 256 MiB pro CSV und ein CSV-Auftrag gleichzeitig begrenzen die zusätzliche temporäre Last. Die 64-MiB-Reserve wird beim Start und ungefähr je MiB nachgeführt, ist aber keine Reservierung gegenüber anderen Anwendungen. Größere Datenbereiche müssen aufgeteilt werden. Quellendatenströme schließen vor der Übertragung; die temporäre Datei schließt auch bei Abbruch.

```sh
python3 tools/benchmark_large.py --rows 1000000 --modes spooled_export --output test-results/benchmark-spooled-export.json
```

Der unveränderte Modus `export` bleibt als Vergleich des früheren Ausgabeverfahrens verfügbar. Im API-Dienst wird er für CSV-Downloads nicht mehr verwendet.
