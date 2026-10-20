# Textmodell Version 3 – lokale Umsetzung und direkte Rahmenbearbeitung

Stand: 20.10.2026. Branch `feature/textmodell-v3`, Basis `main` bei
`4735a16d53a16ada52b8cb5bb580c96e07e73be6` nach PR #8.
Keine Änderungen auf main, kein Commit, Push, Merge, Workflow-Start, Drive-Abgleich
oder Deployment durch diese Umsetzung. Ursprüngliches Repository nicht bearbeitet.

## Bedienung und Umfang

Neue Entwürfe verwenden Version 3. Die Rahmenbreite, Rahmenhöhe und Schriftgrösse
lassen sich unabhängig über beschriftete Zahlenfelder ändern; dazu Position,
Drehung und links-/zentriert-/rechtsbündige Ausrichtung. Ungültige Eingaben werden
mit Hinweis auf den letzten gültigen Wert zurückgesetzt. Ein Wert ändert keine
anderen Grössen automatisch. Maus-/Touch-Verschiebung, Drehgriff und Tastatur
bleiben verfügbar. In der anschliessend freigegebenen Phase wurden acht
Rahmenvergrösserungsgriffe ergänzt (siehe unten); es gibt keinen v3-Textskalierungsgriff.
V1-/V2-Entwürfe verwenden ihre bisherigen Renderer und werden nicht umgestellt.

Der eingegebene Text bleibt unverändert gespeichert. Automatische Umbrüche
entstehen aus der tatsächlichen Innenbreite; bei breiteren Rahmen fallen sie
wieder weg. Enter, Leerzeilen und ein letzter manueller Zeilenumbruch bleiben
erhalten. Lange Wörter können umbrechen. Es gibt kein neues Zeichenlimit und
keine automatische Schriftverkleinerung.

Editor, Designmappe und Vergleich verwenden denselben v3-Renderer. Der
Auswahlrahmen wird als Outline gezeichnet und verbraucht keinen Platz. Bei
420 Einheiten Rahmenbreite und 12 Einheiten Innenabstand bleiben daher überall
396 Einheiten Textbreite. Die bisherige CSS-Regel `font-size:40px!important`
ist auf alte Textobjekte beschränkt. V2 bleibt in seiner bestehenden Geometrie
(392 im Editor / 396 in schreibgeschützter Vorschau); dies wird ohne Migration
nicht heimlich verändert. Die V1-Autoumstellung auf V2 beim Öffnen entfällt,
weil diese Etappe ausdrücklich keine Migration umfasst.

Ein einfacher Platzstatus erscheint ausserhalb der beschnittenen Fläche, auch
in Mappe/Vergleich: Text passt nicht in den Rahmen oder ein gedrehter Rahmen
ragt über die Gestaltungsfläche. Speichern bleibt zum späteren Korrigieren möglich;
der vollständige Text bleibt erhalten. Das ist keine Produktions-/Gravurfreigabe
und ersetzt keine spätere Prüfung tatsächlicher Produktmasse und Gravurbereiche.

## Datenmodell und Schutz alter Entwürfe

Ein v3-Entwurf besitzt `textFrame` mit Mittelpunkt x/y, Breite, Höhe, Schriftgrösse,
Drehung, Ausrichtung, Innenabstand und Zeilenhöhenfaktor. Alle Längen beziehen sich
auf das unveränderte 600×600-Koordinatensystem. Es gibt keinen Objekt-`scale` und
keinen zusätzlichen `transform`-Block. Nur die gesamte Gestaltungsfläche wird auf
die Bildschirmbreite skaliert. Innenabstand und Zeilenhöhe werden mitgespeichert,
in dieser Etappe aber nicht als weitere Bedienelemente angeboten.

Finite Zahlen, erlaubte Wertebereiche und Ausrichtung werden strikt geprüft.
Zusätzlicher Scale, ungültige Rahmen und unbekannte Layoutversionen sperren die
betroffene Mappe gegen Überschreiben; die Rohdaten bleiben erhalten. Editieren
und Duplizieren verwenden eigenständige Rahmenkopien.

