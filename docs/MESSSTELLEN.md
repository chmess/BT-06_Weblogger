# Messstellen V0.8.4

Messstellen sind lokale Metadaten unter `config/application.json` (bis V0.8.0: `config/sites.json`), keine Geräteeinstellungen. Anlage/Änderung/Zuordnung senden keine BLE-Befehle und ändern keine Geräteuhr. Es werden keine Namen, Räume oder echten Zuordnungen ohne ausdrückliche Eingabe angelegt.

## Bedeutung und Historie

Eine Messstelle besitzt eine stabile `site-<UUID>`-ID, Name, Raum, Beschreibung und validierte Auswertekriterien. Kriterien entsprechen den manuellen Feuchteindikatoren (Luft-/Oberflächenschwelle, Hysterese, Mindestdauer, optionale Oberfläche). Sie lassen sich bewusst in die manuelle Auswertung übernehmen; dadurch werden Datenquelle und Zeitraum nicht automatisch passend gewählt. Seit V0.8.5 nutzt der Host-Monitor die gespeicherten Zuordnungskriterien für neue, erfolgreich gespeicherte Empfänge.

Je Logger und Messstelle ist höchstens eine aktive Zuordnung erlaubt. Zuordnungen haben Host-UTC-Beginn einschließlich, Ende ausschließlich und einen vollständigen Snapshot damaliger Angaben/Kriterien. Loggerwechsel oder Standortwechsel schließen betroffene alte Intervalle und erzeugen ein neues. Änderungen an einer aktiv zugeordneten Messstelle schließen ebenfalls das frühere Metadatenintervall und beginnen eines mit den neuen Angaben; alte Namen/Kriterien bleiben erhalten. Es gibt keine Lösch- oder Rückdatierungsfunktion.

Neue Host-Empfänge werden anhand ihres Empfangszeitpunkts unter der passenden stabilen Messstellen-ID gespeichert. Bereits vorhandene CSV-Zeilen werden nicht neu geschrieben; unzugeordnete Zeilen behalten ihre bisherige Loggerkennung. Dateipfade bleiben loggerbezogen. Eine ungeprüfte Gerätehistorie wird nicht aus ihrem Gerätekalender einer Hostzeit-Zuordnung zugeordnet. Simulation wird nicht an reale Loggerzuordnungen gebunden.

## Grenzen dieser Ausbaustufe

Diagramme, Statistik und Exporte wählen einen Logger und Zeitraum. Bei echten Host-Empfängen lässt sich seit V0.8.2 zusätzlich eine Messstelle wählen. Ohne Filter kann der Bereich mehrere Messstellen umfassen. Der Filter verlangt sowohl die bereits gespeicherte Original-ID als auch das passende damalige Host-Zuordnungsintervall (Beginn einschließlich, Ende ausschließlich). Unzugeordnete Altzeilen werden nicht rückwirkend ergänzt. Berichte nennen die stabile ID, den gewählten Logger und den ausdrücklich aktuellen Messstellennamen. Frühere Namen/Kriterien bleiben in der Zuordnungshistorie nachlesbar. Seit V0.8.4 lässt sich nach Messstellenwahl „Alle Logger dieser Messstelle“ wählen. Gerätehistorienzuordnung bleibt ein weiterer Schritt. Save Settings enthält Messstellen und Historie. Load Settings zeigt Änderungen vorab; Messstellen sind abwählbar. Bestehende Historie wird ergänzt, aktive Loggerbindungen bleiben erhalten. Importierte offene Intervalle enden am Dateistand und werden nicht aktiviert. Änderungen aktueller Angaben gelten erst ab Übernahme, widersprüchliche Historie blockiert den Import.

## Integrität

