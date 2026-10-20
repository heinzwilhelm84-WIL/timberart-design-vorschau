# Prüfbericht: stündliche Google-Drive-Synchronisierung

Stand: 20.10.2026. Neuer lokaler Branch `feature/drive-sync-stundenplan`.
Basis: `5015180070666a4d3fc137dcc45b3e3ce7296b27`, übernommener PR #7.
Der Merge wurde ausschliesslich lesend über GitHub bestätigt; main wurde lokal
eingelesen. Keine Änderungen auf GitHub übertragen, kein neuer Commit, kein
Workflow gestartet, kein Drive-Zugriff, kein Merge oder Deployment ausgeführt.
Der Zeitplan ist somit noch nicht auf GitHub aktiviert.

## Änderung

- In `.github/workflows/drive-motifs-sync.yml` ist der vorbereitete Cron-Auslöser
  `17 * * * *` unter `on.schedule` eingetragen. GitHub verwendet UTC.
- Manueller Start bleibt erhalten. Inventur ist weiterhin nur manuell möglich.
  Ein Zeitplanereignis wählt nur den bestehenden PR-Vorbereitungsjob aus.
- Jobs, Actions, Berechtigungen, WIF-Konfiguration, Google-Lesescopes, Draft-PR-
  Einstellung, feste Bot-Branch-Zuordnung und Pfad-Allowlist bleiben unverändert.
- Gemeinsame Concurrency-Gruppe, `cancel-in-progress: false`: keine gleichzeitigen
  Importe desselben Workflows und kein automatischer Abbruch des laufenden Imports.
- Kein automatischer Merge und kein Pages-/Deployment-Schritt. Keine Push-/PR-
  Auslöser ergänzt. Ausschliesslich dieses Vorschau-Repository auf main zugelassen.

## Tatsächlich ausgeführte Offline-Prüfungen

```sh
python3 -B tests/drive_sync_check.py
python3 -B -m unittest discover -s tests -p 'import_check.py' -v
python3 -B tests/drive_connection_check.py
python3 -B tools/sync_motifs.py --validate
env -u TIMBERART_TEST_SCREENSHOTS python3 -B tests/order_safety_check.py
env -u TIMBERART_TEST_SCREENSHOTS python3 -B tests/local_images_check.py
git diff --check
```

Alle Befehle bestanden. 37 Sync-/Workflow-Tests, acht Importtests und sechs
Verbindungstests: **51 Python-Tests, null Fehler im abschliessenden Lauf**.
Die zuvor vorhandenen 49 Tests sind enthalten; zwei zusätzliche Tests prüfen
Zeitplan-Ereignisauswahl und wiederholtes Einlesen eines offenen Sync-PRs.
Die Strukturprüfung wurde an den nun vorgesehenen Stundenplan angepasst.
Google- und GitHub-API-Aufrufe dieser Tests sind simuliert.

Der neue lokale Git-Integrationstest enthält einen offenen PR mit einem geänderten
Bestandsmotiv sowie einer neuen Kategorie und einem neuen Motiv. Zweimaliges
Einlesen und erneutes Synchronisieren erhält alle IDs, Kategorien und Bildbytes:
**null erneute Downloads, null Original-Bildaufbereitungen, null geänderte
Ausgabedateien** nach dem Einlesen des PR-Datenstands. Eine unerwartete erneute
Bildaufbereitung lässt den Test explizit fehlschlagen. Bestehende Tests bestätigen
zusätzlich: parallele Ergänzungen auf main und Bot-Branch bleiben erhalten;
Konflikte, entfernte Identitäten, fremder Code, Fork-Daten und veränderte PR-Heads
werden abgelehnt. Code aus dem Bot-Branch wird nicht ausgeführt.

Die Ereignismatrix prüft die tatsächlichen Job-Bedingungen: schedule -> prepare;
manuelle Inventur -> inventory; manuelle prepare-pr-Auswahl -> prepare;
Push, Pull Request, fremdes Repository, falsche Repository-ID und Entwicklungsref
-> kein Job. Permissions, gepinnte Actions, Draft-PR und Ausgabe-Allowlist geprüft.

