# Automatische Ergänzungen – vorbereitet, nicht aktiviert

## Ablauf und Freigabegrenze

Der bestehende stündliche Workflow (`17 * * * *`, UTC) und der vorhandene
WIF-/Drive-Import werden weiterverwendet. Google Drive wird ausschliesslich mit
`drive.readonly` gelesen. Es gibt keinen neuen Importer und keine privaten
Google-Schlüssel. Unveränderte Motive werden weiterhin anhand ihrer Fingerprints
wiederverwendet, ohne erneuten Download oder neue Bildberechnung.

Nach einem vollständig erfolgreichen Scan und den bisherigen öffentlichen
Validierungen kann `tools/drive_sync_additions.py` eine Ergänzungsprojektion bilden:

- Bestehende Motiv- und Kategoriedatensätze aus dem ausgecheckten `main` werden
  unverändert übernommen, einschliesslich IDs, Schlüssel, Zuordnungen und Metadaten.
- Neue Ordner dürfen als stabile `drive-<folderId>`-Kategorien hinzukommen,
  auch leer oder verschachtelt. Ausschlüsse für LOGO, Schriften und gespeicherte
  ausgeschlossene Ordner-IDs bleiben wirksam.
- Neue Motive sind nur mit eindeutiger, aktuell bestätigter Kategorie zulässig.
  Geprüft werden die beiden lokalen, verlustfreien WebP-Varianten mit höchstens
  600/1600 Pixeln, Fingerprints, Zuordnung, Prüfsummen, Pixelprüfsummen,
  Dimensionen und Metadatenfreiheit. Kein Hochskalieren, kein Original im Git.
- Ist eine bestehende Kategorie oder ein Vorfahr umbenannt, verschoben, anders
  gebunden oder nicht mehr sichtbar, bleiben neue Inhalte darunter manuell.
  Unabhängige, eindeutig sichere Ergänzungen können separat übernommen werden.
- Bestehende Bildersetzungen, Namen, Änderungszeiten, Dateiversionen und
  Kategorieänderungen bleiben im Draft-PR. Es werden keine bestehenden Assets
  überschrieben oder entfernt. Ein beschädigter/unklarer Gesamtkandidat blockiert
  den automatischen Teil vollständig.

Der bestehende Import behält auf Drive fehlende Motive und Kategorien bei.
Solche Löschwünsche werden nicht automatisch ausgeführt. Die manuelle Prüfung
bleibt erforderlich; der öffentliche Bericht nennt nur Gesamtzahlen.

## Frischer Inventurbeleg und offene PRs

`drive_sync.py --apply --additions-evidence <RUNNER_TEMP/datei.json>` schreibt nach
Erfolg einen privaten, kurzlebigen Inventurbeleg ausserhalb des Repositorys.
Er enthält ausschliesslich beobachtete Motiv-/Kategorie-IDs, Datei-Hashes,
Basiskommit, Lauf-ID, Versuch und Zeitstempel, keine Bildinhalte oder Ordnernamen.
Er wird weder ausgegeben noch als Artefakt hochgeladen. Der öffentliche Bericht
muss einen anderen Pfad haben.

Die Ergänzungsprojektion verlangt diesen Beleg passend zu HEAD, Kandidat,
GitHub-Lauf und Versuch sowie maximal einer Stunde Alter. Ein fehlender oder
abweichender Beleg blockiert die Übernahme. Dadurch werden neue Motive eines
älteren offenen PRs, die inzwischen aus Drive verschwunden sind, nicht irrtümlich
als aktuelle Ergänzungen veröffentlicht. Der bisherige PR-Seed führt weiterhin
nur Daten zusammen und führt niemals Programmcode aus dem Bot-Branch aus.

## Git- und Pages-Veröffentlichung nach späterer Aktivierung

Aus einem temporären Git-Index wird ein Commit mit genau einem Elterncommit
(dem vertrauenswürdigen Hauptstand) erstellt. Sein Diff enthält ausschliesslich
`catalog.json`, `data/categories.json`, `data/motifs-manifest.json` und die wirklich
benötigten neuen `assets/motifs/<id>/*.webp`. Konfiguration, Baseline,
Ausschlusszustand, App-Code und Workflows werden niemals automatisch übernommen.
Die übrigen Baumobjekte stammen exakt aus dem vertrauenswürdigen `main`.

Der Push verwendet ausschliesslich den kurzlebigen GitHub-Jobtoken, keine im Git
hinterlegten Zugangsdaten, keinen Force-Push und keine PR-Zusammenführung.
Ein konkurrierender normaler Hauptbranch-Commit wird beim Fast-forward-Push
abgewiesen. Ein Offline-Test prüft das mit einem echten lokalen Bare-Repository.
Nach erfolgreichem Push wird HEAD ohne Verwerfen der Arbeitsdateien auf den neuen
Hauptstand gesetzt. Die übrigen Kandidatenänderungen bleiben für den bisherigen
Draft-PR erhalten. Dadurch funktionieren auch gemischte und wiederholte Läufe.