Der Storage-Key `timberart-designmappe-v1` bleibt. Die äussere Speicherversion ist
bisher 1 und wird erst beim Speichern eines v3-Entwurfs auf 2 gesetzt. Der neue
Reader akzeptiert beide Speicherversionen und Layouts 1/2/3; alte gespeicherte
Entwürfe werden beim Lesen oder Abbrechen nicht umgeschrieben. Gemischte Mappen
bleiben möglich. Die bisherigen Epoch-/Mehrfenster-/Schreibkonflikt-Prüfungen
bleiben erhalten. Alte App-Versionen können die neue äussere Speicherversion
nicht lesen und sperren daher ihre normalen Schreibwege; ein Rollback muss
diese fehlende Lesbarkeit neuer v3-Mappen berücksichtigen. Keine automatische
Löschung, Migration oder Umbenennung der bestehenden Daten.

## Tatsächlich ausgeführte Prüfungen

```sh
node tests/text_frame_check.js
python3 -B tests/text_frame_browser_check.py
python3 -B tests/browser_check.py
python3 -B tests/transform_check.py
python3 -B tests/selection_check.py
python3 -B tests/sync_categories_browser_check.py
python3 -B tests/order_safety_check.py
python3 -B tests/local_images_check.py
python3 -B tests/drive_sync_check.py
python3 -B -m unittest discover -s tests -p 'import_check.py'
python3 -B tests/drive_connection_check.py
python3 -B tools/sync_motifs.py --validate
node --check personal.js
node --check transform.js
node --check text-frame.js
git diff --check
```

Sechs neue Node-Modelltests bestanden: unabhängige Abmessungen/Schriftgrösse,
strikte Validierung, exakter Werte-Roundtrip, Kopien und Drehgeometrie.
51 bestehende Python-Tests bestanden (37 Sync/Workflow, 8 Import, 6 Verbindung).
Alle sechs bisherigen Browser-Skripte und das neue v3-Skript bestanden.
Maus-/Touch-Tests in Chromium bei 1440/820/390 px; externe HTTPS-Aufrufe blockiert.
Legacy-Transformations-/Auswahltests starten nun ausdrücklich mit V2-Testdaten,
damit ihre bisherigen Skalierungs-, Drehungs- und Auswahlverträge erhalten bleiben.
Der bisherige V1-Migrationstest prüft jetzt das ausdrücklich verlangte Nichtmigrieren.

Neu geprüft wurden insbesondere:

- Unabhängige Zahlenfelder, automatische Umbrüche und Wiederzusammenführung.
- Tatsächliche Enter-Tasten, Leerzeilen, letzter Zeilenumbruch und lange Wörter.
- Alle Ausrichtungen; gleiche Textinnenbreite, Zeilenhöhe, Schriftgrösse und
  Transformation in Editor, Mappe und Vergleich sowie nach Neuladen.
- Auswahl ohne Layoutänderung; echte Maus-/Touch-Verschiebung und 45°-Drehung,
  Gestenabbruch, Tastaturbedienung und gespeicherte Rotation.
- Unveränderter Rohtext, sämtliche Rahmenwerte, unabhängige Duplikate,
  Platzwarnungen auch in gespeicherten Vorschauen, gemischte V1/V2/V3-Mappen.
- Öffnen/Abbrechen alter Entwürfe ohne Speicherschreibzugriff; Editieren eines
  V2-Entwurfs erhält V1 und V3 im selben Speicher unverändert.
- Beschädigte Rahmen, doppelte Skalierungsmodelle, unbekannte Versionen und
  falsche Speicherhüllen werden ohne Überschreiben abgefangen.
- Verzögert geladene Schrift mit lokalem DejaVu-Testfont als Ersatz für Montserrat:
  Werte bleiben erhalten, Platzprüfung und Status werden erneut berechnet.
  Dies prüft keine echte Google-Fonts-Auslieferung oder die echten 30 Schriftbilder.

