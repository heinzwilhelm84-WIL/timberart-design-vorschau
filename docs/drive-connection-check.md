# Vorbereitung: manueller Google-Drive-Verbindungstest

Stand: 19.10.2026. Kein Live-Test, keine Google-Konfigurationsänderung und kein
Workflow-Dispatch wurden bei der Vorbereitung ausgeführt. Der Workflow hat
ausschliesslich `workflow_dispatch`, keinen Zeitplan, Push-/PR-Trigger oder Deploy.

## Verifizierter Repository-Stand

- Repository: `heinzwilhelm84-WIL/timberart-design-vorschau`, ID **1425353605**,
  Standardbranch `main`.
- Ausgangscommit für diesen Entwicklungsbranch:
  `9243654948b27551f07edf1dff00a81e80e89d33`.
- `motifs.sources.json` enthält genau einen Hauptordner:
  **12OdcNV5wB5S1H471D0F8th9EJ2LFrJ6G**. Die Konfiguration bleibt unverändert.
- Der letzte lokale Bildbranch wurde bereits vom Benutzer nach `main` übernommen.
  Die Verbindungstest-Vorbereitung verändert keine Motive oder App-Funktionen.
- Die Repository-API bestätigt die ID und Schreibberechtigung für den separaten
  Branch. Die Actions-Einstellungs-APIs antworteten für den vorhandenen
  API-Zugang mit HTTP 403; die dortigen Richtlinien sind deshalb nicht verifiziert.

## Vorgesehene Google-Konfiguration

Diese Werte wurden vom Benutzer bereitgestellt und unverändert im Workflow
hinterlegt. Ihre tatsächlichen Google-IAM-Einstellungen sind **nicht live geprüft**:

- Projektnummer: `949832006175`
- Projekt-ID aus der Dienstkonto-Adresse: `banded-meridian-424821-j9`
- Pool: `timberart-github-sync`
- Anbieter: `timberart-github-actions`
- Vollständige Anbieterkennung:
  `projects/949832006175/locations/global/workloadIdentityPools/timberart-github-sync/providers/timberart-github-actions`
- Dienstkonto:
  `timberart-drive-sync@banded-meridian-424821-j9.iam.gserviceaccount.com`
- Freigegebener Hauptordner laut Benutzer: `TimberArt_Designs`, Rolle Betrachter.

Die folgenden Voraussetzungen sind bei Google zu kontrollieren, bevor später
bewusst ein Live-Test gestartet wird:

1. Pool und Anbieter sind aktiviert. `google.subject` ist gültig gemappt;
   `attribute.repository_id` ist auf `assertion.repository_id` gemappt.
2. Die Anbieterbedingung beschränkt die Repository-ID auf `1425353605` und den
   GitHub-Ref auf `refs/heads/main`. Bei Bedingungen über `attribute.ref` muss auch
   dieser Wert entsprechend gemappt sein.
3. Die IAM-Bindung **am Dienstkonto** erlaubt `roles/iam.workloadIdentityUser` für:
   `principalSet://iam.googleapis.com/projects/949832006175/locations/global/workloadIdentityPools/timberart-github-sync/attribute.repository_id/1425353605`
4. Neben der laut Benutzer aktivierten Drive API müssen die für WIF und das
   Erzeugen des Access-Tokens benötigten APIs, insbesondere IAM Service Account
   Credentials (`iamcredentials.googleapis.com`) und Security Token Service
   (`sts.googleapis.com`), verfügbar/aktiviert sein. Keine API wurde hier aktiviert.
5. Der Hauptordner und seine relevanten Unterordner sind für das Dienstkonto
   tatsächlich lesbar; eingeschränkte Unterordner können eigene Freigaben benötigen.

Keine Editorrolle, keine Domain-Wide Delegation, kein privater Schlüssel und kein
persönlicher Google-OAuth-Refresh-Token sind für diesen Test vorgesehen. Eine
zusätzliche pauschale Token-Creator-Rolle wird nicht vorsorglich verlangt.
Die oben genannten IDs und die Dienstkonto-Adresse sind keine Zugangsdaten.

