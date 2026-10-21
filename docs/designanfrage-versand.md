# Unverbindliche Designanfrage an TimberArt

Stand: 21. Oktober 2026 (Europe/Zurich). Basis: main nach PR #17,
`2b18de1d0930473a3f63a082f93ce72c7cb1a40b`.
Branch: `feature/designanfrage-versand`. Ausschliesslich Vorschau-Repository.

## Funktionsumfang

„Design an TimberArt senden“ öffnet einen separaten Anfrage-Dialog:

- bei einem unveränderten Motiv in der grossen Motivvorschau;
- beim aktuellen personalisierten Entwurf im Editor, auch vor dem Speichern;
- bei einem gespeicherten Entwurf direkt in der Designmappe.

Die Anfrage ist keine Bestellung, kein Vertrag und keine Zahlung. Die beiden
bisherigen Testbestellformulare bleiben unverändert lokal gesperrt. Der Banner
unterscheidet jetzt ausdrücklich die neue Anfrage von diesen Testformularen.

Pflichtfeld Name, E-Mail/Telefon/Bemerkungen freiwillig. Rückmeldung erfordert
freiwillige Kontaktangabe. Vor dem Senden werden ein unveränderlicher Stand und
seine Vorschau erfasst. Versand schreibt keine Entwürfe/Favoriten, verändert
keine Geometrie und löscht keine gespeicherten Daten. Kontaktangaben stehen nur
im offenen Formular/Übermittlungsvorgang, nicht in localStorage/IndexedDB,
Designmappe oder lokalen Gestaltungsdateien. Nach bestätigtem Erfolg oder
Schliessen wird das Kontaktformular geleert. Browser-eigenes Autofill ist davon
unabhängig und wird von diesem Code nicht gespeichert oder verwaltet.

## Technische Referenz und Dateiversand

Die beiden früheren Submit-Funktionen im ursprünglichen Repository wurden nur
lesend untersucht. Sie verwenden Formspree-POSTs mit `application/json` und
flachen Textfeldern. Es gibt darin keinen Dateianhang, Multipart-Versand und
keinen Beleg für freigeschaltete Upload-Funktionen im konkreten Formspree-Konto.
Der frühere Motivsender benutzte einen Thumbnail-Link; dieser wird bewusst nicht
als Original übernommen. Alte Google-Konfiguration oder Schlüssel wurden nicht
kopiert.

Ein Kontotarif, verlässliche MIME-/Grössenfreigaben oder die tatsächliche Annahme
von Anhängen sind aus den vorhandenen Projektdateien nicht feststellbar.
Es wurden weder authentifizierte Kontoabfragen noch Probe-Uploads oder sonstige
Anfragen an den echten Formspree-Endpunkt durchgeführt. Deshalb ist ein
zuverlässiger automatischer Dateiversand **nicht nachgewiesen** und nicht eingebaut.
Keine Behauptung, dass das Konto Anhänge unterstützt oder grundsätzlich ablehnt.

Umgesetzt ist der ausdrücklich erlaubte Fallback: JSON-POST an
`https://formspree.io/f/xzebgwlg` mit vollständigen Gestaltungsdaten und dem
vorhandenen Originalverweis. PNG/SVG/JSON werden separat lokal zum Download
angeboten, nicht als Base64-Textanhänge durch Formspree geschleust. Die E-Mail
enthält daher kein automatisch angehängtes Vorschaubild. Die Vorschau sieht der
Kunde im Dialog; heruntergeladene Dateien können später bei Bedarf persönlich
weitergegeben werden. Keine neue Serverinfrastruktur, Bibliothek oder bezahlter
Dienst.

## Übermittelte Daten und Originalzuordnung

Alle Anfragen enthalten Name, optionale Kontaktangaben/Bemerkungen, feste
Kennzeichnung als unverbindliche Designanfrage, Anfrage-UUID, Motivname,
Motiv-ID, Kategorie, Originaldateiname und die vorhandenen Quelleninformationen.
Der vollständige Rekonstruktionsstand steht zusätzlich als lesbar formatiertes
JSON im Feld `design_data`. Wiederholungs-UUIDs sind keine Zugangsdaten.