Ein zunächst fehlgeschlagener neuer Drehungstest verwendete noch laufendes
Smooth-Scrolling für seine Messposition. Nach explizit sofortiger Positionierung
bestand der Test in allen drei Grössen; die zunächst vermutete Produktursache
wurde nicht bestätigt und die dafür versuchte Produktänderung zurückgenommen.

Zusätzlich Desktop-/Smartphone-Oberfläche anhand lokaler Screenshots betrachtet.
Screenshots und Testdaten liegen ausschliesslich ausserhalb des Repositorys.

## Regressionen, Grenzen und nächste Etappen

Gegenüber Basis-main unverändert: beide Actions-Workflows einschliesslich aktivem
Stundenplan, Importercode, Quellen/Ausschlüsse, Katalog, Herkunftsmanifest,
Kategorien und sämtliche Motivdateien. Validator: 412 Motive, 824 referenzierte
WebPs, 177.108.798 Bytes. Alle 824 Dateien per HTTP unter Pages-Unterpfad geladen
und im Browser decodiert; alte Entwürfe/Favoriten wiederhergestellt. Beide gefüllten
Bestellformulare: keine Requests/fetch/XHR/Beacon, native Übermittlung auch ohne
App-JavaScript durch unveränderte CSP gesperrt. 30 Schriftdefinitionen erhalten.

Keine echte Google-Verbindung und kein Actions-Lauf ausgeführt. Keine physischen
Geräte, Safari-/Firefox-Prüfung, Laserdateierzeugung oder Produktionsfreigabe.
Eine fehlende Originalschrift wird weiterhin angezeigt; Ersatzschriften können
anders umbrechen. Pixelgleiche Schriftkantenglättung zwischen Plattformen wird
nicht versprochen. Die Grundwarnung betrachtet Rahmen und DOM-Textausdehnung,
keine detaillierte Laser-/Glyphenkonturprüfung bei Zierschriften.

Die kontrollierte Migration alter Entwürfe bleibt ausdrücklich nicht umgesetzt.
Die nächste freigegebene Phase der direkten Rahmenbearbeitung ist unten beschrieben.


## Nächste freigegebene Phase: direkte Textrahmenbearbeitung

Weiterhin ausschliesslich lokal auf `feature/textmodell-v3`, unveränderter
HEAD `4735a16d53a16ada52b8cb5bb580c96e07e73be6`. Kein neuer Commit,
kein Push, Merge, Deployment, Actions-Start oder Drive-Zugriff.

### Bedienung

Text anklicken/antippen und im Rahmen ziehen, um ihn zu verschieben. Acht
beschriftete Eck-/Seitengriffe ändern die Rahmenabmessungen. Seitengriffe ändern
nur Breite oder Höhe, Eckgriffe beides unabhängig. Die gegenüberliegende
Seite/Ecke bleibt fest. Die Schriftgrösse bleibt immer unverändert; die vorhandenen
Zahlenfelder sind weiterhin separat nutzbar. Der violette ↻-Griff dreht den Rahmen.
Die Pfeiltasten funktionieren ebenfalls an den Griffen (Umschalt: grössere Schritte).
Escape beziehungsweise ein Touch-Abbruch stellt den vollständigen Gestenbeginn
wieder her. Pointer Capture führt begonnene Gesten auch ausserhalb des Griffs fort.
Ein zweiter Finger startet keine zusätzliche parallele Geste; es gibt keine
Zweifinger-Pinch-Skalierung.

Alle Griffe besitzen 48×48 Bildschirm-Pixel grosse Trefferflächen, unabhängig von
der Vorschauverkleinerung. Bei kleinen, gedrehten oder am Rand liegenden Rahmen
werden sie kollisionsfrei innerhalb der Vorschau versetzt. Gestrichelte
Verbindungslinien zeigen dann auf die tatsächlichen Rahmenpunkte. Die angezeigten
Pfeile/Mauszeiger folgen der Rahmendrehung. Sehr kleine Vorschaufenster unterhalb
der geprüften Smartphone-Grössen sind keine zusätzliche Zusage.

