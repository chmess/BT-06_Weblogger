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

## Zeitabhängige Feuchtephasen (V0.6.1)

Die Feuchteindikatoren sind konfigurierbare Auswertekriterien. Der [UBA-Schimmelleitfaden](https://www.umweltbundesamt.de/system/files/medien/4031/publikationen/240513_uba_fb_schimmelleitfaden_0.pdf) erläutert den Einfluss längerer Oberflächenfeuchte von etwa 70–80 %. Daraus folgt keine universelle feste Mindestdauer. Die Software berechnet weder Schimmelwachstum noch eine Wahrscheinlichkeit und bescheinigt keine Schimmelfreiheit.

Die Oberfläche wird nur auf ausdrücklich gewählte Annahme ausgewertet: konstant eingegebene Temperatur oder Lufttemperatur minus eingegebener Differenz. Keine stillschweigende Wandtemperatur. Modellausreißer lassen den Oberflächenwert unbekannt, auch wenn die Luftfeuchte separat auswertbar ist.

Dauerverfahren aus Originalzeilen, unabhängig von Grafikverdichtung:

- Benachbarte gültige Messpaare zählen nur bei Abstand bis zum 1,5-fachen erwarteten Messintervall. Andere Intervalle sind unbekannt. Ungültige Werte und Lücken beenden eine Phase.
- Zeit ab Schwelle zählt nur Paare, deren beide Endpunkte mindestens die Schwelle erreichen. Das ist eine definierte Modellierung zwischen Stichproben, keine kontinuierliche Messung.
- Eine Phase beginnt am ersten Wert mindestens an der Schwelle. Sie bleibt aktiv bis unter Schwelle minus Hysterese. Phasendauer schließt den Hysteresebereich ein; ein Übergangsintervall zum unterschrittenen Rücksetzwert wird nicht hinzugerechnet.
- Nur Phasen mit modellierter Dauer mindestens der gewählten Mindestdauer qualifizieren sich. Bei Mindestdauer null kann auch ein Einzelwert qualifizieren; eine ausreichende zeitliche Datenabdeckung ist damit nicht belegt.
- Bereichsränder außerhalb vorhandener gültiger Messpaare zählen nicht als bekannte Zeit. Ein Wert allein ergibt keine bekannte Dauer. Beginn/Ende von Phasen an Rändern oder Lücken werden gekennzeichnet.

Berichte nennen Beobachtungszeit, unbekannte Zeit, Zeit ab Schwelle, längste Phase und qualifizierte Phasen. Fehlende Oberflächenannahme bleibt ausdrücklich ohne Bewertung. Es werden höchstens die letzten 100 Phasendetails je Kanal übertragen; Gesamtzähler bleiben vollständig. Geänderte Auswahl kennzeichnet einen vorhandenen Bericht als zum vorherigen Zeitraum gehörend. Kein automatisches Wiederholen und keine dauerhafte Ereignisablage in dieser Version.

Synthetischer Streaming-Test auf dem DeskPi: 43.201 Zeilen in etwa 1,77 s einschließlich Zeilengenerierung, drei Kanäle mit Differenzannahme. 1.080 Luftphasen gezählt, 100 Details übertragen. Keine CSV-/HTTP-/BLE-Leistungsmessung; Laufzeit unter aktueller Systemlast.

## Grundstatistik (V0.7.0)

Min/Max und Stichprobenmittel verwenden alle gültigen Originalwerte des ausgewählten Bereichs. Gültige Stichproben zählen gleich, unabhängig von ihrem zeitlichen Abstand. Das Zeitmittel gewichtet dagegen die lineare Verbindung benachbarter gültiger Messpaare nach deren Dauer. Paare mit mehr als dem 1,5-fachen nominalen Messintervall Abstand oder mit ungültigem Endpunkt werden nicht verbunden; keine Extrapolation über den ersten/letzten Wert hinaus.

Bekannte und unbekannte Zeit werden je Größe ausgewiesen. Eine fehlende Temperatur kann z. B. die Taupunktabdeckung unterbrechen, während die separat vorhandene relative Feuchte weiter auswertbar bleibt. Bei einem Einzelwert ist ein Stichprobenmittel möglich, aber kein Zeitmittel und keine bekannte Paardauer. Größere Zeitlücken zählen nicht als zusätzliche Zeilen; fehlende Zeilenwerte und unbekannte Zeit sind unterschiedliche Kennzahlen.

Taupunkt und absolute Feuchte werden vor der Aggregation aus jedem gültigen Originalpaar berechnet, einschließlich der vorhandenen Modellgrenzen. Die Statistik ist unabhängig von der Grafikverdichtung und beschreibt ausschließlich den ausgewerteten Zeitraum, keine aktuellen oder unbekannten Bedingungen. Keine zusätzliche Messdatenablage.

Synthetischer DeskPi-Test für die Statistik: 43.201 Zeilen in etwa 2,38 s einschließlich Zeilengenerierung; aggregierte Antwort ohne Quellenmetadaten etwa 2,1 KB. Keine CSV-/HTTP-/BLE-Leistungsmessung.
