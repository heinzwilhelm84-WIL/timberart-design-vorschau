# Automatischer Motivabgleich – Implementierung, noch nicht aktiviert

Stand: 19.10.2026. Lokaler Entwicklungsbranch `feature/drive-sync-automatik`,
Basis `d9b8bf6` (vom Benutzer übernommener erfolgreicher Verbindungstest).
Diese Vorbereitung startet keinen Live-Abgleich, keinen Push, PR, Merge oder Deploy.

## Daten und stabile Kategorien

`data/categories.json` enthält die neun bisherigen Kategorien mit festen
`legacy-…`-IDs und unveränderten bisherigen Kategorie-Schlüsseln. Die tatsächlichen
Drive-Ordner-IDs sind noch unbekannt und werden **nicht geraten**. Die erste
Inventur ordnet sie anhand vorhandener Motiv-IDs und eindeutiger Ordnernamen zu.
Mehrdeutige oder widersprüchliche Erstzuordnungen brechen mit einer festen,
metadatenfreien Meldung ab. Namenshinweise werden auch in tieferen Ordnern geprüft.
Ein Motivfund in einem anderen Ordner überstimmt keinen passenden Ordnernamen.
Ein erstmals erkannter, verschobener/umbenannter Unterbaum ohne eindeutige
Zuordnung verlangt ebenfalls eine private Prüfung statt einer Bindung an seinen
neuen Hauptordner. Bereits gespeicherte Ordnerbindungen bleiben bei Umbenennung
und Verschiebung unverändert.

Neue Kategorien erhalten `drive-<Ordner-ID>` als ID und Schlüssel, unabhängig vom
Namen und Speicherort. Eltern-ID und Anzeigename können sich ändern. Tiefere Ordner
erscheinen mit ihrem Pfad als Beschriftung, auch leere Kategorien sind sichtbar.
Alte Kategorie-Schlüssel bleiben gültig, damit gespeicherte Entwürfe weiterhin
aufgelöst werden. Die Oberfläche lädt die Kategorien zusätzlich zum Katalog;
bei einer nicht ladbaren Kategorien-Datei bleibt der bisherige Katalog nutzbar.

`motifs.sources.json` behält Hauptordner und Ausschlüsse `LOGO`/`Schriften` sowie
`deleteMissing: false`. `excludeFolderIds` erlaubt weitere explizite Ausschlüsse.
Beim ersten vollständigen Übernehmen werden erkannte ausgeschlossene Ordner-IDs
in `data/drive-sync-state.json` festgehalten. Ihre spätere Umbenennung führt nicht
versehentlich zum Import. Diese Datei entsteht erst im freigegebenen Live-Abgleich.
Weitere nicht als Motive gedachte Ordner müssen vor der Übernahme über die
Ausschlusskonfiguration identifiziert werden. Ein fehlendes Motiv oder eine
fehlende Kategorie bleibt lokal bestehen und wird im Bericht aufgeführt.

**Elf Drive-Unterordner sind vom Benutzer gemeldet, nicht in diesem Branch live
inventarisiert.** Die echten Namen/IDs und damit die tatsächlichen zwei Ausschlüsse
sind noch nicht unabhängig bestätigt. Die Offline-Simulation mit elf Ordnern
besteht aus neun Motivordnern plus LOGO und Schriften. Sie ersetzt keine Inventur.

## Inkrementeller Import

`tools/drive_sync.py` nutzt ausschliesslich authentifizierte GETs der Drive API,
keinen öffentlichen Thumbnail-Fallback und keine Weiterleitung von Bearer-Tokens.
Es liest alle Seiten und berücksichtigt unvollständige Suchen, Zugriffsfehler,
Duplikate und Grenzen. Drive-Datei-ID bleibt Motiv-ID; Umbenennen oder Verschieben
ändert sie nicht. Löschen und erneutes Hochladen ist eine **neue** Datei-ID: Das
alte Motiv bleibt erhalten, es wird nicht anhand des Dateinamens zusammengeführt.