## Minimaler Workflow und Sicherheitsgrenzen

Dateien:

- `.github/workflows/drive-connection-check.yml`: manueller Test mit zwei Actions.
- `tools/check_drive_connection.py`: Python-Standardbibliothek, keine Installation.
- `tests/drive_connection_check.py`: ausschliesslich lokale Simulationen.

Die offiziellen Actions wurden beim Vorbereiten per Git-Referenz verifiziert und
auf feste Commits gebunden:

- `actions/checkout` v6: `d23441a48e516b6c34aea4fa41551a30e30af803`
- `google-github-actions/auth` v3: `7c6bc770dae815cd3e89ee6cdf493a5fab2cc093`

GitHub-Berechtigungen: ausschliesslich `contents: read` für Checkout und
`id-token: write` für OIDC. Es gibt keine Inhalts-, PR-, Actions- oder Pages-
Schreibberechtigung. `id-token: write` gestattet die OIDC-Token-Ausgabe und ist
keine Berechtigung zum Schreiben von Drive-Dateien.

Google-Scope: **`https://www.googleapis.com/auth/drive.metadata.readonly`**.
Dieser Test braucht keine Bildinhalte; deshalb wird der weitergehende Scope
`drive.readonly` nicht angefordert. Das Access-Token ist auf 600 Sekunden
angefordert; der Job hat höchstens fünf Minuten Laufzeit. Es wird nur dem
Prüfschritt als Umgebungsvariable übergeben. Es wird keine Zugangsdaten-Datei
erzeugt, kein Token gedruckt und kein Token in Git-Konfigurationen gespeichert.

Der Checkout beschränkt sich auf die Quellkonfiguration und das Prüfskript,
verwendet den exakten Run-Commit und speichert keine GitHub-Zugangsdaten.
Es gibt weder Artefakt-Upload noch Cache, Synchronisierung, Bildverarbeitung,
Drive-Schreibaufrufe, Bestellversand oder Deployment. App/CSP/Formulare bleiben
unverändert. Der Prüfcode verwendet ausschliesslich GET und lehnt Umleitungen ab,
damit ein Bearer-Token nicht an einen anderen Host weitergegeben wird.

## Was ein späterer Test tatsächlich prüft

1. Die Auth-Action tauscht GitHub-OIDC gegen ein OAuth-Access-Token des angegebenen
   Dienstkontos mit dem reinen Metadaten-Scope.
2. Die Hauptordner-ID wird aus `motifs.sources.json` gelesen. Bei mehreren Roots
   oder ungültiger Konfiguration bricht der Test ab, statt einen Ordner zu erraten.
3. Ein Metadaten-GET prüft ID, Typ Ordner, nicht im Papierkorb und den erwarteten
   Hauptordnernamen `TimberArt_Designs`.
4. Der Test fragt ausschliesslich **Unterordner** ab, mit vollständiger Pagination,
   und liest rekursiv die Ordnerlisten jedes gefundenen Unterordners. Anders als
   der Motivimport werden auch LOGO-/Schriften-Ordner auf Lesbarkeit geprüft;
   die Import-Ausschlüsse bleiben unverändert.
5. Erst nach vollständig erfolgreicher Traversierung erscheinen PASS-Meldungen und
   die Anzahl direkter/aller lesbaren Unterordner sowie die maximale Tiefe.
   Keine Bildnamen, Ordnerlisten, Rohantworten oder Originaldateien werden geloggt.

Bei 401/403/404, ungültigen Antworten, unvollständiger Suche oder Pagination,
Zyklen und Grenzüberschreitungen wird kein Erfolg gemeldet. Sicherheitsgrenzen:
1 MiB je Metadatenantwort, 1000 Ordner einschließlich Root, 100 Seiten je Ordner,
15 Sekunden je HTTP-Anfrage, fünf Minuten Joblaufzeit. Null lesbare Unterordner
werden als Fehler behandelt, weil für dieses Motivverzeichnis Unterordner erwartet
werden. Diese Grenzen können bei Bedarf später gezielt angepasst werden.

