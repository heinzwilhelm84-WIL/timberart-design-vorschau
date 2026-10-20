# Offline-Prüfergebnis – Drive-Synchronisierung

## Lokale Korrekturen und erneute Prüfung vom 20.10.2026

Uncommittete Änderungen auf `feature/drive-sync-automatik`, HEAD weiterhin
`2e30f0ef7abee09a0c8a12afbfc7d432487844af`. Kein Push, Live-Abgleich, Workflow-Start,
Merge, Deployment oder aktivierter Zeitplan. Der ältere Bericht unten ist ein
historischer Stand; seine damalige detaillierte Berichtsausgabe wurde ersetzt.

Die zwei zuvor unabhängig reproduzierten Fehler sind durch Regressionstests
abgedeckt und behoben:

- `sourceFingerprint` wird vor der Wiederverwendungsentscheidung aus den aktuellen
  Quelldaten berechnet. Umbenennung, neue Änderungszeit und neue Version bei
  identischem Bildinhalt: konsistenter Fingerprint, null erneute Downloads,
  unveränderte WebP-Bytes; der Folgelauf ändert keine Dateien.
- Widerspruch zwischen namensgleichem Ordner und Motivfund in anderem Ordner:
  Inventur und Übernahme brechen ohne Ausgabenänderung mit einer verständlichen,
  metadatenfreien Meldung ab. Umbenennungen, verschobene Unterbäume und bereits
  gebundene Kategorien werden geprüft. Eine private, lokale Erstzuordnungsdatei
  ausserhalb des Repositorys kann den Konflikt bewusst auflösen; sie ist in
  öffentlichen Actions gesperrt und kann keine gespeicherte Bindung umbiegen.
- Inventur- und PR-Bericht geben nur feste Statusmeldungen und Gesamtzahlen aus.
  Eingespeiste Namen, IDs, Pfade und unbekannte Metadaten erscheinen weder im
  Bericht noch in CLI-Erfolgs-/Fehlerausgaben. Auch rohe SyncError-/Decodertexte
  und eine betroffene Motiv-ID werden nicht öffentlich ausgegeben.

Tatsächlich erneut ausgeführte Befehle (alle Exitcode 0):

```sh
python3 -B tests/drive_sync_check.py
python3 -B -m unittest discover -s tests -p 'import_check.py' -v
python3 -B tests/drive_connection_check.py
python3 -B tools/sync_motifs.py --validate
env -u TIMBERART_TEST_SCREENSHOTS python3 -B tests/sync_categories_browser_check.py
env -u TIMBERART_TEST_SCREENSHOTS python3 -B tests/browser_check.py
env -u TIMBERART_TEST_SCREENSHOTS python3 -B tests/transform_check.py
env -u TIMBERART_TEST_SCREENSHOTS python3 -B tests/selection_check.py
env -u TIMBERART_TEST_SCREENSHOTS python3 -B tests/order_safety_check.py
env -u TIMBERART_TEST_SCREENSHOTS python3 -B tests/local_images_check.py
```

35 Sync-Tests (die bisherigen 23 plus zwölf neue), acht Importtests und sechs
Verbindungstests bestanden: **49 Python-Tests insgesamt**, null fehlgeschlagene
Tests. Alle sechs Browser-Skripte bestanden. Chromium: Desktop 1440 px mit Maus,
Tablet 820 px und Smartphone 390 px mit emuliertem Touch. Externe HTTPS-Aufrufe
in Browserprüfungen blockiert; echte Netzwerkverbindungen in Sync-Tests gesperrt.
Beide gefüllten Bestellformulare: wiederholtes Absenden ohne Requests/fetch/XHR/
Beacon, native Übermittlung durch CSP blockiert, auch ohne App-JavaScript.

Der lokale Validator bestätigt 412 IDs, 824 WebPs und 173.988.974 Bytes.
Zusätzliche lesende Git-/Python-Prüfung: Katalog, Herkunftsmanifest und WebPs
gegenüber `origin/main` (`d9b8bf6`) unverändert; alle neun Kategorie-Schlüssel
erhalten und Kategorie-Datei samt IDs gegenüber HEAD unverändert. Oberfläche,
Schriftdefinitionen, CSP und beide Workflows wurden durch die Korrektur nicht
verändert. Alle 824 Dateien im Browser mit HTTP 200, WebP-MIME und erfolgreicher
Decodierung unter Pages-Unterpfad geladen. Bestehende Entwürfe und Favoriten
unverändert wiederhergestellt. Python-Syntax und bekannte Geheimnismuster in
geänderten Dateien geprüft; `git diff --check` ohne Befund.