Neue/geänderte Rasterdateien werden nur im Arbeitsspeicher gelesen. Originale
werden weder geschrieben noch auf Drive bearbeitet, gecacht oder veröffentlicht.
MD5 wird, falls vorhanden, nach dem Download geprüft. EXIF-Ausrichtung,
Transparenz und Farbprofilkonvertierung nach sRGB werden berücksichtigt;
EXIF/XMP/Kommentare/ICC werden nicht in die neuen WebPs übernommen.

Zwei Varianten: verlustfreies WebP, längste Kante maximal 600/1600 Pixel,
Seitenverhältnis erhalten, keine Hochskalierung. Die Pixel des verkleinerten
Referenzbilds werden mit den bestehenden Varianten verglichen. Bei Gleichheit
bleiben deren Bytes und Pfade bestehen; nur abweichende Varianten werden erzeugt.
Inhalts-Hashes verhindern doppelte gleichnamige Dateien und erkennen Kollisionen.
Alte Vorschauversionen werden nicht automatisch entfernt.

Die bestehenden 412 Herkunftseinträge enthalten noch keine Prüfsumme des
Drive-Originals. Daher ist beim ersten vollständigen Abgleich eine **einmalige
Verifikation der 412 lesbaren Originale** notwendig. Die öffentliche Inventur meldet
hierfür nur die Anzahl `unverifiedExisting` und geplanter Downloads, keine
Originalgrössen oder Quelldetails.
Danach verhindert ein unveränderter Original-Fingerprint erneute Downloads und
Verarbeitung. Eine Encoder-/Pipeline-Änderung erfordert bewusst neue Verifikation.
Ohne MD5 muss konservativ die Dateiversion verwendet werden, was bei reinen
Metadatenänderungen zusätzliche Prüfungen verursachen kann.

Einmalige Pixelunterschiede können auch aus der besseren Originalauflösung statt
der bisherigen Drive-Thumbnails entstehen. Der erste PR muss deshalb besonders
auf Bildqualität geprüft werden. Aktuelle Entwürfe speichern Motiv-IDs, keine
unveränderlichen historischen Bildkopien: Ein aktualisiertes Motiv wird auch in
alten Entwürfen aktuell angezeigt. Text/Position/Skalierung/Rotation bleiben erhalten.

Grenzen: 64 MiB pro Original, 40 Millionen Pixel, 1000 Ordner je Root,
20.000 geeignete Dateien, 100 Seiten pro Ordner, 10.000 HTTP-Versuche und
512 MiB referenzierte Vorschauen bzw. 800 MiB aller Vorschau-Dateien einschließlich
alter Versionen. Bei Erreichen des Budgets ist eine manuell geprüfte Bereinigung
erforderlich; auch die Git-Historie wächst mit Änderungen. Animierte Rasterbilder, fehlerhafte Decoder-
oder Farbprofildaten werden abgelehnt; SVG/PDF/Office und andere nicht konfigurierte
MIME-Typen werden nur gezählt und nicht verarbeitet. Drive-Verknüpfungen werden
nicht verfolgt; gemeint sind echte Unterordner. Rate-Limit-/Serverfehler werden
begrenzt mit Backoff wiederholt. Ein Fehler blockiert die gesamte Übernahme.
Erst nach Erfolg aller Bilder werden JSON und WebPs angewandt und erneut geprüft;
bei abschliessenden Validierungsfehlern werden alle geschriebenen Dateien zurückgesetzt.

## Workflow und Berechtigungen

`.github/workflows/drive-motifs-sync.yml` ist **ausschliesslich manuell startbar**.
Der Stundenplan ist lediglich als Kommentar vorbereitet (`17 * * * *`). Kein
`schedule`-Ereignis ist registriert. Beide Jobs erlauben nur das feste Repository
1425353605 auf `refs/heads/main`. Die Stundenplan-Logik ist für eine spätere,
separat freizugebende Aktivierung vorhanden, löst derzeit aber nichts aus.

