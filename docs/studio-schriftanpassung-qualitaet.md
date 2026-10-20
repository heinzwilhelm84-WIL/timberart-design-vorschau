# TimberArt Studio – automatische Schriftanpassung und Qualitätsprüfung

Datum: 20. Oktober 2026 (Europe/Zurich). Ausschliesslich Vorschau-Repository.
Basis: `main` / `bba18f1b79f5fe40a0c0bd9be3975b166b71505b`.
Entwicklungsbranch: `feature/studio-schriftanpassung-qualitaet`.

## Ausgangslage und Umsetzung

Tatsächlicher Bestand: 416 Motive, zehn Kategorien, 30 Schriftdefinitionen.
832 aktuelle referenzierte WebPs (180.916.338 Bytes, etwa 172,54 MiB).
1.084 WebPs liegen insgesamt vor: ältere Varianten bleiben bewusst erhalten.
Katalog, Kategorien, IDs, Bilder, Logo, CSS-Gestaltung, Sync-Code und sämtliche
Workflows/Berechtigungen/Aktivierungsschalter wurden nicht geändert.

### A – Automatische Schriftanpassung

`textFrame.fontSize` bleibt die gewünschte maximale Schriftgrösse. Breite, Höhe,
Position, Drehung, Innenabstand, Zeilenhöhe und Ausrichtung bleiben unabhängige
v3-Eigenschaften. Eine abgeleitete effektive Schriftgrösse wird nur im DOM
berechnet, nicht als zweiter Skalierungswert gespeichert. Keine Formatmigration.

Der bestehende gemeinsame Renderer misst Text inklusive automatischer Umbrüche
und fester Enter-/Leerzeilen in der tatsächlichen Innenbreite der 600er
Gestaltungsfläche. Passt das Maximum nicht, sucht er begrenzt in 0,1-Einheiten
die passende Grösse bis zum bestehenden Minimum von acht Vorschau-Einheiten.
Bei erneut mehr Platz wird vom Maximum aus neu gerechnet. Am Minimum verbleibender
Überlauf erhält eine deutliche Warnung; ausserhalb der Fläche liegende gedrehte
Rahmen werden weiterhin gemeldet. Der vollständige Eingabetext wird gespeichert.

Berechnung bei Text-/Schrift-/Geometrieänderung, Montage/Grössenänderung und über
die bestehenden Font-Ladeereignisse einschliesslich verspäteter Font-Ergebnisse.
Editor, Designmappe und Vergleich verwenden dieselbe Berechnung. Ein Hinweis
zeigt automatisch reduzierte Schriftgrösse und fordert zur Lesbarkeitsprüfung auf.
Keine Millimeterangaben oder neue Gravur-/Bestellübermittlung.

Die Speicherstruktur bleibt unverändert: v3 speichert das Maximum und die
bestehende Geometrie. v1/v2 bleiben unverändert lesbar und editierbar, ohne
Migration auf v3. Bereits gespeicherte v3-Entwürfe verwenden beim Anzeigen nun
ebenfalls die automatische Anpassung. Bei gleicher Schriftverfügbarkeit ergibt
das Wiederöffnen dieselbe Darstellung. Andere verfügbare Fonts können andere
Metriken ergeben; dann werden Anpassung und Warnung bewusst neu berechnet.

### B/G – Reproduzierte Stabilitätsfehler

- Favoriten bei vollem/nicht verfügbarem Schreibspeicher: vor der Korrektur
  änderte sich die Auswahl trotz fehlgeschlagener Speicherung und ungefangener
  Ausnahme. Der neue Regressionstest reproduzierte dies. Jetzt wird erst nach
  erfolgreichem Schreiben die Auswahl übernommen; sonst bleibt sie erhalten
  und ein verständlicher Hinweis erscheint.
- Strukturell ungültiger Katalog: am unveränderten main mit HTTP 200 und `{}`
  reproduziert: ungefangener Fehler „allDesigns is not iterable“, `studio.ready`
  blieb false. Kataloggrundstruktur und eindeutige IDs werden jetzt vor der
  Übernahme geprüft. HTTP-/JSON-Fehler ergeben eine erklärende Ansicht mit
  erneutem Ladeangebot; Schriftatelier und bestehende Entwürfe bleiben nutzbar.