Beide Browser-Skripte bestanden bei 1440/820/390 px in Chromium mit Maus bzw.
emuliertem Touch. Alle 824 referenzierten WebPs laden unter Pages-Unterpfad und
werden decodiert. Alte Entwürfe, Favoriten, Texttransformationen, Designmappe und
Vergleich bleiben nutzbar. Beide ausgefüllten Bestellformulare versenden auch bei
wiederholter Betätigung keine Daten; keine Formularrequests/fetch/XHR/Beacon.
Native Übermittlung wird auch ohne App-JavaScript von der CSP gesperrt.
Externe HTTPS-Aufrufe wurden in diesen Browserprüfungen blockiert.

## Bestand und Sicherheit

Lesender Git-/Python-Vergleich mit der Basis: Katalog, Herkunftsmanifest,
Kategorie-Datei, sämtliche Bilder, Quellenausschlüsse und App-/Importercode
unverändert. 412 eindeutige Motiv-IDs, neun Kategorien, 824 referenzierte WebPs,
177.108.798 Bytes. Physisch liegen 1076 WebPs vor, weil die im Erstimport
ersetzten 252 Vorschauen bewusst erhalten blieben. Keine zusätzlichen Duplikate
durch diese Änderung. Alle 412 Motive besitzen einen wiederverwendbaren
Original-Fingerprint. `LOGO`, `Schriften`, gespeicherte Ausschluss-IDs und
`deleteMissing: false` bleiben erhalten.

Syntax, Git-Whitespace und bekannte Geheimnismuster in geänderten Dateien geprüft.
Keine Zugangsdaten oder Originalbilder hinzugefügt. Berichte bleiben auf feste
Statusmeldungen und Gesamtzahlen beschränkt. Ein späterer öffentlicher Daten-PR
enthält weiterhin App-Motivnamen, IDs und Herkunftszuordnungen; vertrauliche
Quellen dürfen nicht ungeprüft zur Veröffentlichung vorgesehen werden.

## Grenzen und weitere Freigabe

Kein echter Zeitplanlauf, keine erneute Google-Authentifizierung und keine echte
PR-Aktualisierung ausgeführt. Der bereits erfolgreiche Erstimport ist die Basis,
kein Ersatz für einen späteren beobachteten Zeitplanlauf. Drittanbieter-PR-Action
und serverseitige Rechte wurden nicht live schreibend getestet. Physische Geräte
und ein neuer Qualitätsvergleich mit Google-Originalen wurden nicht geprüft.

Unveränderte Originale werden weder heruntergeladen noch neu aufbereitet. Lokale
WebPs werden weiterhin zur Integritätskontrolle gelesen/decodiert; der Lauf führt
ausserdem eine Metadateninventur aus. Ohne MD5 kann die vorhandene konservative
Versionsprüfung zusätzliche Downloads verursachen. Alle aktuell 412 importierten
Einträge erfüllen bei unveränderten gespeicherten Quelldaten den Wiederverwendungscheck.

GitHub-Zeitpläne können verzögert oder ausgelassen werden und nach 60 Tagen ohne
Repository-Aktivität deaktiviert werden. Der manuelle Start bleibt als Ausweichweg.
Der Zeitplan wirkt erst auf dem Standardbranch. Die weitere Reihenfolge lautet:
erst ausdrückliche Freigabe für Commit/Push dieses Entwicklungsbranches, danach
separate Prüfung/Freigabe einer Übernahme auf main. Ein solcher manueller Merge
kann eine bestehende main-basierte Pages-Konfiguration auslösen und muss hinsichtlich
Veröffentlichung gesondert abgestimmt werden. Der Sync-Workflow selbst veröffentlicht
keine Webseite und führt keine PRs automatisch zusammen.