- `inventory` (Voreinstellung): `contents: read`, `id-token: write`;
  Google-Scope `drive.metadata.readonly`. Keine Bilder und keine PR-Schreibrechte.
- `prepare-pr`: zusätzlich notwendiges `contents: write` und
  `pull-requests: write`; Google-Scope `drive.readonly`, da Inhalte gelesen werden.
  Kein Google-Schreibscope, kein Pages-/Deployment-Schreibrecht.

Authentifizierung erfolgt mit der vorhandenen WIF-Anbieterkennung und dem
Dienstkonto, ohne private Schlüssel oder Refresh-Tokens. Tokens werden nur an den
jeweiligen Importprozess übergeben, ohne Zugangsdaten-Datei. Actions sind auf
verifizierte Commit-Referenzen gebunden; Pillow bleibt auf die bestehende Version
gepinnt. Standard-Ubuntu-Runner und die freien Bibliotheken benötigen keinen neuen
kostenpflichtigen Dienst. Laufzeit-/API-/Speicherquoten sind weiterhin einzuhalten.

Der Bericht liegt nur in `RUNNER_TEMP` und wird in der Job-Zusammenfassung sowie
im PR-Text angezeigt. Beide Modi verwenden dieselbe geschlossene Ausgabe:
feste Statusmeldungen und Gesamtzahlen für Ordner, Ausschlüsse und Bildänderungen.
Keine tatsächlichen Ordnernamen, Datei-/Ordner-IDs, Dateinamen, Pfade, MIME-Typen,
Dateigrössen oder Kategoriezuordnungen werden ausgegeben. Auch Fehler enthalten
keine Rohantworten oder dynamischen Exception-Texte; Zuordnungskonflikte verweisen
mit einer festen Meldung auf die private Prüfung. Interne Details bleiben nur im
Prozessspeicher, es gibt keine Option zum Export eines Detailberichts.
Es gibt **keinen Artefakt-Upload und keinen Originaldatei-Cache**. Unbekannte
API-Felder, Antworttexte und kurzlebige Download-Links werden nicht übernommen.
Bekannte Geheimnis-Muster führen vor einer Veröffentlichung zum Abbruch.

### Private Erstprüfung und bestätigte Bindungen

Die öffentliche Inventur ersetzt keine Prüfung der tatsächlichen Zuordnung.
Vor dem ersten vollständigen Import prüft der Eigentümer auf einem vertrauenswürdigen
Gerät die Drive-Ordner, ihre URLs/IDs, Ausschlüsse und vorhandenen Motiv-IDs direkt
in der Drive-Oberfläche. Keine Screenshots, Namen oder Detailtabellen in öffentliche
Issues, Actions-Logs, Job-Zusammenfassungen, PR-Texte oder Artefakte kopieren.
Alternativ ist nach eigener Freigabe eine lokale Metadatenprüfung in einer privaten
Sitzung möglich; diese Änderung startet eine solche Sitzung nicht.

Eine manuell geprüfte Erstzuordnung kann als private JSON-Datei **ausserhalb** des
Repositorys mit restriktiven Dateirechten bereitgestellt werden. Schema mit reinen
Platzhaltern: `{"version":1,"bindings":{"BESTEHENDE_KATEGORIE_ID":"GEPRUEFTE_ORDNER_ID"}}`.
Die Kategorie-ID wird aus `data/categories.json` übernommen; IDs und Schlüssel
werden nicht neu erzeugt. Der lokale CLI-Parameter lautet
`--category-bindings /privater/pfad/bindings.json`. Er kann einen Konflikt bewusst
auflösen, aber keine bereits gespeicherte Bindung umbiegen. Unbekannte Kategorien,
nicht sichtbare/ausgeschlossene Zielordner und doppelte Bindungen werden abgelehnt.
Der Parameter wird in öffentlichen Actions (`GITHUB_ACTIONS=true`) und bei einem
Dateipfad innerhalb des Repositorys abgelehnt. Die Datei wird weder kopiert noch
geloggt oder dem PR hinzugefügt. Bei Inventur bleibt die Entscheidung nur im RAM;
bei einem später separat freigegebenen lokalen `--apply` wird sie als normale
Kategoriebindung gespeichert. Bis zur geprüften Übernahme dieser Bindung muss
ein öffentlicher CI-Lauf mit demselben Konflikt weiterhin abbrechen.