- Fehlendes Motiv in gespeicherten Entwürfen: bisher nur „Bitte ein Motiv
  auswählen“. Jetzt ausdrücklich als nicht mehr/derzeit im Katalog verfügbar
  beschrieben, mit Erhaltung von Text, Zuordnung und Einstellungen in v1/v2/v3.
  Der Entwurf wird nicht gelöscht. Speichern erfordert weiterhin ein gültiges
  Motiv; ein neues Motiv muss bewusst gewählt werden.

### Aktualisierte Tests

Keine dauerhaft festen Erwartungen von 412/824 Motiven/Bildern oder neun
Kategorien in Browserprüfungen. Erwartungen kommen aus aktuellem Katalog,
Kategorieverzeichnis und separat geschütztem Basisbestand. Leere konfigurierte
Kategorien zählen mit. Fixe Zahlen in synthetischen Unit-Test-Fixtures sind
weiterhin bewusst Fixture-Erwartungen, keine Annahmen zum Produktionskatalog.

An bisherige Überlaufannahmen angepasste Tests prüfen jetzt die neue Semantik:
Maximum unabhängig, effektiv kleiner, gegebenenfalls Minimum-Warnung. Die
bestehenden verspäteten Font-Warnungstests laufen dafür am Minimum; zusätzliche
Fälle prüfen echtes Schrumpfen/Wachsen oberhalb des Minimums nach >4 Sekunden.

Der Bestellsperrentest ohne JavaScript hatte selbst einen Fehler: er versuchte
per `page.evaluate` JavaScript-Funktionen auszuführen und erwartete danach eine
Konsolenmeldung. Jetzt werden beide originalen HTML-Formulare mit unveränderter
Original-CSP in einer isolierten Testseite ohne JavaScript nativ angeklickt.
Jedes Formular verwendet eine eigene Seite: Chromium/Playwright kann eine
blockierte native Navigation als ausstehend melden. Kein Umgehen der CSP,
keine Änderungen an Formularen oder Sicherheitsregeln.

## Tatsächlich ausgeführte Prüfungen

Alle Browserprüfungen nutzen isolierte lokale Profile, einen lokalen Testserver
und blockieren externe HTTPS-Zugriffe. Kein Workflow, kein Drive-Zugriff, keine
Bestellungen, kein Deployment. Chromium Desktop sowie emuliertes Tablet und
Smartphone bei 1440/820/390 Pixeln; Maus und über CDP simulierte Touch-Gesten.
Zusätzliche Querformatprüfung für v3-Auto-Fit und Speicherung.

### Modell- und Python-Tests

| Befehl | Ergebnis |
| --- | --- |
| `node --test tests/text_frame_check.js` | 12 Modelltests bestanden |
| `python -B -m unittest discover -s tests -p drive_sync_check.py` | 37 bestanden |
| `python -B -m unittest discover -s tests -p drive_additions_check.py` | 36 bestanden |
| `python -B -m unittest discover -s tests -p drive_connection_check.py` | 6 bestanden |
| `python -B -m unittest discover -s tests -p drive_diagnosis_check.py` | 14 bestanden |
| `python -B -m unittest discover -s tests -p import_check.py` | 8 bestanden |

101 Python-Tests und zwölf Modelltests bestanden. Die Sync-Prüfungen sind
Simulationen, kein Live-Abgleich. Erwartete Fehlermeldungen in negativen Fällen
sind geprüfte Ablehnungen, keine fehlgeschlagenen Tests.

### Browserprüfungen

Alle 14 Browserprüfskripte bestanden nach den unten erklärten Testkorrekturen.
Befehl jeweils `python -B tests/<Skript>.py`:

