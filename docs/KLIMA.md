# Klimaberechnungen V0.6.0

Berechnete Größen sind von Originalmessungen getrennt. Es gibt keine neue Messdatenablage und keine Änderung der Geräteuhr. Eingaben in °C und % relativer Feuchte, Ausgaben ausdrücklich mit Einheit.

## Modell und Quellen

Magnus-Näherung über flüssigem Wasser:

- Sättigungsdampfdruck `es = 6,112 × exp(17,62 × T / (243,12 + T))` in hPa.
- Partialdruck `e = es × rF / 100`.
- Taupunkt `Td = 243,12 × ln(e / 6,112) / (17,62 − ln(e / 6,112))` in °C.
- Absolute Feuchte `216,679 × e / (T + 273,15)` in g/m³.

Koeffizienten und empfohlener Bereich −45 bis +60 °C: [Universität Hamburg, Wettermast-Datenbeschreibung, A.10](https://wettermast.uni-hamburg.de/Downloads/Wettermast_Datenbeschreibung.pdf). Absolute Feuchte nach idealer Gasgleichung: [Vaisala HMP155, Calculation formulas](https://docs.vaisala.com/r/M210912EN-J/en-US/GUID-8F8C9ECE-FFD9-4F6F-9F11-D94CF9122735).

Keine Druckkorrektur und kein Frostpunktmodell. Eingaben sowie invertierte Temperaturen außerhalb des Modellbereichs werden nicht extrapoliert. Bei 0 % rF sind Partialdruck und absolute Feuchte null, ein endlicher Taupunkt ist nicht definiert. Fehlende/ungültige Messwerte bleiben unbekannt.

## Oberflächenannahme

Gleicher Wasserdampf-Partialdruck an Luft und Oberfläche wird angenommen. Rechnerische Oberflächen-rF ist `100 × e / es(Ts)`. Oberhalb 100 % bezeichnet sie die Bedingung vor Kondensation; die Anzeige nennt ≥100 % und keine physisch dauerhaft übersättigte Oberfläche. Die 70-/80-%-Temperaturen entstehen durch Invertieren von `es = e / 0,7` beziehungsweise `e / 0,8`. Taupunktabstand: `Ts − Td`.

Oberflächentemperaturen sind manuelle Annahmen. Ohne Eingabe bleiben Oberflächenfeuchte, Abstand und Kondensationsaussage unbekannt. Die Momentaufnahme liefert keine zeitabhängige Schimmelbewertung oder Schimmelwahrscheinlichkeit. Dauer, Material, Unsicherheit, Feuchtetransport und zeitliche Lücken sind damit nicht bewertet.

## Darstellung und Performance

Taupunkt nutzt die °C-Achse des Klimaverlaufs. Originalpunkte und CSV-Export bleiben unverändert; ein zusätzlicher abgeleiteter Antwortbereich enthält Taupunkt und absolute Feuchte. Berechnung vor der Verdichtung, Extremwerterhalt für alle vier Größen, Lücken auch in der Taupunktkurve. Ursprüngliche dreispaltige Punktantwort bleibt erhalten.

Synthetischer DeskPi-Lauf: 43.201 Originalwerte, 1.087 Grafikpunkte, etwa 2,52 s inklusive CSV-Lesen; Prozessspitze etwa 34 MiB inklusive Testdatenerzeugung und Export. Separater Vergleich derselben 43.201 Speicherzeilen: vorher etwa 0,54 s, mit Klimaberechnung etwa 1,07 s. Einzelmessungen unter vorhandener Systemlast, keine SMApi- oder BLE-Leistungsmessung.
