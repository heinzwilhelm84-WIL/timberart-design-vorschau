# Prüfung der lokalen Motivbilder – 19.10.2026

Basis: `main` bei `beee8b282d5f0fee44a521d4a2a30af8661eb0a3`.
Entwicklungsbranch: `feature/lokale-motivbilder`.

## Ergebnis

Alle 412 Motive behalten IDs, Namen und Kategorien exakt; alle 9 Kategorien und
30 Schriftdefinitionen bleiben erhalten. Die 824 referenzierten WebP-Dateien
existieren vollständig. Es gibt keine zusätzlichen unreferenzierten WebP-Dateien.

| Variante | Dateien | Bytes | MiB |
| --- | ---: | ---: | ---: |
| maximal 600 Pixel | 412 | 35.229.832 | 33,60 |
| maximal 1600 Pixel | 412 | 138.759.142 | 132,33 |
| Gesamt | 824 | 173.988.974 | 165,93 |

Grösste einzelne Datei: 1.493.436 Bytes (ca. 1,42 MiB).
158 Quellvorschauen haben nativ weniger als 1600 Pixel an der längsten Kante und
werden nicht vergrössert. Die Quellvorschauen umfassen 348 PNG und 64 JPEG mit
192.467.694 Bytes; diese extern zwischengespeicherten Dateien sind nicht im Git.
Der etwas höhere Platzbedarf gegenüber der ersten Schätzung folgt aus der
Glättung von Bilevel-Linienbildern vor der WebP-Kodierung.

## Erfolgreiche Prüfungen

- Alle 824 Dateien dekodiert: WebP-Format, Kantenlängen, Abmessungen, Dateigrössen,
  SHA-256 und Pixel-Prüfsummen stimmen. Keine Hochskalierung.
- Alle 824 RGBA-Pixelbilder sind exakt gleich der erneut mit LANCZOS verkleinerten
  Quellvorschau, einschließlich Transparenz. Die WebP-Kompression ist verlustfrei.
- Alle 824 URLs unter `/timberart-design-vorschau/`: HTTP 200, Content-Type
  `image/webp`, erfolgreiche Chromium-Dekodierung.
- Desktop 1440×1000, Tablet 820×1180, Smartphone 390×844: Startseite, komplette
  Galerie, grosse Vorschau, Personalisierung, ältere/neue Entwürfe, Designmappe
  und Vergleich laden lokale Bilder. Tablet/Smartphone zusätzlich mit Touch und
  doppelter Pixeldichte. Kein horizontaler Überlauf; keine Drive-/Login-Bildrequests.
- Vorhandene Favoriten und Entwürfe der Layoutversionen 1 und 2 bleiben erhalten;
  gespeicherte Position, Skalierung und Rotation bleiben korrekt. Speicherung wird
  durch das Laden lokaler Bilder nicht verändert.
- Simulierte HTTP-404-Bilder: lokaler Platzhalter bzw. vorhandener Hinweis,
  kein Drive-Fallback, Auswahl bleibt erhalten.
- Bestehende Browser-, Transformations- und Auswahltests vollständig bestanden:
  Maus-/Touch-Verschieben, Skalieren/Drehen, Randbegrenzung, Tastatur, Persistenz,
  Bearbeiten/Duplizieren/Löschen/Vergleichen, Beratungsreset und Speicherschutz.
- Beide ausgefüllten Bestellformulare auf allen drei Bildschirmgrössen: wiederholt
  absenden, keinerlei Formularrequests, keinerlei fetch/XHR/Beacon beim Absenden.
  Native Übermittlung wird durch `form-action 'none'` blockiert, auch ohne App-JS.
- Acht Offline-Importtests: exakte Alphapixel, keine Hochskalierung, unveränderte
  Wiederholungsimporte, Erkennung beschädigter Assets, neue verschachtelte Ordner,
  Ausschlüsse/Kategoriekonflikte, API-Paginierung, GET-only, sichere Fehlermeldungen,
  HTTP-Dekompression/-Grössenlimit, kein Pfadausbruch, kein Metadatenwechsel bei
  Teilfehlern, keine Änderungen im Dry Run, Beibehaltung fehlender Motive.
- Erneuter echter Import: 412× `unchanged`, `metadataChanged: false`, keine erneuten
  Downloads, keine neu erzeugten Dateien.
- Sichtprüfung von RGB-, RGBA- und Bilevel-Beispielen in Hoch-/Querformat sowie
  Desktop-/Smartphone-Screenshots: für Bildschirmvorschauen geeignete Darstellung.
- JavaScript-Syntax, Git-Whitespaceprüfung und Suche nach Token-/API-Key-/Private-
  Key-Mustern in den zu veröffentlichenden Textdateien ohne Befund; keine `.env`.

Die CSP wurde ausschliesslich verschärft: `img-src 'self' data:`. Bestellsperren,
`connect-src 'self'`, `form-action 'none'` und die Testkennzeichnung bleiben erhalten.

## Grenzen und Veröffentlichung

Die Prüfungen nutzen Chromium mit emulierten Maus-/Touch-Viewports, keine physischen
Geräte; Edge, Safari und Firefox wurden nicht separat ausgeführt. WebP erfordert
einen aktuellen Browser. Google Fonts bleiben eine externe Abhängigkeit; die Tests
blockieren sie bewusst und prüfen den vorhandenen Ersatzschrift-Hinweis.

Die Dateien sind Bildschirmvorschauen, keine Gravur-/Produktionsdateien. Die
Verkleinerung kann Details reduzieren; JPEG-Artefakte werden nicht entfernt.
Die Originaldateien auf Drive wurden ausschliesslich per stabiler Datei-ID
referenziert und nicht verändert. Der Laufzeitkatalog enthält keine Drive-Bild-URLs.

Die automatische Ordnererkennung ist vorbereitet und offline getestet, mangels
Drive-API-Zugangsdaten hier noch nicht gegen echte Ordner ausgeführt. Die eindeutige
Originalzuordnung per ID/Link ist für alle 412 Motive vorhanden. Vollständige
Originaldateinamen/Ordner-/Änderungsmetadaten werden bei der ersten API-Erkennung
ergänzt. Kein Zeitplan und kein automatisches Deployment wurden eingerichtet.

Die Arbeitsumgebung lieferte während des Imports zeitweise HTTP-503-Proxyfehler.
Die fehlenden öffentlichen Vorschaubilder wurden über alternative öffentliche
Thumbnail-URLs vollständig nachgeholt und danach ausschliesslich lokal geprüft.

Kein Merge, keine Pages-Konfiguration und kein Deployment. Es wird ausschliesslich
der neue Entwicklungsbranch im Vorschau-Repository übertragen. Das ursprüngliche
Repository `timberart-design` wird nicht verändert.