| Skript | Tatsächlich geprüfter Schwerpunkt |
| --- | --- |
| `text_fit_browser_check` | Auto-Fit, Maximalgrösse, Mindestwarnung, Textlöschen, alle Schrift-Auswahlen, alle Ausrichtungen, Drehwinkel, Speicher-/Vergleichsgleichheit, Querformat, fehlendes Motiv v1/v2/v3, abgebrochener Reload |
| `text_frame_browser_check` | v3-Modell, feste/automatische Umbrüche, manuelle Felder, Maus/Touch, v1/v2-Lesekompatibilität, defekte Daten |
| `frame_resize_browser_check` | alle vier Eckgriffe × vier Drehwinkel × drei Bildschirmgrössen, feste Gegenanker, Live-Umbruch, Schriftmaximum unabhängig, Drehgriff, Abbruch, Tastatur, Rand-/Minirahmen |
| `late_font_browser_check` | zwölf Warnungsszenarien nach echtem >4s-Timeout in Editor/Mappe/Vergleich, FontFaceSet-Nachladen, vier zusätzliche Schrumpf-/Wachstumsszenarien nach spätem Font |
| `studio_resilience_check` | alle aktuellen Kategorien, dynamische Suche/Filter, Leerzustand, Favoriten bei Quote/Reload, HTTP 503/ungültiges JSON, Navigation während verzögertem HTTP, leere Kategorie |
| `motif_quality_browser_check` | sieben gesonderte Zuordnungs-/Proportionsprüfungen und echte Modal-/Editor-Ladevorgänge bei drei Grössen |
| `local_images_check` | alle 832 Referenzbilder laden/decodieren, Projekt-Unterpfad, Platzhalter bei 404, Mappe/Favoriten/alte IDs erhalten |
| `browser_check` | Speichern, Wiederöffnen, Bearbeiten, Duplizieren, Vergleich, Löschen, Speicherausfall, Reset, fehlerhafte Speicherdaten |
| `tab_sync_browser_check` | echte Mehrtab-Ereignisse, ungespeicherte Eingaben, Konflikte, Queue/Abbruch, v1/v2, fehlende Locks, IDB-Rollback, 30 konkurrierende Schreibrennen |
| `order_safety_check` | beide ausgefüllten Formulare, wiederholtes Absenden, kein Fetch/XHR/Beacon, native Übermittlung mit/ohne JavaScript durch Original-CSP gesperrt |
| `selection_check` | native Maus/Touch-Auswahl/Abwahl, erster Tap auf Felder, Tastatur, keine Werkzeuge in Mappe/Vergleich, Reset |
| `transform_check` | unveränderte ältere v2-Bewegung/Skalierung/Drehung, Abbruch, Grenzen, Speichern, v1 |
| `atelier_browser_check` | bestehende Gestaltung/Original-Logo, dynamische Kategorien, weisse Vorschauen, Touchflächen, kein horizontaler Überlauf |
| `sync_categories_browser_check` | neue/leere/umbenannte Kategorien und neue Motive als lokale Browser-Fixture, stabile Schlüssel, Escaping; kein Live-Sync |

Nicht als 14 einzelne Assertions zu verstehen: jedes Skript umfasst viele
Funktionsfälle. Keine unbeabsichtigten POST-Anfragen oder ungefangenen
JavaScript-Fehler in den bestandenen App-Prüfungen.

Der erste finale Sammeldurchlauf hatte 13/14 erfolgreiche Skripte. Der Griff-Test
scheiterte auf dem Tablet an einer versteckten Griffbox. Eine gezielte
Ereignisaufzeichnung reproduzierte einen Koordinaten-Tap auf die **leere
Gestaltungsfläche** nach Fokus-/Scrollwechsel aus einem Zahlenfeld. Warten allein
half nicht. Der Test verwendet jetzt einen echten Locator-Tap mit der
Stabilitäts-/Trefferprüfung von Playwright, ohne erzwungene Auswahl oder
übersprungene Gesten. Danach bestanden alle drei Bildschirmgrössen. Keine
zusätzliche Änderung der App-Auswahllogik aufgrund dieser Testdiagnose.

Auch der zusätzliche Reload-Test erforderte eine Korrektur des Testaufbaus:
Ein vorsorglicher Accept-Dialoghandler blieb nach dem Verlassen eines sauberen
Editors ungenutzt registriert und bestätigte später den Reload. Er wird jetzt
nur bei tatsächlich ungespeicherten Änderungen installiert. Die finale Prüfung
lehnt den echten `beforeunload`-Dialog ab und prüft Seitenmarker, vollständiges
ungespeichertes Modell und gespeicherten Rohwert auf Unverändertheit bei allen
drei Grössen. Ein nach der Ablehnung ausstehender Playwright-Reload-Waiter wird
von diesem tatsächlichen App-Zustand unterschieden. Der bestehende Browser-
Verlassen-Schutz wurde nicht verändert. Der anfangs beobachtete Testfehlschlag
war kein Grund, eine neue Kundendaten-Sicherung oder Migration einzubauen.