Wichtig: Der anonyme Bericht macht **nicht** die generierten App-Daten anonym.
Ein späterer öffentlicher Motiv-PR enthält notwendigerweise Bilder, öffentliche
Motivnamen/IDs, Vorschaupfade und Herkunftszuordnungen in seinen Dateidiffs; die
PR-Action kann solche Pfade protokollieren. Auch Ausschluss-IDs werden im Sync-State
gespeichert. Vertrauliche Quellen dürfen daher nicht ungeprüft in `prepare-pr`
übernommen werden. Soll auch diese Zuordnung geheim bleiben, sind ein privater
Importprozess und eine gesonderte Bereinigung der öffentlichen Daten nötig;
der öffentliche Bericht allein kann das nicht leisten.

## PR-Erstellung und sicherer Wiederholungslauf

`prepare-pr` erstellt/aktualisiert einen **Entwurfs-PR** von
`bot/drive-motifs-sync` nach `main`, ohne Auto-Merge. Der Bot-Branch bleibt bestehen.
Die PR-Action wird auf `22a9089034f40e5a961c8808d113e2c98fb63676` (v7) gebunden.

`tools/drive_sync_guard.py` übernimmt von einem bereits offenen Sync-PR nur geprüfte
Daten und WebPs. Sein Programmcode wird niemals ausgecheckt oder ausgeführt.
Fork-PRs werden nicht als Datenquelle akzeptiert; PR-Head und gelesener Commit
müssen übereinstimmen. JSON-Einträge werden anhand ihrer IDs mit dem gemeinsamen Basisstand verglichen:
Neuzugänge auf main und im offenen PR bleiben erhalten; widersprüchliche Änderungen
verlangen eine manuelle Prüfung. Damit werden neue Motive eines noch nicht
gemergten PRs nicht versehentlich beim nächsten Lauf entfernt.

Eine Pfad-Allowlist erlaubt nur `catalog.json`, `data/categories.json`,
`data/motifs-manifest.json`, `data/drive-sync-state.json` und gehashte WebPs unter
`assets/motifs/`. Gelöschte Pfade, Symlinks, fremder Code, Originalformate oder
private Bildmetadaten in neuen Assets werden abgelehnt. Der Workflow verwendet
nur `git add` über die explizite Allowlist der PR-Action; kein pauschales Staging.
Wenn main während des Abgleichs weitergelaufen ist, muss der Lauf wiederholt werden.
Keine PR-/Workflow-Dateien aus Drive oder einem offenen PR werden ausgeführt.

Der GITHUB_TOKEN muss laut Repository-Einstellung PRs erstellen dürfen. Der
Branchschutz für main soll direkte Bot-Pushes und unkontrollierte Merges verhindern;
der Workflow selbst pusht nur seinen festgelegten Bot-Branch. Weitere CI-Läufe
auf token-erzeugten PRs können eine manuelle Freigabe verlangen. Die Bild-/ID-
Prüfung erfolgt deshalb schon vor der PR-Action. Ein Konflikt führt zum Abbruch,
nicht zum Überschreiben fremder Änderungen. Den Bot-Branch nicht manuell bearbeiten.

## Erster kontrollierter Live-Test – erst nach ausdrücklicher Freigabe