Ein GitHub-Jobtoken-Push allein löst keinen normalen Pages-Build aus. Ein separater
Job mit ausschliesslich `contents: read` und `pages: write` fordert deshalb später
über die GitHub-API einen Build an. Vorher werden die bestehende Pages-Konfiguration
(`legacy`, Quelle `main`, Pfad `/`) und der aktuelle veröffentlichte Datencommit
geprüft. Es werden keine Pages-Einstellungen geändert und keine zusätzlichen
Dateien in GitHub hochgeladen. Der Job bestätigt den passenden fertigen Build
oder meldet Fehler/Timeout; er wiederholt den POST nicht.

Der vorbereitende Job behält seine bisherigen Rechte (`contents: write`,
`pull-requests: write`, `id-token: write`). GitHub kann Schreibrechte technisch
nicht auf diese Verzeichnisse einschränken; die Datenbegrenzung wird durch den
vertrauenswürdigen Publisher und dessen Tests erzwungen. Ein Ruleset darf nicht
umgangen werden. Blockieren Branchschutz oder Organisationsregeln den Jobtoken,
bleibt eine spätere automatische Veröffentlichung blockiert.

## Absichtlich AUS

Diese Implementierung aktiviert nichts. Im Workflow steht fest:

```
TIMBERART_AUTO_ADDITIONS_ARMED: 'false'
```

Zusätzlich wäre die Repository-Variable
`TIMBERART_AUTO_ADDITIONS_ENABLED` mit exakt `true` erforderlich. Auch eine bereits
vorhandene Variable kann den festen Schalter nicht übergehen. Die Voraussetzungen
werden im Workflow **und** im Publisher geprüft: korrektes Repository samt ID,
`schedule`, `refs/heads/main`, passender Hauptcommit und passender Remote.
Manuelle Inventur-/PR-Testläufe können niemals automatisch veröffentlichen.
Kein neuer Push-/PR-Trigger, kein neuer Zeitplan und keine neuen Schlüssel.

Erst nach ausdrücklicher späterer Freigabe: PR prüfen/übernehmen, Berechtigungen
und Branchschutz kontrollieren, kontrollierten vollständigen Inventur-/PR-Test
mit ausgeschalteter Veröffentlichung durchführen, danach den festen Schalter in
einem geprüften Commit und die Repository-Variable bewusst aktivieren. Der erste
stündliche Lauf muss beaufsichtigt und der Pages-Build kontrolliert werden.

## Grenzen und Wiederherstellung

- Kein Live-Drive-/Actions-/Pages-Test als Teil dieser Implementierung. WIF bleibt
  wie bisher auf `main` begrenzt; Entwicklungsbranch-Läufe sind kein Live-Test.
- Ein Drive-Scan ist keine globale transaktionale Momentaufnahme. Änderungen nach
  dem Scan werden erst im nächsten Lauf erkannt. Fehler während des Imports
  verhindern die Ergänzungsveröffentlichung.
- Metadatenänderungen werden konservativ manuell gehalten, auch wenn das Bild
  inhaltlich gleich bleibt. Neue Inhalte unter strittigen Kategorien ebenfalls.
- Git-Push, PR-Aktualisierung und Pages-Build sind keine gemeinsame Transaktion.
  Scheitert nach dem Datenpush die PR-Erstellung, der Build oder die Verbindung,
  kann der Datencommit bereits auf `main` liegen. Die bisherige Site bleibt bei
  einem fehlgeschlagenen Build bestehen. Es gibt keinen automatischen Rollback,
  Force-Push, Löschlauf oder unkontrollierten Wiederholungsversuch. Der Zustand
  ist anhand des Datencommits und der Build-Historie manuell zu prüfen.
- Die vorhandenen Bild-/Speicherbudgets bleiben bestehen (64 MiB Original,
  40 Mio. Pixel, 512 MiB referenzierte Vorschauen, 800 MiB Vorschau-Assets).
  Stündliche Actions-/Pages-Läufe können von GitHub verzögert werden.

## Tatsächlich ausgeführte lokale Prüfung

- Bestehende Python-Prüfungen: 37 Synchronisierungs-, acht Import- und sechs
  Verbindungstests, alle bestanden und ausschliesslich offline (zusammen mit
  den 29 neuen Tests insgesamt 80 Python-Tests).
- `tests/drive_additions_check.py`: 29/29 bestanden. Ergänzungen, gemischte Ersetzungen/Umbenennungen/
  Verschiebungen, verschachtelte und leere Kategorien, Ausschlüsse, aktuelle und
  fehlende Drive-Beobachtung, wiederholte Läufe, alter/fremder Inventurbeleg,
  beschädigte Bilder, Secrets, Code-/Workflow-Injektion, Git-Konflikte,
  deaktivierte/fremde Kontexte, Sanitierung und simulierte Pages-API-Ergebnisse.