Die anfänglich fehlerhafte JavaScript-freie Formular-Testmechanik wurde wie oben
beschrieben korrigiert und beide nativen Klicks erfolgreich nachgeprüft. Die
anfängliche absichtliche Favoriten-Regression schlug vor der App-Korrektur fehl
und bestand danach. Keine dieser anfänglichen Fehlversuche wird als bestandener
Lauf ausgegeben.

## Motiv- und Bildprüfung

`python -B tools/sync_motifs.py --validate` prüfte alle 416 Datensätze und 832
Referenzdateien erfolgreich: Katalog-/Manifestgleichheit, eindeutige IDs,
Erhaltung aller 412 Basis-IDs, Originalzuordnung, Datei-/Pixel-Hashes, Dateigrösse,
Format, Abmessungen und keine Hochskalierung. Ergebnis: `sourcePixelComparisons: 0`.
Keine Originaldateien liegen als Vergleichsbasis vor; Hash-/Formatprüfungen sind
kein Nachweis der visuellen Qualität gegenüber den Drive-Originalen.

Zusätzlich alle 1.084 vorhandenen WebPs rein lesend geprüft: Datei-Hash im
Dateinamen, verlustfreier WebP-Container ohne zusätzliche Metadaten, vollständiges
Pillow-Decoding und jeweilige maximale Kantenlänge; keine fehlerhafte Datei.
Alle 832 aktuell referenzierten Bilder wurden im Chromium unter einem Pages-
ähnlichen Unterpfad per HTTP/MIME und tatsächlichem Bild-Decoding geladen.

Die sieben geforderten Motive wurden gesondert in grosser Vorschau und Editor
bei allen drei Bildschirmgrössen geladen, auf Motiv-ID und `object-fit: contain`
geprüft. Die 600er/1600er-Masse entsprechen einer proportionalen Verkleinerung
der im Manifest gespeicherten Quelldimensionen:

| Motiv | Kategorie | 600er | 1600er |
| --- | --- | --- | --- |
| 03_Jagd_Revier_Beispiel | CAP-Design | 600 × 293 | 1600 × 780 |
| 04_Jagd_Revier_Leer | CAP-Design | 600 × 293 | 1600 × 780 |
| 09_Metallbau_Beispiel | CAP-Design | 600 × 340 | 1600 × 906 |
| 10_Metallbau_Leer | CAP-Design | 600 × 340 | 1600 × 907 |
| 05_Werkstatt_Beispiel | CAP-Design | 600 × 300 | 1600 × 800 |
| 06_Werkstatt_Leer | CAP-Design | 600 × 300 | 1600 × 800 |
| Bergkette-Churfürsten | Bergmotive | 600 × 200 | 1600 × 533 |

Abweichungen um einen Pixel entstehen aus proportionaler Rundung. Die sechs
CAP-Zuordnungen wurden ausserdem mit dem separaten Basisbestand verglichen.
Kein Hinweis auf neue CSS-Beschneidung. Kein Vergleich feiner Linien/Schraffuren
mit hochauflösenden Drive-Originalen: hierfür bleibt ein manueller Vergleich nötig.

## Grenzen und noch erforderliche Praxisprüfungen

- Echtes iPad/iPhone-Safari, Android-Gerät und Windows-Edge nicht vorhanden.
  Touch ist Chromium-Emulation, kein Hardwaretest. Firefox-/WebKit-Binaries sind
  nicht installiert; keine zusätzliche Installation oder neue Abhängigkeit.
- Alle 30 Schrift-Auswahlen und wiederholte Wechsel wurden bedient. Tests mit
  blockierten externen Fonts prüfen Ersatzschriften und Fehlermeldungen. Lokale
  FontFace-Fixtures prüfen reale Metrikänderungen und verspätetes Laden, aber
  nicht Verfügbarkeit und Aussehen sämtlicher 30 Google-Fontdateien im Internet.
- Automatisches Einpassen garantiert keine lesbare Gravur bei sehr kleinen
  Rahmen. Mindestgrösse acht bezieht sich auf die 600er Vorschau, nicht auf
  Fertigungseinheiten. Produktionsfreigabe bleibt ein eigener Schritt.
- Erneutes Öffnen setzt gleiche Schriftverfügbarkeit voraus. Es wird bewusst
  kein von einer vorübergehenden Ersatzschrift abhängiger Effektivwert gespeichert.
