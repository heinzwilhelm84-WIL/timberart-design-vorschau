# Marktstand: nur PNG

Basis: `origin/main` nach PR #18 (`6ad5d41`).

In Motivauswahl, Personalisierung und Designmappe ersetzt „Design als PNG speichern“
die bisherigen Versandbuttons. Beide Testbestellformulare und ihr Schrift-Auswahlweg
sind entfernt. „Mit Motiv kombinieren“ im Schriftatelier bleibt erhalten. Der
Formspree-Sender wird nicht mehr ausgeliefert; die CSP erlaubt nur lokale Verbindungen
und weiterhin keine Formularübermittlung. SVG-/JSON-Downloads und Kontaktfelder gibt
es in der Oberfläche nicht mehr. Kein Mailversand, ZIP oder neuer Dienst.

## Export

- PNG mit exakt 2400 × 2400 Pixeln und vollständig weissem Hintergrund.
- Text wird direkt mit der Ausgabeauflösung gezeichnet, einschliesslich tatsächlicher
  Umbrüche, Ausrichtung, gewählter Schrift, Position und Drehung. Kein Hochskalieren
  des bisherigen 1200-Pixel-Gesamtbildes, keine Änderung am Textmodell.
- Motivquelle ist die grösste lokale WebP-Variante (bis 1600 Pixel), nicht das
  Galerie-Thumbnail. Originale liegen weiterhin unverändert auf Drive. Ohne
  authentifizierten Zugriff stehen sie dem Browser nicht zuverlässig zur Verfügung;
  deshalb kein öffentlicher Drive-Download als Ausweichweg. Wo die Zielplatzierung
  mehr Quellpixel benötigt, zeigt der Dialog einen Auflösungshinweis. Zusätzliche
  Motivdetails entstehen durch die 2400-Pixel-Leinwand nicht.
- Bei fehlendem Motivbild, nicht bestätigter Schrift, Textüberlauf oder über den
  Rand ragendem v3-Textrahmen wird kein unvollständiges PNG zum Download angeboten.
  Kurz schliessen, Ursache im Editor beheben und erneut öffnen.
- Bestehende v1-/v2-Entwürfe bleiben unverändert; nicht quadratische alte Anordnungen
  werden proportional auf dem weissen Quadrat zentriert. Kein Schreiben/Migrieren
  der Designmappe durch den Export. Leerer Text erzeugt keinen Platzhalter im PNG.
- PNG ist ein Rasterbild für den Import in xTool Creative Space. Kein SVG, keine
  editierbaren Schriftpfade und keine garantierte Gravur-/Produktionsdatei. Physische
  Abmessungen, Schwellenwerte und Gravureinstellungen in xTool selbst prüfen.

## iPad-Bedienung

1. Auf „Design als PNG speichern“ tippen: Der Vorschaudialog bereitet die Datei vor.
2. Das fertige PNG prüfen, dann den gleichnamigen Download-Link im Dialog antippen.

Der zweite Tap ist ein echter Benutzerklick auf eine bereits fertige Blob-Datei.
Es gibt keinen automatischen Klick nach asynchronem Font-/Bildladen und kein
sofortiges Freigeben der Download-URL. Falls Safari die Bildansicht öffnet:
„Teilen → In Dateien sichern“. Kein Zwang zum Teilen über andere Apps.

## Gezielte Prüfung

Keine vollständige Regressionstestserie und kein Live-Versand. Auszuführen:

```sh
node --check png-export.js
node --check design-export.js
node --check personal.js
node tests/text_frame_check.js
python -B tests/market_png_check.py
python -B tests/order_safety_check.py
```

Der neue lokale Browsercheck blockiert alle externen Verbindungen und prüft auf
1440/820/390 Pixeln: PNG aus Motiv, Editor und Mappe; 2400²; Deckkraft/Weiss;
grösste lokale Bildquelle; Textposition gegenüber Editor-Pixeln; Drehung; v1/v2;
unveränderten Speicher; fehlende Schrift/Bilder; Beratungsreset; keine POSTs.
Für reproduzierbare Geometrie wird eine lokale Testschrift als Montserrat geladen.
Damit ist nicht die Darstellung sämtlicher echter Google-Schriften bewiesen.
Die früheren reinen Anfrage-/SVG-UI-Tests wurden mit der entfernten Funktion entfernt;
die PNG-Pixelprüfung ist im neuen Browsercheck enthalten. Der bestehende allgemeine
Browsercheck und der Bestellsicherheitstest wurden an die entfernten Formulare angepasst.

**Noch praktisch zu prüfen:** physisches iPad mit Safari, tatsächlicher Speicherort
und Öffnen des PNG in xTool. Touch-Emulation in Chromium ersetzt diesen Test nicht.
Keine Änderung an Motivdaten, Originaldateien, Favoritenmodell oder Drive-Workflows.

## Tatsächliches Ergebnis am 21.10.2026

- Drei Syntaxchecks und Prüfung des HTML-Inline-Skripts: bestanden.
- Zwölf bestehende Textmodelltests: bestanden.
- PNG-Browsercheck: 1440 Pixel/Maus sowie 820 und 390 Pixel mit Touch-Taps bestanden.
  PNG-Text gegen Editorbild: mittlerer RGB-Abstand 1,543/255 in der Textregion.
- Bestellsicherheitscheck: bestanden, einschliesslich nativer Formularsperre ohne JS.
- Kein JavaScript-Fehler und keine POST-Anfrage im erfolgreichen PNG-Browserlauf.
- Diff-Prüfung: Motivkatalog, Daten, Motivbilder, Importwerkzeuge, Workflows und alle
  30 Schriftdefinitionen unverändert. Geänderte/neue Textdateien auf gängige
  Zugangsdatenmuster geprüft, ohne Fund. Keine temporären Dateien im Commit.
- Keine grosse Regressionstestserie, kein physisches Safari/iPad und kein xTool-Test.