Änderungen brauchen die aktuelle Konfigurationsrevision. Speichern erfolgt nach vollständiger Validierung per atomarem JSON-Ersatz, Datei privat (600). Bei einem Fehler vor Dateiersatz bleibt der alte Gesamtstand erhalten. Kann ein Fehler erst nach Dateiersatz auftreten (z. B. Verzeichnis-fsync), wird eine gültige sichtbare Gesamtdatei übernommen, jedoch als unbestätigt gemeldet; weitere Änderungen bleiben bis zum Dienstneustart gesperrt. Ungültige bestehende Konfiguration wird nicht automatisch geleert oder repariert. Zeitstempel kommen ausschließlich von der Hostuhr; nicht vorwärts fortgeschrittene Zeit blockiert Zuordnungsänderungen. Die Historie wird nicht zur aktuellen Gerätezeit erklärt.

Gleichzeitige API-Aufträge werden innerhalb des laufenden Prozesses serialisiert; veraltete Revisionen werden abgewiesen. Bis 200 Messstellen und 10.000 Zuordnungsintervalle; Erreichen der Grenze verwirft keine ältere Historie. Die Oberfläche erhält ungespeicherte Entwürfe bei ersetzt vorliegendem Stand und verlangt vor dem Speichern dessen ausdrückliche Übernahme. Zuordnungswechsel zeigen betroffene aktuelle Belegungen vor dem Klick an.

Messstellenaktionen werden im bestehenden privaten Betriebsereignisprotokoll dokumentiert. Kein zusätzlicher Hintergrunddienst, keine Datenbank und kein gesondertes Backup-System.


## Auswertungsgrenzen

Der Filter verwendet einen konsistenten Snapshot der Zuordnungshistorie je Anfrage. Intervallsuche erfolgt binär, Zeilen werden laufend gefiltert; keine zusätzliche vollständige Messdatenkopie für Statistik oder CSV-Filter. Interne Segmentkennungen erscheinen nicht als zusätzliche CSV-Spalten. Original-/Auswahl-/Klima-CSV und Statistikexport verwenden denselben Filter.

Jede Zuordnungsgrenze, auch eine Metadatenversionierung ohne Ortswechsel, unterbricht Kurven und benachbarte Messpaare für Zeitmittel/Feuchtephasen. Beide Grenzpunkte bleiben bei Verdichtung erhalten; dazwischen wird eine sichtbare Kurvenlücke eingefügt. Zeiten ohne gültiges Messpaar bleiben unbekannt. Die Berichtsspanne umfasst weiterhin den angefragten Zeitraum; unzugeordnete Abschnitte werden nicht als unkritisch gezählt. Ohne Messstellenfilter bleiben bisherige loggerbezogene Auswertungen unverändert.

Auswertekriterien stammen weiterhin aus dem manuellen Formular und werden im Bericht ausgewiesen. Auswahl einer Messstelle aktiviert weder ihre aktuellen Kriterien automatisch noch eine historische Kriterienmischung oder eine historische automatische Bewertung. Die Oberfläche erlaubt weiterhin bewusstes Übernehmen aktueller Messstellenkriterien. Simulation und ungeprüfte Gerätezeit bieten keinen Messstellenfilter.


## Loggerwechsel gemeinsam darstellen

Nach Auswahl einer Messstelle steht im Loggerfeld zusätzlich „Alle Logger dieser Messstelle“ bereit. Damit erscheinen frühere und aktuelle Logger im selben Verlauf, derselben Statistik/Feuchteauswertung und im selben CSV. Die damaligen Zuordnungen entscheiden über die Herkunft; es wird keine reale Zuordnung geändert oder angelegt. Der aktuelle Name wird weiterhin ausdrücklich als aktuell bezeichnet, Kriterien bleiben manuell.

Loggerwechsel und sämtliche weiteren Intervallgrenzen bleiben Kurven-/Zeitbewertungsunterbrechungen. Im zusammengeführten CSV ist `Logger` eine zusätzliche Pflichtspalte; einzelne Logger behalten ihren bisherigen Originalexport. Nur relevante Zuordnungen im gewählten Zeitraum werden berücksichtigt, höchstens 64 Logger gleichzeitig. Beim Aufheben des Filters wechselt die Ansicht zurück auf einen einzelnen Logger, unpassende Exportvorbereitungen werden verworfen. Gerätezeit und Simulation bleiben getrennt.
