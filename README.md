# TimberArt Design – Testversion

Separate Vorschau aus `heinzwilhelm84-WIL/timberart-design`, Branch
`design/phase-1-geschenkstudio`, Quellcommit `5ad3ec35dea1b5576ce2b7a4f74c4d2e1077d491`.

- Deutliche Kennzeichnung als Testversion; keine echten Bestellungen.
- Beide Formulare testen ausschliesslich lokal. Kein Formspree-Endpunkt oder Bestellversand.
- Content Security Policy blockiert Formularübermittlungen und externe JavaScript-Netzwerkanfragen.
- Google-API-Schlüssel und Formspree-Konfiguration wurden entfernt.
- `catalog.json` enthält eine Momentaufnahme von 412 Motiven in 9 Kategorien.
  Alle Motivbilder kommen lokal aus `assets/motifs/`; Schriften von Google Fonts.
- Keine ursprüngliche Git-Historie übernommen. Das Quellrepository bleibt unverändert.
- Dieser Entwicklungsbranch ändert keine Pages-Einstellungen und enthält keine Deployment-Workflows.

Lokal ansehen: `python3 -m http.server 8000`, dann http://localhost:8000 öffnen.

## Personalisierung und Designmappe

Auf Branch `feature/personalisierung-designmappe`: Motiv öffnen und
„Personalisieren“ wählen, oder im Schriftatelier „Mit Motiv kombinieren“.
Wunschtext und eine der 30 Schriften kombinieren, lokal speichern, bearbeiten,
duplizieren, löschen und zwei Entwürfe vergleichen. Lange Texte werden nicht
abgeschnitten oder pauschal begrenzt; Hinweise unterstützen bei der Lesbarkeit.

Die Designmappe nutzt den Browserspeicher (`timberart-designmappe-v1`), ohne
Backend, Konto oder zusätzliche Dienste. Sie gilt nur für dieses Browserprofil
und ist kein dauerhaftes Archiv. „Neue Beratung“ löscht nach Bestätigung alle
Entwürfe, Favoriten, Auswahl und Formulare. Andere Browserdaten bleiben erhalten.
Andere offene App-Tabs laden bei Änderungen neu, damit alte Kundenauswahlen
nicht versehentlich weiterbenutzt werden. Gleichzeitiges Bearbeiten in mehreren
Tabs wird nicht unterstützt. Speicherfehler werden gemeldet; ungespeicherte
Änderungen werden beim Verlassen geschützt.

Die Vorschau ist keine Produktions-/Gravurdatei; ältere Entwürfe behalten ihre bisherige Anordnung, bis sie ausdrücklich bearbeitet und gespeichert werden.
Lokale Motivbilder benötigen keinen Google-Zugriff. Google-Schriften benötigen Internet. Fehlende Motivbilder und
Schriften werden kenntlich gemacht. Testbestellungen bleiben gesperrt.

### Browserprüfung

Mit Python und dem kostenlosen Paket `playwright` sowie Chromium:
`python3 -B tests/browser_check.py`.
Bei Bedarf `CHROMIUM_PATH` auf den Chromium-Pfad setzen. Optionale Screenshots:
`TIMBERART_TEST_SCREENSHOTS=/tmp/timberart-check python3 -B tests/browser_check.py`.
Die Tests blockieren externe Bild-/Schriftanfragen bewusst und prüfen dabei auch
die Hinweise bei fehlenden Ressourcen. Desktop (1440 px), Tablet (820 px) und
Smartphone (390 px) werden als Browser-Viewports geprüft, nicht auf physischen
Geräten. Es werden keine Testbestellungen übermittelt.


## Frei gestaltbarer Wunschtext

Branch `feature/text-transform-vorschau` baut auf dem geprüften
Personalisierungsbranch auf. Neue und bearbeitete Entwürfe verwenden eine
quadratische Gestaltungsfläche:

- Text mit Maus oder einem Finger verschieben.
- Griff ⤢ ziehen, um gleichmässig zu skalieren (25–300 %).
- Griff ↻ ziehen, um zu drehen (volle 360 Grad, Anzeige −180 bis 180 Grad).
- Alternativ Position in Prozent, Grössen-/Drehregler oder Tastatur verwenden.
  Pfeiltasten bewegen den fokussierten Text um 1 Prozentpunkt, mit Umschalt um 5.
  An Griffen ändern Pfeiltasten Grösse/Drehung; Home setzt die jeweilige
  Eigenschaft zurück. Escape oder ein Touch-Abbruch verwirft die laufende Geste.
- „Position, Grösse und Drehung zurücksetzen“ stellt die Ausgangsanordnung her.

Position, Skalierung und Drehung werden mit `layoutVersion: 2` und `transform`
pro Entwurf gespeichert. Die Darstellung nutzt einen festen internen
600×600-Gestaltungsraum und skaliert ihn proportional. Dadurch bleibt die
Anordnung in Editor, Mappe und Vergleich über Bildschirmgrössen hinweg gleich.
Ältere Entwürfe ohne Transformationswerte werden weiterhin angezeigt. Beim
Öffnen im Editor wird eine neue Anordnung vorbereitet; erst „Änderungen
speichern“ übernimmt sie. Beim Duplizieren und Bearbeiten bleibt das Original
unverändert.

