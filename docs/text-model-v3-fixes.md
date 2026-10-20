# Textmodell V3 – Korrektur der beiden Befunde aus PR #9

Branch: `feature/textmodell-v3`. Ausgangscommit:
`2350a5ace9f4847de563bd705a06175dfb9a7923`.
Lokale Korrektur; kein Commit, Push, Merge, Workflow-Start, Drive-Abgleich oder Deployment.

## Mehrere Tabs: Verhalten und Konfliktschutz

Favoritenänderungen werden ohne Reload in Navigation und Galerie übernommen.
Offener Text, Rahmengeometrie, Schrift und Dirty-Zustand bleiben dabei erhalten.
Bei einer geänderten Designmappe übernimmt ein Tab ohne offenen Entwurf den neuen
Stand. Ein Tab mit offenem Entwurf behält ihn unverändert und zeigt einen Konflikt.
Ein veralteter Stand darf nicht gespeichert werden. Erst nach bewusstem Verlassen
(einschliesslich Verwerfen-Bestätigung bei ungespeicherten Änderungen) wird die
aktuelle Mappe übernommen. Es gibt keine automatische Zusammenführung von Entwürfen.

Ein bestätigter Beratungsreset erhält weiterhin eine neue Epoch und zusätzlich
`reset:true`. Dadurch ist er auch dann von der ersten normalen Speicherung zu
unterscheiden, wenn zuvor noch keine Mappe existierte. Andere Tabs setzen die
vorherige Beratung per Reload zurück. Mehrere zugehörige Storage-Ereignisse werden
auf einen Reload zusammengefasst. Andere Tabs prüfen vor dem Reset die bestätigte
Guard-Transaktion; ein zurückgerollter Reset darf auch dort keine ungespeicherte
Arbeit verwerfen. Ungültige fremde Mappen werden nicht übernommen
oder überschrieben; offener Text bleibt bestehen. Das Entfernen der kompletten
Mappe über Browser-Speicherwerkzeuge bleibt eine Datenschutzgrenze.

Alle Mappen-Schreiboperationen einschliesslich Duplizieren, Löschen und Reset
verwenden dieselbe exklusive Web-Lock. Die erwartete Ausgangsversion wird **vor**
dem Warten erfasst. Bereits ausgetauschte Ausgangsstände werden zusätzlich atomar
in einer IndexedDB-Transaktion erkannt: `timberart-map-write-guards`, Store
`usedSnapshots`, enthält ausschliesslich SHA-256-Schlüssel und den Wert `true`.
Keine Wunschtexte, Motiv-IDs, Namen, Originaldateien oder Zugangsdaten werden dort
abgelegt. Die eigentlichen Entwürfe bleiben im bestehenden localStorage-Schlüssel
und im bisherigen Mappenformat. Der Fingerabdruck wird nur bei einer tatsächlichen
Änderung verbraucht; unveränderte Schreibvorgänge erzeugen keine Schreibsperre.

Diese Zusatzsicherung ist durch einen tatsächlichen Befund begründet: In den
Paralleltests konnten beide Writer trotz Web-Lock und localStorage-Vergleich
Erfolg melden. Ein Tab las dabei noch einen alten Browser-Storage-Cache. Die atomare
Transaktion verhindert, dass derselbe Ausgangsstand ein zweites Mal ersetzt wird.
Ein blosses zusätzliches Event-Loop-Warten war im Test nicht ausreichend und ist
nicht die endgültige Lösung.

Bei einem Transaktionsabbruch wird die eigene localStorage-Änderung nach Möglichkeit
zurückgerollt. Erst nach bestätigtem Transaktionsabschluss wird ein Editor geschlossen
oder die Oberfläche für eine neue Beratung geleert. Ein fehlgeschlagener Save bleibt
sichtbar als nicht gespeichert. Weitertippen während eines wartenden Saves bleibt
auch nach erfolgreichem Schreiben des angeklickten Schnappschusses erhalten; der
nächste Save aktualisiert denselben Entwurf und erzeugt kein Duplikat.

