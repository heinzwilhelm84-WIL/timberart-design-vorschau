# Lokale Motivvorschauen

Für den neuen authentifizierten Automatik-Import und stabile Kategorien gilt
[drive-sync.md](drive-sync.md). Die nachfolgenden ursprünglichen CLI-Beispiele
beschreiben den bisherigen öffentlichen Einzelimport, nicht den neuen Workflow.

Die Anwendung lädt Motivbilder ausschliesslich relativ zur Seite aus
`assets/motifs/<Drive-Datei-ID>/`. Das funktioniert auch unter dem Pages-Unterpfad
`/timberart-design-vorschau/`. Google-Login und Drittanbieter-Cookies sind dafür
nicht erforderlich. Es gibt keinen Drive-Fallback. Fehlende Bilder erhalten einen
lokalen Platzhalter bzw. den vorhandenen Hinweis; die Auswahl bleibt erhalten.
Die CSP erlaubt Bilder nur noch von `'self'` und `data:`. Google Fonts bleiben extern.

## Dateien und Zuordnung

- `catalog.json`: Laufzeitkatalog, unveränderte IDs, Namen und Kategorien; `url`
  (600er), `detailUrl` (1600er), `images` mit tatsächlichen Abmessungen für `srcset`.
- `data/motifs-baseline.json`: ursprüngliche 412 IDs/Namen/Kategorien als Referenz.
- `data/motifs-manifest.json`: jede ID mit eindeutiger ursprünglicher Drive-Datei,
  Original-Link, Quellvorschau-Prüfsumme, Abmessungen und Prüfsummen beider Varianten.
- `motifs.sources.json`: erweiterbare Liste der einzulesenden Drive-Wurzelordner.
- `tools/sync_motifs.py`: ausschliesslich lesender Import, keine Veröffentlichung.

Die Erstübernahme nutzt den bestehenden Katalog und öffentlich erreichbare
Drive-Bildvorschauen mit angeforderter Breite 1600. **Keine Laser-Originale werden
heruntergeladen, konvertiert oder überschrieben.** Die Datei-ID ist die eindeutige
Originalzuordnung. Originaldateiname, Ordner und Änderungsmetadaten sind in dieser
Erstübernahme unbekannt (`null`), bis eine lesende API-Ordnererkennung ausgeführt wird.
Der Katalogname wird nicht als angeblich ermittelter Originaldateiname ausgegeben.
Die tatsächlichen Grössen der Laser-Originale wurden nicht ermittelt.

Nach EXIF-Ausrichtung werden RGB/RGBA-Bilder proportional mit LANCZOS verkleinert,
maximal 600 bzw. 1600 Pixel entlang der längsten Kante, niemals vergrössert.
Bilevel-/Palettenbilder werden vor der Skalierung konvertiert, damit feine Linien
geglättet werden. WebP wird verlustfrei einschließlich Transparenz gespeichert.
„Verlustfrei“ bezieht sich auf das skalierte Vorschaubild; die Verkleinerung selbst
reduziert Details, vorhandene JPEG-Artefakte werden nicht repariert. Kein Gravur-Export.
Dateinamen enthalten einen Inhalts-Hash; geänderte Dateien erhalten neue URLs.

Galerie und kleine Karten verwenden responsive Bildquellen mit verzögertem Laden.
Grosse Vorschau, Personalisierung, ältere Entwürfe, Mappe und Vergleich nutzen
dieselbe lokale Auflösungsauswahl. Der Browser darf abhängig von Bildschirmdichte
auch die grössere Variante wählen. Favoriten und Entwürfe bleiben ID-basiert;
Speicherschlüssel und Transformationswerte werden nicht migriert oder zurückgesetzt.
Browserdaten sind weiterhin an Browserprofil und Seiten-Origin gebunden. Ein
Wechsel der Domain oder ein neues Browserprofil überträgt keine lokale Designmappe.

## Import und spätere Ordnersynchronisierung

Python 3.10+ und kostenlose Abhängigkeit:

```sh
python -m pip install -r tools/requirements-images.txt
python -B tools/sync_motifs.py
python -B tools/sync_motifs.py --apply
python -B tools/sync_motifs.py --validate
```