Personalisierte Anfragen enthalten zusätzlich unveränderten vollständigen Text
mit Enter-/Leerzeilen, Schriftname/-ID/-Familie, Layoutversion und alle bereits
vorhandenen Draft-Eigenschaften. V3: maximale Schriftgrösse, x/y, Breite/Höhe,
Ausrichtung, Rotation, Innenabstand, Zeilenhöhe. V2: ursprünglicher Transform mit
normalisierten Positionen, Skalierung und Rotation; V1: ursprüngliches Layout.
Keine fiktiven v3-Felder für alte Layouts. Abgeleitete Renderdaten enthalten
effektive Schriftgrösse, aktuelle Font-Verfügbarkeit, tatsächliche Zeilenläufe,
Objektgeometrie, Vorschauabmessungen und Warnungen. Ursprüngliche gespeicherte
Layouts und Zeitstempel werden nicht migriert oder überschrieben.

Quellen stammen ausschliesslich aus dem vorhandenen lokalen Manifest. Nur
Google-Drive-Quelldaten mit passender Datei-ID werden übernommen. Als Original
wird nur der exakt passende gespeicherte `drive.google.com/file/d/.../view`-Link
akzeptiert; keine Thumbnails, fremden Hosts, erfundenen Namen oder neu erzeugten
Freigaben. Der Zugang ist ausdrücklich **nicht geprüft**: Anmeldung/Berechtigung
kann erforderlich sein. Fehlendes Manifest/Original wird als fehlend markiert,
nicht durch einen Thumbnail ersetzt. Es gibt keine Drive-Anfragen des Senders.
Quellfelder sind per Allowlist begrenzt; etwaige Credential-Felder werden nicht
übernommen. Lokale Vorschauvarianten sind separat als solche aufgeführt.

## Lokale Exporte und ihre Grenzen

- PNG: bei v2/v3 1200 × 1200 Pixel auf weissem Grund; Bildschirmvorschau, kein
  Fertigungsmass. Verwendet das lokale Vorschaumotiv und die aktuell verfügbaren
  Browser-Schriften. Bei älterem responsive aufgebautem v1 richtet sich die
  Zeichenfläche nach dem erfassten sichtbaren Layout.
- SVG: Rastermotiv als PNG eingebettet, echte SVG-Textzeilen aus dem gemessenen
  Browser-Umbruch. Position/Rotation/v2-Skalierung und v3-Textclip werden übernommen.
  Keine Drive-Bildreferenz erforderlich, kein extern nachzuladendes Motiv.
  Texte und XML-Metadaten sind escaped; unzulässige XML-Steuerzeichen werden im
  SVG ersetzt. Das JSON erhält den vollständigen unveränderten Eingabetext.
- JSON: vollständige Rekonstruktionsdaten ohne zusätzliche Kontaktformularfelder.

SVG-Schriften sind **nicht eingebettet und nicht in Pfade umgewandelt**. Ohne
dieselben installierten/verfügbaren Fonts kann ein SVG-Programm andere Glyphen,
Abstände oder Ersatzschriften verwenden. SVG2- und eingebettete PNG-Unterstützung
ist beim Zielprogramm erforderlich; reine Vektor-Gravurprogramme können das
Rastermotiv nicht als Vektor verarbeiten. PNG erhält die gezeichnete Ansicht,
bietet aber ebenfalls keine editierbaren Vektor- oder Laserdaten.

Keine Produktionsreife: keine physischen Einheiten, Material-/Laserparameter,
Schriftkonturen oder Gravurfreigabe. Originale bleiben auf Drive unverändert.
Fehlt eine Vorschau, wird ein sichtbarer Platzhalter/Warnhinweis exportiert;
Gestaltungsdaten können trotzdem als Anfrage gesendet werden. Textüberlauf und
Rahmen ausserhalb der Fläche bleiben Warnungen, nicht verschwiegene Kürzungen.
Bei blockiertem Canvas/fehlgeschlagener Vorbereitung wird nichts gesendet und
eine Fehlermeldung gezeigt. Sehr grosse Texte werden nicht still gekürzt; reale
Formspree-Limits können eine Ablehnung verursachen (z. B. HTTP 413).

## Versandzustände und Datenschutz

Versand ausschliesslich nach bewusstem Submit und erfolgreicher Validierung.
Während Hashing/Übermittlung sind Submit und Eingaben gegen Doppelklicks gesperrt.
Escape darf keinen Hintergrunddialog schliessen und beendet keinen laufenden
Versand. Es gibt einen Browser-Verlassen-Hinweis während des Sendens.