## Verspätete Schrift: Verhalten

Der Vier-Sekunden-Timeout beendet die Ladeprüfung nicht mehr. Er zeigt nur den
Zwischenstatus mit Ersatzschrift. Jedes tatsächliche Ladeergebnis aktualisiert den
Status und prüft die verbundenen V3-Vorschauen erneut. Zusätzlich reagieren die
sichtbaren Ansichten auf `document.fonts`-Ereignisse `loadingdone` und `loadingerror`,
etwa bei einem späteren erneuten Ladeversuch. Veraltete Requests und bereits
entfernte Ansichten dürfen keine aktuelle Statusmeldung überschreiben.

Die vorhandene Platzprüfung wird weiterverwendet. Es gibt keine neue Mess- oder
Skalierungslogik. Neu entstehender Überlauf wird sichtbar gemeldet; verschwindender
Überlauf entfernt die Warnung. Text und sämtliche Rahmenwerte bleiben unverändert.

## Dateien

- `personal.js`: Speicherlesen/Validierung, Tab-Ereignisse, geschützte asynchrone
  Schreibvorgänge, Reset-Behandlung und Schriftlade-/Statusbehandlung.
- `tests/tab_sync_browser_check.py`: dauerhafte Regression der tatsächlichen
  Mehrfensterszenarien und konkurrierender Schreibvorgänge.
- `tests/late_font_browser_check.py`: dauerhafte verspätete Schriftprüfungen.
- `tests/browser_check.py`, `tests/transform_check.py`, `tests/selection_check.py`,
  `tests/text_frame_browser_check.py`, `tests/frame_resize_browser_check.py`:
  Die bisherigen Inhaltsassertionen bleiben; nach Schreibaktionen wird jetzt der
  Abschluss der asynchronen Speicheroperation abgewartet.
- `docs/text-model-v3.md` und dieser Bericht: Nachtrag und Verweis auf die Korrektur.

## Testumfang und verbleibende Einschränkungen

Die neuen Browserprüfungen laufen lokal in Chromium bei 1440×1000 mit Maus,
820×1180 und 390×844 mit Touch-Emulation. Alle externen HTTPS-Anfragen sind blockiert.
Fontfixtures stammen aus lokalem DejaVu Sans Mono, nicht von Google. Ein zusätzlicher
Test erfüllt eine CSP-erlaubte Font-URL direkt über Playwright mit lokalen Bytes;
er erzeugt ein echtes FontFaceSet-Ladeereignis, ohne Google zu kontaktieren oder
CSP zu ändern. Physische Geräte, Firefox und WebKit/Safari bleiben ungetestet;
die Browser fehlen und der zuvor versuchte Download war durch HTTP 403 gesperrt.

Erforderlich sind ein aktueller Browser in sicherem Kontext (HTTPS bzw. localhost),
Web Locks, Web Crypto und zugängliche IndexedDB. Fehlen diese Voraussetzungen,
wird kein unsicherer Schreib-Fallback benutzt: Der Entwurf bleibt geöffnet und
Speichern/Reset meldet den Fehler. Bereits geöffnete Tabs einer **älteren** App-Version
müssen nach dem Update neu geladen werden; ihre alten Writer benutzen den neuen
Schutz nicht. Private-Modus-/Quota-/Betriebssystemvarianten sind damit nicht pauschal
als hardwaregetestet bestätigt.