Ein erfolgreicher Test beweist Zugriff auf den Hauptordner und alle vom Dienstkonto
sichtbaren/erreichbaren Unterordner. Vollständig versteckte Unterordner lassen sich
ohne Vergleich mit einer Eigentümer-Inventur nicht erkennen. Der Test beweist
bewusst **nicht** das Herunterladen von Bildern oder die Funktionsfähigkeit einer
späteren Synchronisierung. Er verändert keine Freigaben.

## Ausführung unter der bestehenden main-Bedingung

**Aktuell kann dieser Test unter allen genannten Bedingungen nicht live ausgeführt
werden.** Der Entwicklungsbranch dient nur der Vorbereitung und Prüfung.

- GitHub benötigt die manuell startbare Workflow-Definition auf dem Standardbranch.
- Die Google-Bedingung erlaubt nur OIDC-Tokens mit `ref == refs/heads/main`.
- Zusätzlich überspringt der Job jeden Run von anderen Refs oder Repositorys.
- Ein Checkout von `main` innerhalb eines Branch-Runs ändert dessen OIDC-Ref nicht.
  Auch ein PR-Run ist kein zulässiger Ersatz. Die Google-Bedingung wird nicht gelockert.

Erst nach einer **später ausdrücklich freigegebenen** Übernahme der geprüften
Workflow-/Skriptdateien auf `main` kann der Eigentümer den Test manuell ausführen:

1. In GitHub Actions müssen die beiden offiziellen Actions zugelassen sein und
   OIDC verfügbar sein. Der Startende benötigt Schreibzugriff auf das Repository.
2. Actions → „Google Drive – read-only connection check“ → „Run workflow“ →
   Branch **main**. Kein anderer Branch und kein Zeitplan.
3. Ergebnis anhand beider Auth-/Metadatenschritte auswerten. Ein übersprungener
   Branch-Run gilt nicht als Verbindungserfolg.

Alternativ ist **erst dann** der folgende manuelle CLI-Aufruf möglich; er wurde
hier ausdrücklich **nicht ausgeführt**:

```sh
gh workflow run drive-connection-check.yml \
  --repo heinzwilhelm84-WIL/timberart-design-vorschau \
  --ref main
```

Das Übernehmen von Dateien nach `main` kann bei einer bereits auf main basierenden
Pages-Konfiguration einen separaten Pages-Build auslösen. Daher wird auch diese
Übernahme hier nicht vorgenommen und muss vor einem späteren Live-Test gesondert
mit der Vorgabe „keine Veröffentlichung“ abgestimmt werden. Der Testworkflow
selbst hat keinen Deploy-Schritt und keine Pages-Berechtigung.

## Vorbereitungsprüfung und Quellen

YAML-/Python-Struktur, feste Action-Referenzen, Berechtigungen und Ref-Sperren
wurden statisch geprüft. Sechs lokale Offline-Prüfungen bestanden: eindeutige
Ordnerkonfiguration, rekursive/paginierte Ordnerlisten mit ausschliesslich GET,
fehlgeschlagene HTTP-Antworten ohne Token-Ausgabe, Sperre von Media-Endpunkten
und Umleitungen, fehlerhafte/unvollständige Ordnerbäume sowie sichere Fehlerlogs.
Diese Prüfungen nutzten simulierte Antworten und einen ausdrücklich unechten
Sentinel statt eines Tokens; Netzwerkverbindungen waren im Test blockiert.
Das ist kein Nachweis einer erfolgreichen Google-Verbindung. Es wurde kein
Actions-Lauf gestartet.

Reproduzierbare **Offline-Prüfung**, ohne Authentifizierung oder Drive-Zugriff:

```sh
python3 -B tests/drive_connection_check.py
```

Das Prüfsystem testet den Hilfscode lokal, nicht den Actions-/OIDC-Ablauf.

- [Offizielle Auth-Action](https://github.com/google-github-actions/auth)
- [Manueller Workflow-Start](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
- [Drive files.list](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list)
- [Drive-Berechtigungsbereiche](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