- Zwölf bestehende Textmodelltests bestanden. Drei gezielte Browser-Skripte:
  Kategorien, App-/Designmappenfunktionen und beide Bestellsperren, jeweils
  Desktop/Tablet/Smartphone (Chromium, Touch emuliert).
- Der Kategorien-Browsertest hatte eine überholte feste Zahl von zehn Karten
  inklusive Testkategorie. Er verwendet jetzt die tatsächliche Basisanzahl plus
  eine simulierte neue Kategorie; keine Inhaltsprüfung wurde entfernt.
- Aktuelles `main` als Basis: 415 Motive, zehn Kategorien, 830 WebPs. Alle
  ursprünglichen 412 IDs bleiben enthalten. Katalog, Motivdateien, App,
  Textbearbeitung, Fonts, Speicherung und Bestellsperren wurden nicht verändert.

## Manueller Live-Dry-run ohne Veröffentlichung

Im bestehenden Workflow gibt es zusätzlich die manuelle Auswahl `dry-run`.
Nach einer separat freigegebenen Übernahme dieser Erweiterung auf `main`:

1. **Actions → Google Drive – prepare motif sync PR → Run workflow** öffnen.
2. Branch **main**, Modus **dry-run** auswählen und den Lauf bewusst starten.
3. Die Job-Zusammenfassung lesen. Nur feste Statusmeldungen und Gesamtzahlen
   erscheinen: neue Kategorien/Motive im Kandidaten, automatisch zulässige
   Ergänzungen sowie zurückgehaltene bestehende und neue Datensätze.

Der eigene Dry-run-Job liest den vorhandenen Sync-PR mit dem bisherigen sicheren
Seed, authentifiziert sich über die bestehende WIF-Verbindung und verwendet den
unveränderten Import mit `drive.readonly`. `--apply` schreibt Vorschauen und
Kandidatendaten ausschliesslich in die wegwerfbare Arbeitskopie des Runners.
Das ist kein Commit oder Push nach `main`. Danach laufen die bisherigen
Datenprüfungen und die identische Ergänzungsprojektion mittels
`drive_sync_additions.py --dry-run-summary`, ausdrücklich ohne `--publish`.

Berechtigungen dieses Jobs: `contents: read`, `pull-requests: read` zum Lesen des
Sync-PRs und `id-token: write` für WIF. Keine GitHub-Schreibrechte, PR-Erstellung,
Pages-Anforderung oder Artefakt-Uploads. Die bisherigen Jobs/Berechtigungen und
beide Aktivierungsschalter werden nicht verändert. Auch wenn später beide
Schalter eingeschaltet wären, veröffentlicht dieser manuelle Modus nichts.

Die acht Summen enthalten keine Namen, IDs, Quellpfade oder Zugangsdaten.
Zurückgehaltene Bestandsdatensätze umfassen auch beim aktuellen Scan nicht mehr
sichtbare Motive/Kategorien; sie werden weiterhin nicht gelöscht. Neue Kandidaten
aus offenen PRs zählen zur Kandidatenmenge, benötigen aber für die automatische
Zulässigkeit einen aktuellen passenden Inventurbeleg. Unbestätigte neue Inhalte
werden separat als zurückgehalten ausgewiesen. Die Zusammenfassung ersetzt einen
vorhandenen temporären Summary-Text, damit keine alten privaten Inhalte angehängt
werden. Sie darf nicht dieselbe Datei wie der private Inventurbeleg verwenden.

Voraussetzungen: Erweiterung auf `main`, zulässige Actions und lesender Zugriff
auf den Sync-PR sowie bestehende WIF-/Drive-Freigabe. Eine Ausführung auf einem
Entwicklungsbranch wird durch Workflow und WIF weiterhin nicht zugelassen.
Es ist keine Aktivierung der Veröffentlichungsvariablen nötig. Fehler bei Import,
Kandidatenprüfung oder Inventurbeleg beenden den Lauf ohne Erfolgszusammenfassung.
Ein Dry-run bestätigt weder Hauptbranch-Schreibrechte noch Pages-Schreibrechte.

Gezielte lokale Prüfung dieser Ergänzung: 36 Ergänzungs-/Workflow-Tests und 37
bestehende Sync-Tests bestanden, ausschliesslich offline. Neue Fälle prüfen die
Zählung gemischter Änderungen, fehlende Drive-Beobachtung, geänderte Kategorien,
Datenschutz, unveränderten Git-Stand, gesperrte Veröffentlichungsaufrufe, auch bei
beiden eingeschalteten Schaltern, sowie den read-only Workflow. Kein Live-Lauf,
Merge, Deployment oder Aktivieren von Schaltern wurde dabei ausgeführt.