Es gibt keine automatische Konfliktzusammenführung oder automatische Rettung eines
veralteten Entwurfs als neue Variante. Der offene Text bleibt verfügbar; vor einem
bewussten Verwerfen muss benötigter Inhalt gesichert werden. Eine manuelle
Wiederherstellung alter localStorage-Schnappschüsse ohne die zugehörige
Browser-Speicherhistorie kann den Replay-Schutz auslösen. Partielle Löschung nur
eines Speichers ist kein unterstützter Import-/Wiederherstellungsweg. Die
Fingerabdrücke werden lokal aufbewahrt und wachsen mit der Anzahl tatsächlicher
Schreibvorgänge; ein kontrollierter Backup-/Importablauf ist nicht Teil dieser
Korrektur. Browserprozess-/Stromausfall während eines Schreibvorgangs wurde nicht
simuliert; es gibt keine atomare Transaktion über localStorage und IndexedDB zusammen.
Die erzwungenen Transaktions- und Quota-Fehler sind separat zu bewerten.

Die ursprünglichen V1-/V2-Reader, Rahmengeometrie, acht Griffe, Schriftgrössen,
Umbrüche und Ausrichtungen werden nicht umgestellt. Auch Motivbestand,
Drive-Synchronisierung und Bestellschutz bleiben unverändert. Ein Live-Drive-Test,
Actions-Lauf oder Produktions-/Gravurfreigabe gehört nicht zur lokalen Prüfung.

## Tatsächlich ausgeführte Abschlussprüfungen – Ergebnis

Der abschliessende vollständige Lauf des korrigierten lokalen Codes bestand:

| Befehl | Ergebnis |
| --- | --- |
| `node tests/text_frame_check.js` | 12/12 bestanden |
| `python3 -B tests/drive_sync_check.py` | 37/37 bestanden, offline |
| `python3 -B -m unittest discover -s tests -p 'import_check.py'` | 8/8 bestanden, offline |
| `python3 -B tests/drive_connection_check.py` | 6/6 bestanden, offline |
| `python3 -B tests/browser_check.py` | bestanden |
| `python3 -B tests/transform_check.py` | bestanden |
| `python3 -B tests/selection_check.py` | bestanden |
| `python3 -B tests/sync_categories_browser_check.py` | bestanden |
| `python3 -B tests/order_safety_check.py` | bestanden |
| `python3 -B tests/local_images_check.py` | bestanden |
| `python3 -B tests/text_frame_browser_check.py` | bestanden |
| `python3 -B tests/frame_resize_browser_check.py` | bestanden |
| `python3 -B tests/tab_sync_browser_check.py` | neu, bestanden |
| `python3 -B tests/late_font_browser_check.py` | neu, bestanden |
| `python3 -B tools/sync_motifs.py --validate` | 412 IDs, 824 referenzierte WebPs, 177.108.798 Bytes |
| `node --check personal.js`, `node --check transform.js`, `node --check text-frame.js` | bestanden |
| `git diff --check` und Python-AST-Prüfung | bestanden |

Die acht bisherigen Browser-Skripte behalten ihre Inhaltsprüfungen. Fünf davon
warten an Schreibgrenzen nun ausdrücklich auf die asynchrone Speicherung; vorherige
Sofortprüfungen direkt nach einem Klick waren für die neue Sperre nicht geeignet.
Keine Inhaltsassertion wurde entfernt, um einen Produktfehler zu übergehen.

Das neue Mehrfenster-Skript prüft die Hauptabläufe in allen drei Bildschirmgrössen:

- Favorit in Tab B ändern: Tab A bleibt ohne Reload und mit exakt gleichem Entwurf.
- Stand desselben Entwurfs in Tab B speichern: Tab A behält seinen Text und meldet
  den Konflikt; der veraltete Save wird abgewiesen und ändert den Speicher nicht.
- Verwerfen abbrechen erhält den Entwurf; erst ausdrückliches Verwerfen übernimmt
  den fremden Mappenstand, ohne Reload.
- Zwei gegen denselben Stand wartende Saves: ein Erfolg, eine explizite Ablehnung;
  der abgelehnte Entwurf bleibt geöffnet.
- Weitertippen während wartendem Save: der angeklickte Schnappschuss wird gespeichert,
  neuerer Text bleibt ungespeichert im Editor, ein Folgesave erzeugt kein Duplikat.