- Es gibt weiterhin keine automatische Sicherung ungespeicherter Eingaben.
  Vorhandener Browser-Verlassen-Hinweis ist kein Schutz bei Prozessabbruch,
  Stromverlust oder mobilem Tab-Abwurf. Entwürfe ausdrücklich speichern.
- Bestehendes Speichern benötigt Secure Context/HTTPS, Web Locks, IndexedDB,
  Web Crypto und nutzbaren lokalen Speicher. Fehlende Sperren, Speicherfehler,
  Konflikte und defekte Daten werden in den bestehenden Tests abgefangen;
  keine unsichere Ausweichspeicherung oder stilles Überschreiben ergänzt.
- Reload bei Speicherdaten bleibt lokal auf diesem Browser/Origin. Keine
  geräteübergreifende Sicherung und keine Migration von Kundendaten.

Empfohlener Praxistest: auf echtem Smartphone/Tablet mit verfügbaren Originalfonts
einen mehrzeiligen Entwurf mit Leerzeile gestalten, alle vier Ecken ziehen,
drehen, Maximum ändern, speichern, Browser neu laden und wieder öffnen.
Anschliessend zwei Varianten vergleichen und Bestellsperre sichtbar kontrollieren.
Die sieben detailreichen Motive zusätzlich mit privaten Originalen vergleichen.

## Geänderte Dateien

- `text-frame.js`: gemeinsames Auto-Fit und Hinweise, bestehendes v3-Modell.
- `personal.js`, `transform.js`: verständlicher Hinweis für fehlendes Motiv in
  allen gespeicherten Layoutversionen.
- `index.html`, `studio.js`: geprüfter Katalog-Ladepfad, Fehlermeldung und
  transaktionale Favoritenanzeige nach erfolgreicher Speicherung.
- `tests/atelier_browser_check.py`, `tests/browser_check.py`,
  `tests/local_images_check.py`: dynamische aktuelle Katalog-/Kategorieprüfung.
- `tests/text_frame_browser_check.py`, `tests/frame_resize_browser_check.py`,
  `tests/late_font_browser_check.py`: neue Auto-Fit-Semantik und späte Fonts.
- `tests/order_safety_check.py`: echte native Formularklicks ohne JavaScript.
- `tests/text_fit_browser_check.py`, `tests/studio_resilience_check.py`,
  `tests/motif_quality_browser_check.py`: dauerhafte gezielte Regressionen.
- Diese Dokumentation.

## Screenshots und Abschlussprüfung

Screenshots liegen ausserhalb des Git-Repositorys unter
`/workspace/artifacts/timberart-studio-qa/`: Startseite und bestehender Editor
bei drei Grössen, Auto-Fit-Editor/Auto-Fit-Vergleich sowie alle sieben Motive bei
drei Grössen (39 PNG-Dateien insgesamt). Zusätzliches ZIP ausserhalb des Repositorys:
`/workspace/artifacts/timberart-studio-qa.zip`. Startseite auf Smartphone und Auto-Fit-Vorschau auf Desktop und
Smartphone wurden zusätzlich visuell angesehen. Das ersetzt keinen visuellen
Vergleich mit privaten hochauflösenden Originalen und keine echte Touch-Hardware.

`git diff --check`, JavaScript-Syntaxprüfungen sowie Begrenzung auf 16 beabsichtigte
Frontend-/Test-/Dokumentationsdateien erfolgreich. Keine Treffer der vorhandenen
Secret-Musterprüfung in den Änderungen. Original-CSP, beide Formulare und
Bestellhandler wurden zusätzlich bytegleich mit main verglichen. Katalog,
Kategorien, Motivassets, Logo, Sync und Workflows haben keine Änderungen.

Keine bisher bekannte offene App-Regression aus den ausgeführten Prüfungen.
Offen bleiben die oben benannten Umgebungs-/Originalvergleichsgrenzen.
Ausgefallen/übersprungen: zusätzliche Browserengines und echte Geräte mangels
verfügbarer Umgebungen; Live-Drive-/Actions-/Veröffentlichungsprüfungen wegen der
vorgegebenen Änderungsgrenzen; Originalbildvergleich mangels lokaler Originale.
Kein Merge und kein Deployment. Genau ein Draft-PR ist die Übergabe.