1. Jetzt nur lokalen Code prüfen. Kein Push und kein Live-Lauf wurde ausgeführt.
2. Erst nach separater Freigabe diesen Entwicklungsbranch übertragen und prüfen.
   Weil WIF nur main erlaubt, ist danach eine ausdrücklich freigegebene Übernahme
   auf main nötig, bevor der neue Workflow dort manuell gestartet werden kann.
   Eine bereits main-basierte Pages-Konfiguration kann auf einen main-Commit
   reagieren; das muss vor der Übernahme separat mit „keine Veröffentlichung“
   abgestimmt werden. Der Sync-Workflow selbst hat keinen Deployment-Schritt.
3. Zuerst Ordner, Ausschlüsse und Erstbindungen privat wie oben prüfen. Nach
   separater Freigabe Workflow auf **main**, Modus **inventory** starten: Dieser
   liest nur Metadaten und veröffentlicht ausschliesslich Status und Gesamtzahlen.
   Namen und Zuordnungen können nicht aus dem öffentlichen Bericht geprüft werden.
   Konflikte privat lösen, niemals öffentliche Detailausgaben einschalten.
4. Erst nach Freigabe dieses Inventurberichts `prepare-pr` einmal manuell starten.
   Er darf temporär Originalinhalte lesen und einen Entwurfs-PR erstellen. Keine
   Originalinhalte werden gespeichert oder veröffentlicht. Initiale Bildprüfung
   kann entsprechend länger dauern; Timeout ist 30 Minuten.
5. Entwurfs-PR auf alle IDs, Kategorien, Bilder und Bericht prüfen. Nichts wird
   automatisch gemergt oder auf Pages veröffentlicht. Ein zweiter, freigegebener
   Lauf mit unveränderten Quellen muss die gespeicherten Fingerprints wiederverwenden.
6. Erst später nach neuer Freigabe den vorbereiteten Stundenplan tatsächlich
   unter `on` eintragen. Ohne diesen Eintrag läuft nichts automatisch.

Der erfolgreiche Metadaten-Verbindungstest bestätigt noch nicht den Download von
Originalen. Der `drive.readonly`-Scope und Downloadrechte des Betrachters müssen
beim kontrollierten Bildtest funktionieren; eingeschränkte Freigaben können dies
verhindern. Vollständig unsichtbare Ordner/Dateien sind ohne Eigentümer-Inventur
nicht erkennbar. Die echte Drive-Inventur und der PR-Schreibzugriff wurden in dieser
Offline-Vorbereitung nicht erneut getestet.

## Reproduzierbare lokale Prüfungen

```sh
python3 -B tests/drive_sync_check.py
python3 -B -m unittest discover -s tests -p 'import_check.py'
python3 -B tests/drive_connection_check.py
python3 -B tools/sync_motifs.py --validate
python3 -B tests/sync_categories_browser_check.py
python3 -B tests/browser_check.py
python3 -B tests/transform_check.py
python3 -B tests/selection_check.py
python3 -B tests/order_safety_check.py
```

Die neuen Importtests simulieren Drive vollständig und sperren echte Netzwerk-
verbindungen. Browserprüfungen starten nur lokale HTTP-Server und blockieren externe
Ressourcen. Desktop 1440 px, Tablet 820 px und Smartphone 390 px werden in Chromium
mit Maus/Touch geprüft; keine physischen Geräte und keine echte Google-Anmeldung.

Ausführliches Ergebnis der durchgeführten Offline-Prüfungen:
[drive-sync-test-results.md](drive-sync-test-results.md).

Auch ein später aktivierter GitHub-Zeitplan ist kein Echtzeitdienst: Läufe können
sich verzögern. In öffentlichen Repositorys kann GitHub geplante Workflows nach
60 Tagen ohne Repository-Aktivität deaktivieren. Der manuelle Start bleibt daher
als Ausweichweg erhalten; der letzte erfolgreiche Lauf sollte kontrolliert werden.