Grenzen: kein echter Google-/GitHub-Integrationstest, keine physischen Geräte,
kein Vergleich mit Drive-Originalen (`sourcePixelComparisons: 0`). Die echte
Ordnerzuordnung bleibt privat zu prüfen. Öffentliche PR-Dateidiffs enthalten
weiterhin App-Daten und Herkunftszuordnungen; der anonyme Bericht versteckt diese
nicht. Sicherer Prüfweg und Grenzen stehen in [drive-sync.md](drive-sync.md).

## Historischer Prüfstand vor diesen Korrekturen

19.10.2026, Branch `feature/drive-sync-automatik`, Basis `d9b8bf6`.
Kein Live-Drive-Lauf, kein Workflow-Dispatch, kein Push, PR, Merge oder Deploy.

## Bestehender Bestand

- Katalog und Herkunftsmanifest enthalten dieselben 412 eindeutigen Motiv-IDs.
- Die neun bisherigen Kategorien/Schlüssel sind vollständig in der neuen
  Kategorien-Datei enthalten. Es wurden keine echten Drive-Ordner-IDs erfunden.
- Alle 824 bestehenden WebPs unverändert: 173.988.974 Bytes, ca. 165,93 MiB.
- Format, Abmessungen, SHA-256 und Pixel-Prüfsummen aller 824 Dateien stimmen mit
  dem bisherigen Manifest überein; keine Hochskalierung.
- Kein bestehendes Motiv, Bild oder Herkunftseintrag wurde durch die Vorbereitung
  geändert. Die 30 Schriftdefinitionen und die CSP sind identisch zum Basisstand.
- Bestehende Bilder enthalten keine EXIF-/XMP-/ICC-Metadaten.

## Neue Offline-Vertragstests

23 Tests in `tests/drive_sync_check.py` bestanden; echte Netzwerkverbindungen
wurden während der Tests blockiert. Drive liefert ausschliesslich simulierte Daten.

Geprüft wurden insbesondere:

- Inventur ohne Download oder Repository-Änderung; Ausschluss von LOGO/Schriften.
- Simulation von elf Root-Unterordnern mit neun resultierenden Motivkategorien.
- Leere und verschachtelte neue Kategorien, gleiche Namen mit verschiedenen IDs.
- Einmalige Erstverifikation mit Wiederverwendung der bestehenden WebP-Bytes;
  zweiter unveränderter Lauf: null Downloads, null Dateiveränderungen.
- Neue Rasterbilder, Transparenz, Inhaltsänderung und Erhalt alter Vorschaupfade.
- Umbenennen und Verschieben von Ordnern mit unveränderter Kategorie-/Motiv-ID.
- Reine Dateiumbenennung ohne erneute Bildverarbeitung.
- Fehlende Rechte, fehlerhafte Bilder auch nach einem vorher erfolgreichen Bild,
  abschliessender Validierungsfehler mit vollständigem Zurücksetzen aller Ausgaben.
- Fehlende Motive/Kategorien bleiben erhalten. Ein einmal ausgeschlossener Ordner
  bleibt auch nach Umbenennung ausgeschlossen.
- Verweigerung mehrdeutiger Erstzuordnung, Kategoriezyklen und geheimnisähnlicher
  Metadatentexte; blockierte fremde Pfade und falsche/animierte/übergrosse Bilder.
- ICC-zu-sRGB-Konvertierung mit Alphakanal, EXIF-Ausrichtung, keine Übernahme privater
  Bildmetadaten. Kein Originalformat wird als öffentliche Datei ausgegeben.
- Authentifizierte GETs, vollständige Pagination, Abbruch bei unvollständiger Suche,
  wiederholten Seiten, MD5-/Grössenfehlern und Umleitungen; sichere HTTP-Fehlermeldungen.
