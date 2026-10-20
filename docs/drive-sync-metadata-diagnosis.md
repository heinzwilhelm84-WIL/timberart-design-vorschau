# Einmalige manuelle Metadaten-Diagnose

Ziel: die Art einer Rückhaltung bestehender Motive erklären, ohne private
Quelldaten zu veröffentlichen. Neuer manueller Modus `diagnose-metadata` im
bestehenden Workflow. Kein Zeitplan für diesen Job, kein Import und keine
Veröffentlichung. Die bestehenden Aktivierungsschalter bleiben unverändert.

## Umfang und Sicherheit

Der Job liest den ausgecheckten Katalog, das Manifest, die Kategoriebindungen,
die Quellenkonfiguration und den gespeicherten Ausschlusszustand. Er verwendet
`inventory`, `source_data`, die gleiche Metadatenprojektion wie `convert_record`
und die vorhandene Wiederverwendbarkeitsprüfung. Kein Seed aus offenen PRs:
Vergleichsbasis ist ausschliesslich der beim Start ausgewählte main-Commit.

Google: vorhandene WIF-Authentifizierung, nur `drive.metadata.readonly`,
kurzlebiges Token (900 Sekunden), keine Schlüssel- oder Credentialdatei.
GitHub: nur `contents: read` und `id-token: write`; keine PR-/Pages-Schreibrechte.
Keine Originaldownloads, keine neuen WebPs, keine Änderungen am Arbeitskatalog,
keine Commits/Pushes. Die einzige Ergebnisdatei enthält feste Bezeichnungen und
Zahlen im temporären Runnerverzeichnis; nur diese wird als Job-Zusammenfassung
angezeigt. Keine privaten Berichte, Rohdaten, Caches oder Upload-Artefakte.
Fehlertexte aus API oder Quelldaten werden nicht ausgegeben.

## Ergebnis lesen

- Nicht sichtbare Bestandsmotive: beim vollständigen Scan nicht erkannt. Dies
  beweist keine Löschung; Berechtigungen, Ausschlüsse oder ein anderer Dateityp
  können ebenfalls die Ursache sein. Bei einem fehlgeschlagenen Scan gibt es
  keinen Erfolgsbericht.
- Metadatenprojektion abweichend: feste Zähler nennen betroffene Felder, darunter
  Dateiname, Änderungszeit, Dateiversion, Prüfsumme, Grösse und Ordnerzuordnung.
  Der Quell-Fingerprint wird separat auf Konsistenz geprüft.
- Wiederverwendbares Bild und abweichende Metadaten: der aktuelle Import würde
  den bestehenden Datensatz allein wegen dieser Metadaten zurückhalten, ohne
  einen neuen Bilddownload zu benötigen.
- Bildverifikation erforderlich: Inhalt, gespeicherter Inhalts-Fingerprint,
  Importversion oder Vorschaugenerator erlauben keine sichere Wiederverwendung.
  Diese Diagnose lädt kein Bild; Unterschiede der tatsächlichen Vorschauen oder
  ihrer Erzeugungsmetadaten bleiben dann ausdrücklich unbewertet.

Feldzähler können dasselbe Motiv mehrfach betreffen. Der Gesamtzähler der durch
Metadaten/Sichtbarkeit erklärten Rückhaltungen zählt jedes Motiv nur einmal.
Die Angaben beziehen sich auf die aktuelle Drive-Aufnahme; der historische
Dry-run lässt sich ohne dessen inzwischen verworfene private Kandidatendaten
nicht exakt rekonstruieren. Ein Scan ist keine atomare Drive-Momentaufnahme.

## Späterer kontrollierter Start

Dieser PR startet selbst nichts. Die bestehende OIDC-Bedingung erlaubt nur
`refs/heads/main`. Deshalb ist ein authentifizierter Lauf vom Entwicklungsbranch
nicht möglich und wird vom Job zusätzlich ausgeschlossen. Keine Bedingung lockern.
Nach separat freigegebener Übernahme in main: Actions → bestehender Drive-Sync →
Run workflow → Branch main → Modus `diagnose-metadata`, einmal manuell ausführen.
Andere Jobs mit Schreibrechten bleiben für diesen Modus ausgeschlossen. Es gibt
keine dauerhafte Einmal-Sperre; der Modus könnte bewusst erneut manuell gestartet
werden, jedoch niemals vom stündlichen Zeitplan.

Falls die aggregierten Felder zur eindeutigen Zuordnung nicht reichen: eine
berechtigte Person kann denselben Vergleich auf einem vertrauenswürdigen lokalen
Rechner mit kurzlebiger, lesender Google-Authentifizierung untersuchen. Die
Zuordnung bleibt in Arbeitsspeicher/privater lokaler Sitzung. Keine Zugangsdaten
per Chat anfordern, keine IDs/Dateinamen in öffentliche Issues/PRs/Logs oder
Artefakte kopieren. Ein privater Detail-Export ist hier absichtlich nicht eingebaut.

## Gezielte Offline-Prüfungen

Siehe `tests/drive_diagnosis_check.py`: unveränderter Bestand, Feldänderungen,
fehlendes Motiv, Umbenennung/Verschiebung von Ordnern und Motiven, inkonsistenter
Fingerprint, alte Importdaten/Generator, persistente Ausschlüsse, keine Downloads
oder Katalogschreibzugriffe, generische Fehler, ausgeschlossene Importoptionen,
kein privater Inhalt im Bericht und manuelle Workflow-/Berechtigungsgrenzen.

Tatsächlich ausgeführt (Offline, 2026-10-20):

```text
python -B tests/drive_diagnosis_check.py                         14 bestanden
python -B tests/drive_sync_check.py                             37 bestanden
python -B tests/drive_additions_check.py                        36 bestanden
python -B tests/drive_connection_check.py                        6 bestanden
python -B -m unittest discover -s tests -p import_check.py        8 bestanden
```

Insgesamt 101 bestandene Tests. Die Diagnoseprüfung enthält ausdrücklich die
Kombination „ein neues Motiv + ein bestehendes Motiv mit neuer Dateiversion bei
gleicher Inhaltsprüfsumme“ und bestätigt die Übereinstimmung mit dem Importer.
Die Fehlermeldungen in negativen Tests sind erwartete Ablehnungen. Kein Live-Test,
kein Workflow-Start und keine Browser-Testserie; App und Browsercode unverändert.