Der Textmittelpunkt bleibt mit 6 % Sicherheitsabstand innerhalb der Fläche.
Teile grosser oder gedrehter Texte dürfen über den Rand reichen und werden in
der Vorschau abgeschnitten; ein Hinweis macht darauf aufmerksam. Der Wunschtext
wird vollständig gespeichert. Es gibt weiterhin keine pauschale Zeichen- oder
Zeilenbegrenzung. Die Textbreite im Gestaltungsraum ist fest; Skalierung verändert
Breite und Höhe gemeinsam. Keine Scherung, Perspektive oder Millimeterangaben.

Ein-Finger-Griffe werden unterstützt, keine Zwei-Finger-Pinch-/Drehgesten.
Ausserhalb des Textes und der Griffe kann die Seite normal gescrollt werden.
Die App benötigt einen modernen Browser mit Pointer Events und ResizeObserver.
Motivbilder kommen aus lokalen WebP-Dateien, Schriften weiterhin von Google Fonts. Bei
fehlender Originalschrift kann sich das Schriftbild der Ersatzschrift ändern;
die gespeicherten Positionen und Transformationswerte bleiben erhalten.

Zusätzliche reproduzierbare Prüfungen:

- `python3 -B tests/transform_check.py`: tatsächliche Maus- und Chromium-
  Touch-Ereignisse, Ziehen/Skalieren/Drehen, Randbegrenzung, Abbruch,
  Tastatur, Speicherung/Neuladen, Duplikate/Vergleich, Bildschirmwechsel und
  Migration älterer Entwürfe bei 1440, 820 und 390 Pixeln.
- `python3 -B tests/order_safety_check.py`: beide ausgefüllten Bestellformulare,
  wiederholtes Absenden, keine fetch-/XHR-/Beacon-Aufrufe oder Formulardaten
  in Requests; native Übermittlung auch ohne App-JavaScript durch CSP gesperrt.

Touch wurde im Chromium-Browser emuliert. Reale iOS-/Android-Geräte sowie Safari
und Firefox wurden nicht geprüft. GitHub Pages und bestehende Pull Requests
werden durch diesen Branch nicht verändert; kein Merge oder Deployment.

## Auswahlabhängige Bearbeitungswerkzeuge

Branch `feature/textauswahl-werkzeuge`: Der Editor startet mit einer Vorschau
ohne Auswahlrahmen, Griffe oder Raster. Klick/Tap auf den Text wählt ihn aus und
zeigt Rahmen, Griffe, Raster sowie die Positions-/Grössen-/Drehregler. Klick/Tap
auf einen anderen Bereich hebt die Auswahl wieder auf. Beim Benutzen der Griffe
und zugehörigen Regler bleibt sie erhalten; Formulare und Schriftwahl funktionieren
weiterhin mit dem ersten Klick/Tap. Die Auswahl wird erst beim abgeschlossenen
Klick aufgehoben, damit eingeklappte Werkzeuge auf kleinen Bildschirmen nicht das
angetippte Bedienelement vor dem Klick verschieben.

Tastaturfokus auf dem Text wählt ihn ebenfalls aus. Escape hebt die Auswahl auf;
während einer laufenden Geste verwirft Escape zuerst nur diese Geste. Auswahl
und Sichtbarkeit der Werkzeuge sind flüchtiger Oberflächenzustand und werden
nicht gespeichert. Gespeicherte Position, Skalierung und Drehung bleiben beim
Abwählen unverändert. Das erneute Öffnen eines Entwurfs beginnt ohne Auswahl.
Designmappen-Karten und der Vergleich zeigen grundsätzlich keine Werkzeuge;
„Bearbeiten“ öffnet den Editor, in dem der Text gezielt ausgewählt werden kann.

`python3 -B tests/selection_check.py` prüft Auswählen/Abwählen, erneutes Auswählen,
Maus-/Touch-Gesten, Werkzeugbedienung, den ersten Tap auf Eingaben/Schriften,
Tastatur, unveränderte Geometrie und Speicherung, saubere Vorschau-/Vergleichs-
ansichten und Beratungsreset bei 1440, 820 und 390 Pixeln in Chromium. Zusätzlich
bleiben die bisherigen Funktions-, Transformations- und Bestellsperrentests aktiv.
Reale Geräte, Safari und Firefox wurden nicht geprüft.

## Lokale Motivbilder

Branch `feature/lokale-motivbilder`: 412 unveränderte Motiv-IDs mit jeweils zwei
verlustfreien WebP-Bildschirmpreviews (maximale Kantenlänge 600/1600 Pixel). Alle
Ansichten verwenden lokale relative URLs, ohne Drive-Fallback. Die Bild-CSP wurde
auf eigene Dateien eingeschränkt. Originale auf Drive bleiben unverändert.

Import, eindeutige Originalzuordnung, Erweiterung um neue Drive-Ordner, Prüfbefehle
und Einschränkungen: [docs/motifs-import.md](docs/motifs-import.md).