- Lokales Git-Integrationsszenario für einen offenen PR: Zusätze auf main und im
  Bot-Branch bleiben erhalten. Gleichzeitige widersprüchliche Änderungen oder
  Löschungen werden abgelehnt. Fremder Workflow-Code im Bot-Branch wird zurückgewiesen,
  ohne ihn auszuführen. Fork-PRs und zwischenzeitlich geänderte Remote-Heads
  werden ebenfalls nicht übernommen. Kein echter PR oder GitHub-Zugriff im Test.
- Workflow-Struktur: nur manueller Auslöser, default `inventory`, getrennte Rechte,
  feste main-/Repository-Prüfung, gepinnte Actions, kein Zeitplan, kein Artefakt-
  Upload, keine automatische Zusammenführung und kein Deployment.

Zusätzlich bestanden die acht bisherigen Importtests und sechs bisherigen
Offline-Verbindungstest-Prüfungen. Insgesamt 37 Python-Vertragstests erfolgreich.

## Lokale Browserprüfungen

Chromium, 1440 px Desktop, 820 px Tablet, 390 px Smartphone; externe Ressourcen
wurden blockiert. Kein Zugriff auf Kunden-Browserspeicher oder echte Bestelldienste.

- Neue Kategorie zunächst leer, später mit Bild, danach umbenannt: stabiler Schlüssel.
- Manipulierte Motiv-/Ordnernamen werden als Text behandelt, auch im alten Renderer.
- Bestehende Motivsuche, Filter, Favoriten und alle 30 Schriftoptionen erhalten.
- Lange und mehrzeilige Texte, Speichern/Neuladen/Bearbeiten/Duplizieren/Löschen,
  Vergleich, Beratungsreset, Speicherschutz und tabübergreifende Behandlung bestanden.
- Tatsächliche Maus-/emulierte Touch-Ereignisse für Verschieben, Skalieren, Drehen,
  Randbegrenzung, Auswahlwerkzeuge, Tastatur und Wiederherstellung bestanden.
- Beide Bestellformulare mit vollständig ausgefüllten Feldern und wiederholtem
  Absenden: keine Formularrequests und keine fetch/XHR/Beacon-Aufrufe beim Absenden.
  Native Übermittlung auch ohne App-JavaScript durch CSP gesperrt.
- Kein horizontaler Überlauf und keine JavaScript-Laufzeitfehler in den Prüfungen.

Python-/JavaScript-Syntax und Git-Whitespace geprüft. Die neuen/geänderten Textdateien wurden abschliessend auf bekannte Geheimnismuster
kontrolliert und die Dateiliste auf Originale/Zugangsdaten geprüft; ohne Befund.

## Nicht nachgewiesen und verbleibende Voraussetzungen

Die tatsächlichen elf Drive-Ordnernamen, ihre IDs und die zwei realen Ausschlüsse
wurden nicht live eingelesen. Ihre Zuordnung ist erst im freigegebenen Inventurmodus
zu bestätigen. Ein erfolgreicher Metadaten-Verbindungstest beweist noch keinen
Originaldownload. `drive.readonly`, tatsächliche Downloadrechte und PR-Erstellung
mit dem Actions-Token sind daher bei kontrollierter Inbetriebnahme zu prüfen.

Es wurden keine echten Actions-Laufzeiten, Google-Quoten oder PR-Schreibrechte
gemessen. Erforderlich sind die vorhandene WIF-/Betrachterfreigabe sowie GitHub-
Rechte für Bot-Branch und PR-Erstellung; main soll geschützt bleiben. Es wurden
keine Cloud-/Repository-Einstellungen geändert und keine privaten Schlüssel erstellt.

Der erste vollständige Abgleich muss die bisherigen 412 Originale einmalig
verifizieren, da deren Original-Fingerprints fehlen. Die vorhandenen 824 Vorschauen
werden dabei pixelweise wiederverwendet, soweit sie übereinstimmen. Aktuell
referenzierte Motive in alten Entwürfen zeigen spätere Bildaktualisierungen;
historische Bildversionen werden nicht pro Entwurf festgeschrieben.

Physische Geräte, Safari/Firefox und echte Google-/GitHub-Integration wurden nicht
getestet. Grenzen, manueller Erstlauf und spätere Zeitplan-Freigabe stehen in
[drive-sync.md](drive-sync.md).