HTTP-Erfolg **plus** JSON `ok: true` bestätigt die Annahme durch Formspree. Erst
dann erscheint Erfolg; Gmail-Zustellung wird nicht behauptet. Definierte
4xx-Ablehnungen lassen Korrektur/erneuten bewussten Versuch zu. Fehlertexte aus
dem Dienst werden nicht ungeprüft in HTML ausgegeben. Netzwerkfehler, Timeout
(30 Sekunden), 5xx oder eine unklare 2xx-Antwort gelten als unbestätigt: Es könnte
bereits angekommen sein. Kein automatischer Retry. Ein gesondert beschrifteter
manueller Retry macht das Doppelrisiko sichtbar und verwendet dieselbe UUID.

Bestätigte und unklare Anfragen werden nur als opaque Payload-Hashes/UUIDs im
Seitenspeicher gemerkt. Identische Anfragen werden nach Bestätigung nicht erneut
gesendet; ein unklarer Stand wird auch nach Schliessen/erneutem Öffnen im selben
Dokument erneut zurückgehalten. Keine dauerhafte Kontakt-/Payload-Speicherung.
Kein serverseitiges Idempotenzversprechen: Reload, andere Tabs/Geräte oder
veränderte Eingaben können erneut senden. Ohne Serverunterstützung kann die App
keine globale Genau-einmal-Zustellung garantieren. Bei Unsicherheit zuerst bei
TimberArt nachfragen, nicht blind erneut senden.

Fetch verwendet `credentials: omit`, `redirect: error`, `referrerPolicy:
no-referrer` und JSON/Accept-Header. Keine Zugangsdaten im Code. Die Formspree-
Formularadresse ist eine öffentliche Empfangsadresse, kein privater API-Schlüssel.
Die CSP ergänzt nur diesen konkreten HTTPS-Pfad in `connect-src`. `form-action
'none'`, Script-/Font-/Bild-/Object-Regeln und die bisherigen Bestellsperren
bleiben erhalten. Andere Formspree-Pfade und externe API-Hosts bleiben gesperrt.
Native Dialog-Unterstützung wird vor der Nutzung geprüft; bei Nichtverfügbarkeit
wird nichts gesendet und ein aktueller Browser empfohlen.

## Tatsächlich ausgeführte Tests

Keine realen Formspree-, Gmail- oder Drive-Anfragen. Versandtests intercepten den
exakten Endpunkt; sonstige externe HTTPS-Zugriffe werden abgebrochen. Die
bestehenden Offline-Sync-Prüfungen bleiben Simulationen.

| Prüfung | Ergebnis |
| --- | --- |
| `node --test tests/text_frame_check.js tests/design_inquiry_check.js` | 23 bestanden (12 bestehende Modelle + 11 neue Provenienz-/Payload-/XML-Tests) |
| `python -B -m unittest discover -s tests -p 'drive*check.py'` | 93 bestanden |
| `python -B -m unittest discover -s tests -p import_check.py` | 8 bestanden |
| `python -B tests/design_inquiry_browser_check.py` | Desktop 1440, Tablet 820, Smartphone 390 bestanden |
| `python -B tests/design_inquiry_edge_check.py` | v1/v2/v3, fehlendes Manifest/Thumbnail/Bild/Motiv, Timeout, CSP, fehlende Dialog-API bestanden |
| `python -B tests/design_export_visual_check.py` | Zwei PNG-/Editor-Pixelvergleiche bestanden; Ersatzschrift und lokal geladene FontFace-Fixture |

Neue Browserprüfung: Name erforderlich/Whitespace, freiwillige/ungültige E-Mail,
Sonderzeichen und lange Mehrzeilentexte, vollständige Rahmen-/Fontdaten, reale
SVG/PNG/JSON-Downloads, XML-Parsing, PNG-Decoding, unveränderte Designmappe und
ungespeicherter Editor, Name/E-Mail/Bemerkungen nicht in Gestaltungsdateien,
mehrfaches Absenden, Schliessen bei laufender Anfrage, Dubletten nach erneutem
Öffnen, 422/429/500, Netzwerkfehler, fehlende Bestätigung und bewusster Retry.
Ein Timeout wurde mit Playwright-Uhr simuliert: genau ein abgefangener Versuch,
auch nach weiterer virtueller Zeit kein automatischer Retry.