- Bestätigter Reset setzt andere Tabs zurück. Ein laufender Reset sperrt zusätzliche
  Saves; eine neue Beratung startet nicht parallel zu einem laufenden Schreibvorgang.
- Ungültige fremde JSON-Daten bleiben erhalten, der Editor bleibt geöffnet und
  überschreibt sie nicht.

In zusätzlichen isolierten Desktop-Kontexten desselben Skripts werden V1 und V2,
fehlende Web Locks sowie erzwungene IndexedDB-Transaktionsabbrüche geprüft. Bei den
Abbrüchen bleiben Entwurf, vorhandene Mappe und Favoriten erhalten. Ein anderer
Tab mit ungespeichertem Text wird bei einem fehlgeschlagenen Reset nicht neu geladen.
Diese Unterfälle verwenden Standard-Desktop-Kontexte; sie sind keine zusätzlichen
physischen Smartphone-/Safari-Nachweise.

Der abschliessende isolierte Stressteil provoziert 30 weitere Schreibrennen:
**30-mal genau ein erfolgreicher Writer pro Ausgangsstand**. Ein No-op verbraucht
keinen Fingerabdruck. Die Datenbank enthält danach genau 30 hexadezimale
SHA-256-Schlüssel und ausschliesslich den Wert `true`, keine Entwurfsdaten.

Die neue Schriftregression prüft zwölf Kombinationen: Editor beziehungsweise
Mappe einschliesslich beider Vergleichsvorschauen, jeweils neu auftretender und
verschwindender Überlauf, in allen drei Bildschirmgrössen. Jeder Fall wartet
wirklich länger als vier Sekunden. Nach Schriftauflösung stimmen alle sichtbaren
Platzwarnungen und der Schriftstatus; sämtliche Entwurfswerte und gespeicherten
Rohdaten bleiben exakt gleich. Ein zusätzlicher Test bestätigt ein tatsächliches
FontFaceSet-`loadingdone` nach zunächst fehlender Schrift. Bereits geschlossene
Ansichten werden durch spätere Ereignisse nicht wieder aufgebaut.

Alle finalen Browserprüfungen bestanden ohne aufgezeichnete JavaScript-Pageerrors.
Die Bestellprüfungen bestätigen weiterhin beide Sperren, einschliesslich nativer
Übermittlung ohne App-JavaScript. Alle 824 referenzierten WebPs wurden per HTTP
unter einem Pages-Unterpfad geladen und decodiert. Keine echten Bestellungen.

Bytevergleich/Git-Diff gegen den Ausgangscommit: `text-frame.js`, `text-frame.css`,
`transform.js`, `studio.css`, `index.html`, `.github`, `tools`, `data`, `assets`,
Katalog, Quellenmanifest, Bildlader und `studio.js` unverändert. 412 Motiv-IDs,
neun Kategorien und 30 Schriftdefinitionen bleiben erhalten. Das ursprüngliche
Repository hat einen sauberen Arbeitsbaum und wurde nicht verändert.

Die Testprotokolle liegen ausschliesslich ausserhalb des Git-Repositories unter
`/tmp/timberart-v3-*-final.log`. Während der Umsetzung gefundene Zwischenfehler
(bereits beendete Transaktion nochmals abbrechen, doppelte Reset-Navigation und
Schreibrennen trotz reiner Web-Lock) wurden behoben; der abschliessende Lauf enthält
keine fehlgeschlagenen Prüfungen.

**Ergebnis:** Beide ursprünglichen Befunde sind im getesteten lokalen Stand
nachweislich behoben. Die neue Absicherung verändert weder Textgeometrie noch
Bestellschutz oder Drive-Synchronisierung. Der Remote-PR #9 enthält weiterhin den
vorherigen Commit, bis Commit und Push ausdrücklich freigegeben werden. Keine
Übertragung und keine Veröffentlichung als Teil dieser Korrektur.