Ohne `--apply` wird nur ein Bericht ausgegeben. Bestehende geprüfte Dateien werden
wiederverwendet. `--refresh --apply` liest die Drive-Vorschaudaten erneut ein. Der
Quellvorschau-Cache liegt standardmässig neben dem Repository, nie darin; ein Cache
innerhalb des Repositorys wird zurückgewiesen. Es werden nur GET-Anfragen gesendet.
HTTP-Fehler werden mit Wiederholungen behandelt, ein alternativer öffentlicher
Google-Bildhost wird ausschliesslich beim Import benutzt. Anmelde-/Fehlerseiten
werden nicht als Bild akzeptiert. Scheitert ein Motiv, bleibt der bisherige Katalog
unverändert. Bereits erzeugte, noch nicht referenzierte Assets können zurückbleiben;
ein erneuter Import nutzt den Quellcache. Veraltete Assets werden nicht automatisch
entfernt, damit alte Links nicht unerwartet brechen. Nach mehreren Updates kann
eine separat überprüfte Bereinigung sinnvoll sein.

Für neue Ordner weitere `roots` in `motifs.sources.json` eintragen. Pro Root sind
`folderId`, `recursive`, `includeRootImages`, optional `category` und
`excludeFolderNamesContaining` konfigurierbar. Ohne explizite Kategorie bildet der
erste Unterordner die Kategorie. Unterordner werden rekursiv gelesen; ID bleibt
immer die Drive-Datei-ID. Doppelte IDs mit widersprüchlichen Kategorien brechen ab.
Fehlende/gelöschte Drive-Bilder werden gemeldet und lokal **beibehalten**.

Die automatische Erkennung benötigt einmalig einen auf dem Importrechner gesetzten
`GOOGLE_DRIVE_API_KEY` (öffentliche Ordner) oder `GOOGLE_DRIVE_ACCESS_TOKEN`
mit ausschliesslich lesendem Drive-Zugriff. Die Bildvorschauen müssen weiterhin
öffentlich lesbar sein; private Bilder werden mit diesem Vorschauimport nicht
über einen Originaldatei-Download umgangen. Zugangsdaten gehören weder in die App
noch in Dateien/Commits. Die aktuelle Umgebung hat keine solchen Drive-Zugangsdaten;
die echte Ordnererkennung ist deshalb noch nicht gegen das Konto ausgeführt.

```sh
# Zugangsdaten vorher über sichere Umgebungsvariablen bereitstellen.
python -B tools/sync_motifs.py --discover
python -B tools/sync_motifs.py --discover --apply
```

Der erste Aufruf zeigt neue und nicht mehr gefundene IDs und nötige Importe.
Der zweite erzeugt neue Dateien und aktualisiert Katalog/Manifest erst nach Erfolg
aller Bilder. Änderungsmetadaten erkennen später geänderte Inhalte; bestehende
Dateien werden nicht unnötig neu kodiert. Umbenennen/Verschieben kann die Anzeige
aktualisieren, IDs und gespeicherte Entwürfe bleiben zugeordnet. Für regelmässige
Synchronisierung kann derselbe Befehl später in einem geplanten Maintainer-Job
laufen und einen überprüfbaren Branch/PR erzeugen. **Kein Zeitplan, kein GitHub
Action Workflow und kein automatischer Push/Deploy wird hier eingerichtet.**

## Prüfungen

```sh
python -B tools/sync_motifs.py --validate --verify-source-cache ../motif-preview-cache
python -B -m unittest discover -s tests -p 'import_check.py'
python -B tests/local_images_check.py
python -B tests/browser_check.py
python -B tests/transform_check.py
python -B tests/selection_check.py
python -B tests/order_safety_check.py
```

Alle Varianten werden dekodiert und bezüglich Format, Kantenlänge, Dateigrösse,
SHA-256, Pixel-Prüfsumme und Originalzuordnung geprüft. Der optionale Cachevergleich
prüft alle RGBA-Pixel gegen die unabhängig erneut verkleinerte Quellvorschau.
Die Browserprüfung lädt alle 824 Dateien auch unter einem Projekt-Unterpfad,
blockiert externe Ressourcen und prüft Ansichten, alte Speicherstände und Ausfälle.
Chromium-Viewports mit Maus-/Touch-Ereignissen ersetzen keine physischen Geräte-
oder Safari-/Firefox-Prüfung. Bestellformulare bleiben vollständig gesperrt.

GitHub Pages wird von diesen Werkzeugen nicht konfiguriert oder veröffentlicht.
Vor einem kommerziellen Produktivbetrieb sind die Pages-Nutzungsbedingungen und
das geeignete Hosting gesondert zu klären. GitHub-Speicher und Bandbreite sind
begrenzt; der Browser lädt dank Lazy Loading nicht alle 824 Bilder auf einmal.