Im Pixelvergleich wurde die tatsächliche 600er Editor-Zeichenfläche bei DPR 2
mit dem erzeugten PNG verglichen. Nur der Textbereich unterhalb des Motivbildes
wurde quantitativ verglichen, um unterschiedliche Rasterbild-Resamplingstufen
nicht mit Textfehlern zu verwechseln. Mittlerer absoluter RGB-Fehler: 0,5982/255
bei Ersatzschrift und 0,5512/255 bei lokaler Font-Fixture, jeweils unter 5/255.
Kein Nachweis bitgleicher Darstellung aller Fonts, aller SVG-Programme oder
Gravurqualität. Die ursprünglichen Capture-Versuche enthielten umgebendes
Sticky-/Scroll-UI bzw. den 12px-Dekorrahmen; nach expliziter Angleichung des
Zeichenflächen-Ursprungs bestand der unveränderte Export die Prüfung.

Zusätzlich alle 14 bestehenden Browserprüfskripte ausgeführt:
`browser_check`, `atelier_browser_check`, `text_frame_browser_check`,
`frame_resize_browser_check`, `late_font_browser_check`, `tab_sync_browser_check`,
`order_safety_check`, `local_images_check`, `selection_check`, `transform_check`,
`sync_categories_browser_check`, `studio_resilience_check`,
`text_fit_browser_check`, `motif_quality_browser_check`.
Alle bestanden nach gezielter Nachprüfung von `text_frame_browser_check`: Der
alte Rohkoordinaten-Tap wartete nach Feld-/Scrollwechsel nicht auf einen stabilen
Treffer; er verwendet jetzt native Locator-Taps mit Sichtbarkeitsprüfung.
Keine App-Gestenlogik dafür verändert. Erster Sammellauf: 13/14 erfolgreich;
gezielte Nachprüfung des korrigierten Skripts bei allen drei Grössen erfolgreich.
Die neuen Tests reproduzierten ausserdem einen Escape-Fokusfall, bei dem der
alte Hintergrunddialog geschlossen wurde; der neue Dialog schirmt Escape jetzt
auch bei deaktivierter Submit-Schaltfläche ab.

Damit 101 Python-Tests, 23 Node-Tests und 17 Browserprüfskripte im geprüften
Bestand erfolgreich. Keine ungefangenen App-JavaScript-Fehler oder unerwarteten
POSTs in den bestandenen Prüfungen. HTTP-MIME/Decoding aller 832 aktuellen
lokalen Vorschaureferenzen weiterhin erfolgreich. Motivdaten und gespeicherte
Designformate sind unverändert. Keine neuen Abhängigkeiten.

## Offene Voraussetzungen und kontrollierter Live-Test

Noch offen: Annahme des echten Kontos, CORS-/Domainfreigabe, Spam-/CAPTCHA-Regeln,
aktuelle Quoten und Gmail-Zustellung. Keine dieser Kontoeigenschaften ist durch
Simulation bewiesen. Dateiannahme bleibt ungeprüft und deaktiviert. Echte
Mobilgeräte/Safari/Firefox/WebKit sowie SVG-Import in die tatsächliche
Gravursoftware wurden hier nicht geprüft. Schriften aus dem Internet und private
Drive-Zugriffsrechte wurden nicht live getestet.

Nach separater Freigabe für einen Live-Test und eine geeignete Testumgebung:

1. Auf einer für dieses Formspree-Formular zulässigen Origin öffnen; diese
   Freigabe weder erraten noch CORS/Sicherheitsregeln umgehen.
2. Mit eindeutig als Test gekennzeichneten Angaben bewusst genau die freigegebene
   Anfrageart senden; keine echten Kundendaten nötig. UUID/Bestätigung notieren.
3. Annahme im Formspree-Konto und Nachricht im Gmail-Postfach manuell prüfen.
   Vollständigen Wunschtext/JSON, Dateiversion und Originalverweis kontrollieren.
4. Erst nach weiterer Freigabe zweite Variante testen. Keine Anhänge, kein
   automatischer Retry und keine Änderung von Drive-Freigaben.
5. PNG und SVG lokal mit der Editoransicht und dem vorgesehenen SVG-Programm
   prüfen; bei SVG dieselbe Schrift installieren oder später nach separater
   Prüfung in Konturen überführen. Noch keine Gravurfreigabe ableiten.

Dieser Branch enthält weder Merge noch Deployment, Workflow-Start, Änderung
von Sync/Workflows/Variablen/Branchschutz oder Änderungen am Originalrepository.
