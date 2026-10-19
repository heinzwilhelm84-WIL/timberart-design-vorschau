# TimberArt Design – Testversion

Separate Vorschau aus `heinzwilhelm84-WIL/timberart-design`, Branch
`design/phase-1-geschenkstudio`, Quellcommit `5ad3ec35dea1b5576ce2b7a4f74c4d2e1077d491`.

- Deutliche Kennzeichnung als Testversion; keine echten Bestellungen.
- Beide Formulare testen ausschliesslich lokal. Kein Formspree-Endpunkt oder Bestellversand.
- Content Security Policy blockiert Formularübermittlungen und externe JavaScript-Netzwerkanfragen.
- Google-API-Schlüssel und Formspree-Konfiguration wurden entfernt.
- `catalog.json` enthält eine Momentaufnahme von 412 Motiven in 9 Kategorien.
  Bilder werden weiterhin von Google Drive geladen; Schriften von Google Fonts.
- Keine ursprüngliche Git-Historie übernommen. Das Quellrepository bleibt unverändert.
- GitHub Pages wird nicht aktiviert; keine Deployment-Workflows enthalten.

Lokal ansehen: `python3 -m http.server 8000`, dann http://localhost:8000 öffnen.

## Personalisierung und Designmappe

Auf Branch `feature/personalisierung-designmappe`: Motiv öffnen und
„Personalisieren“ wählen, oder im Schriftatelier „Mit Motiv kombinieren“.
Wunschtext und eine der 30 Schriften kombinieren, lokal speichern, bearbeiten,
duplizieren, löschen und zwei Entwürfe vergleichen. Lange Texte werden nicht
abgeschnitten oder pauschal begrenzt; Hinweise unterstützen bei der Lesbarkeit.

Die Designmappe nutzt den Browserspeicher (`timberart-designmappe-v1`), ohne
Backend, Konto oder zusätzliche Dienste. Sie gilt nur für dieses Browserprofil
und ist kein dauerhaftes Archiv. „Neue Beratung“ löscht nach Bestätigung alle
Entwürfe, Favoriten, Auswahl und Formulare. Andere Browserdaten bleiben erhalten.
Andere offene App-Tabs laden bei Änderungen neu, damit alte Kundenauswahlen
nicht versehentlich weiterbenutzt werden. Gleichzeitiges Bearbeiten in mehreren
Tabs wird nicht unterstützt. Speicherfehler werden gemeldet; ungespeicherte
Änderungen werden beim Verlassen geschützt.

Die Komposition zeigt Motiv über Text und ist keine Produktions-/Gravurdatei.
Bilder und Schriften benötigen weiterhin Internet. Fehlende Motivbilder und
Schriften werden kenntlich gemacht. Testbestellungen bleiben gesperrt.

### Browserprüfung

Mit Python und dem kostenlosen Paket `playwright` sowie Chromium:
`python3 -B tests/browser_check.py`.
Bei Bedarf `CHROMIUM_PATH` auf den Chromium-Pfad setzen. Optionale Screenshots:
`TIMBERART_TEST_SCREENSHOTS=/tmp/timberart-check python3 -B tests/browser_check.py`.
Die Tests blockieren externe Bild-/Schriftanfragen bewusst und prüfen dabei auch
die Hinweise bei fehlenden Ressourcen. Desktop (1440 px), Tablet (820 px) und
Smartphone (390 px) werden als Browser-Viewports geprüft, nicht auf physischen
Geräten. Es werden keine Testbestellungen übermittelt.