Rahmen, Griffe und Verbindungslinien sind nur bei aktiver Textauswahl sichtbar.
Ausserhalb klicken/tippen hebt die Auswahl auf. In gespeicherten Karten und im
Vergleich werden überhaupt keine Griff-/Linien-Elemente erzeugt.

### Geometrie, Layout und Speicherung

`frameResize` transformiert die Pointer-Differenz vom Gestenbeginn mittels inverser
Rahmendrehung in lokale Rahmenachsen. Nur Breite, Höhe und der daraus resultierende
Mittelpunkt ändern sich. Die gegenüberliegende Ecke/Seite bleibt auch bei
Grenzwerten fest; die zulässige Änderung wird begrenzt, statt den Rahmen nachträglich
zu verschieben. Bestehende Grenzen bleiben: Mittelpunkt 36–564, Rahmenmasse
32–1800 Designeinheiten, zusätzlich ausreichend Platz für den Innenabstand.
Ein über die Gestaltungsfläche ragender Rahmen erzeugt weiterhin eine Warnung.

Es gibt keinen zweiten Text-Scale und keine Änderung am Speicherformat dieser
Phase. Schriftgrösse, Zeilenhöhe, Innenabstand, Ausrichtung, Rohtext und manuelle
Enter-Umbrüche bleiben beim Ziehen unverändert. Der vorhandene gemeinsame Renderer
berechnet automatische Umbrüche sofort aus der neuen Innenbreite. Die bestehende
Platzwarnung wird nach jeder Pointer-Bewegung neu berechnet und bleibt auch in
Mappe/Vergleich erhalten. Der volle Text wird gespeichert; eine Warnung verhindert
keine Speicherung, stellt aber ausdrücklich keine Gravurfreigabe dar.

Die Zahlenfelder zeigen nach Gesten höchstens eine Nachkommastelle, damit keine
langen Dezimalzahlen die Bedienung erschweren. Im Modell und im lokalen Speicher
bleibt die ungerundete Geometrie erhalten. Fokussieren/Verlassen eines Zahlenfeldes
ohne Eingabe ändert diese Werte nicht. Alte V1-/V2-Entwürfe bleiben bei ihren
vorhandenen Renderern und Werkzeugen; es findet weiterhin keine Migration statt.

### Dateien dieser Phase

- `text-frame.js`: gedrehte Resize-Geometrie, acht Griffe, kollisionsarme Anordnung
  mit Verbindungslinien, Pointer-/Tastaturbindung und lesbare Zahlenfeldanzeige.
- `text-frame.css`: Griffgestaltung und nur bei Auswahl sichtbare Verbindungslinien.
- `tests/text_frame_check.js`: sechs zusätzliche reine Geometrie-/Grenzfalltests.
- `tests/frame_resize_browser_check.py`: neue lokale Maus-/Touch-Regressionsprüfung.
- `README.md` und dieser Prüfbericht: Bedienung, technische Grenzen und Ergebnisse.

Die nicht committierten Änderungen der vorherigen Etappe bleiben zusätzlich
bestehen. Insgesamt sind gegenüber HEAD 13 Dateien geändert beziehungsweise neu;
die übrigen sieben wurden in dieser Phase nicht weiter bearbeitet.

### Abschlussprüfung dieser Phase – tatsächlich ausgeführt

Alle folgenden Prüfungen wurden erneut lokal ausgeführt und bestanden:

| Befehl | Ergebnis |
| --- | --- |
| `node tests/text_frame_check.js` | 12/12 bestanden |
| `python3 -B tests/drive_sync_check.py` | 37/37 bestanden, offline |
| `python3 -B -m unittest discover -s tests -p 'import_check.py'` | 8/8 bestanden, offline |
| `python3 -B tests/drive_connection_check.py` | 6/6 bestanden, offline |
| `python3 -B tests/browser_check.py` | bestanden |
| `python3 -B tests/transform_check.py` | bestanden |
| `python3 -B tests/selection_check.py` | bestanden |
| `python3 -B tests/sync_categories_browser_check.py` | bestanden |
| `python3 -B tests/order_safety_check.py` | bestanden |
| `python3 -B tests/local_images_check.py` | bestanden |
| `python3 -B tests/text_frame_browser_check.py` | bestanden |
| `python3 -B tests/frame_resize_browser_check.py` | bestanden |
| `python3 -B tools/sync_motifs.py --validate` | 412 IDs, 824 referenzierte WebPs, 177.108.798 Bytes |
| `node --check text-frame.js`, `node --check personal.js`, `node --check transform.js` | bestanden |
| `git diff --check` | bestanden |

