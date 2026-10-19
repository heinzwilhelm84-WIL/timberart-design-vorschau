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