Die acht Browser-Skripte prüfen Chromium mit 1440×1000 (Maus), 820×1180 und
390×844 (Touch-Emulation über echte Chromium-Touch-Ereignisse). Externe
HTTPS-Anfragen werden in den Browserprüfungen blockiert; optionale Screenshots
liegen nur unter `/tmp`, nicht im Repository. Desktop, Tablet und Smartphone
wurden zusätzlich anhand lokaler Screenshots betrachtet.

Das neue Skript prüft alle acht Griffe bei 0°, 31°, 90° und −47°, jeweils in beide
Grössenrichtungen und bei allen drei Bildschirmgrössen: 96 Griff-/Drehwinkel-
Konfigurationen mit Vergrösserung und Verkleinerung. Geprüft wurden feste
Gegenanker, unveränderte Schriftgrössen und Ausrichtungen, manueller Rohtext,
sofortiger Umbruch während laufender Geste, Drehen nach Rahmenänderung und erneutes
Resize in den neuen Achsen, Verschieben, Gestenabbruch, Rand-/Minimalrahmen,
Tastatur, Speichern, Neuladen, Mappe, Vergleich und erneutes Öffnen. Beim
Verkleinern der Höhe erscheint die Platzwarnung, bei ausreichender Höhe
verschwindet sie wieder. Die gespeicherte Geometrie bleibt exakt, auch nach
unverändertem Fokussieren/Verlassen der gerundet angezeigten Zahlenfelder.

Die neuen Tests benötigten zwei Testkorrekturen: CSS-Zahlen werden vom Browser
für die Style-Anzeige gerundet (Vergleich daher mit enger Toleranz statt als
identische Zeichenfolge); String-Prädikate in Playwright wurden durch Funktionen
ersetzt, damit kein durch CSP verbotenes `eval` benötigt wird. Die Testposition
wurde ausserdem unterhalb des festen mobilen Seitenkopfs gewählt. Die CSP wurde
nicht geändert. Die abschliessenden vollständigen Läufe haben keine Fehler.

Bytevergleich beziehungsweise Git-Diff gegen HEAD: Workflows inklusive aktivem
Stundenplan, `tools`, `data`, `assets`, Katalog, Herkunftsmanifest, Bildlader und
`studio.js` unverändert. Beide vollständigen Formularblöcke und CSP ebenfalls
unverändert. 412 Motiv-IDs, neun Kategorien und 30 Schriften erhalten. Alle 824
referenzierten Vorschaudateien lieferten HTTP 200 und wurden im Browser decodiert.
Die Formularprüfungen bestätigen null Übermittlungen, Fetch/XHR/Beacon und
CSP-Schutz auch bei deaktiviertem App-JavaScript. Das ursprüngliche Repository
`/workspace/timberart-design` hat einen sauberen Arbeitsbaum und wurde nicht verändert.

**Grenzen:** Keine Tests auf physischen Geräten, Safari oder Firefox. Die echten
Google-Fonts wurden ohne externe Verbindungen nicht nachgeladen; Ersatzschriften
können andere Umbrüche erzeugen, die vorhandene Warnung bleibt aktiv. Kein neuer
Live-Test von Google Drive/Actions. Die Geometrie- und Platztests ersetzen keine
Prüfung auf tatsächlichen Werkstücken und keine Gravurfreigabe. Keine Änderungen
übertragen, nichts veröffentlicht; weitere Schritte warten auf ausdrückliche Freigabe.
