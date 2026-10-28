# Nachrichtenlage

Sammelt Meldungen aus 20 Nachrichtenquellen, gruppiert sie nach Bedeutung zu Themen – auch
über Sprachgrenzen hinweg – und zeigt, welche Medien worüber berichten und wie sie es tun.

Alles läuft kostenlos bei GitHub: Alle 20 Minuten holt ein automatischer Job die Feeds,
bildet die Themen, lässt Claude die Perspektiven der größten Themen vergleichen und
veröffentlicht das Ergebnis als Webseite. Kein eigener Server nötig.

## Einrichtung (einmalig, ca. 10 Minuten)

Am bequemsten am Computer, geht aber auch im Browser auf dem iPhone.

1. **Repository anlegen:** Auf github.com oben rechts „+“ → „New repository“.
   Name z. B. `nachrichtenlage`, Sichtbarkeit **Public** (GitHub Pages ist kostenlos nur
   für öffentliche Repositories), dann „Create repository“.

2. **Dateien hochladen:** Auf der Repository-Seite „uploading an existing file“ wählen und
   alle Dateien und den Ordner `site` hochladen, dann „Commit changes“.
   Der Ordner `.github` ist versteckt und wird beim Hochladen oft übersprungen. Deshalb:
   „Add file“ → „Create new file“, als Namen `.github/workflows/update.yml` eintippen
   (die Schrägstriche legen die Ordner an), den Inhalt der Datei `update.yml` hineinkopieren
   und „Commit changes“.

3. **Pages einschalten:** „Settings“ → „Pages“ → bei „Source“ **GitHub Actions** wählen.

4. **Claude-Schlüssel hinterlegen** (für den Perspektivvergleich):
   „Settings“ → „Secrets and variables“ → „Actions“ → „New repository secret“.
   Name `HENDRIK_API_KEY`, Wert dein Schlüssel von console.anthropic.com.
   Der Schlüssel bleibt geheim, auch im öffentlichen Repository.

5. **Ersten Lauf starten:** Tab „Actions“ → „Nachrichten aktualisieren“ → „Run workflow“.
   Der erste Lauf dauert ein paar Minuten (das Sprachmodell wird einmalig geladen).

6. **App aufs iPhone:** `https://<dein-github-name>.github.io/nachrichtenlage/` in Safari
   öffnen → Teilen → „Zum Home-Bildschirm“.

## Gut zu wissen

- **Sichtbarkeit:** Die Seite ist für jeden mit dem Link erreichbar, aber für Suchmaschinen
  gesperrt. Sie zeigt nur Überschriften, kurze Teaser und Links zu den Verlagen.
- **Kosten:** GitHub ist für öffentliche Repositories kostenlos. Claude wird nur gefragt,
  wenn ein Thema mindestens drei Quellen hat und neue Quellen dazukommen, höchstens
  8-mal pro Lauf (`NL_MAX_COMPARE` in `build.py`). Ohne Schlüssel läuft alles außer dem Vergleich.
- **Pausen:** GitHub startet geplante Läufe manchmal mit Verzögerung. Bei längerer
  Inaktivität im Repository kann GitHub den Zeitplan pausieren und schickt dann eine Mail;
  im Tab „Actions“ lässt er sich mit einem Klick wieder aktivieren.
- **Status:** Der Tab „Quellen“ in der App zeigt, welche Feeds funktionieren, ob der
  Abgleich nach Bedeutung aktiv ist und wann der letzte Lauf war.

## Anpassen

- **Quellen:** `feeds.py` bearbeiten (geht direkt auf github.com über den Stift).
- **Takt:** `cron` in `.github/workflows/update.yml`.
- **Themen strenger/lockerer:** `NL_MEANING_THRESHOLD` (Standard 0.62) als Variable im
  Workflow setzen. Werden verschiedene Ereignisse zusammengeworfen → 0.68; zerfallen
  Themen in zu viele Teile → 0.55.

## Dateien

| Datei | Zweck |
|---|---|
| `build.py` | Ein Durchlauf: holen, gruppieren, vergleichen, Seite schreiben |
| `feeds.py` | Quellenliste |
| `fetch.py` | Feeds lesen (RSS/RDF/Atom) |
| `embed.py` | Mehrsprachiges Sprachmodell für den Abgleich nach Bedeutung |
| `cluster.py` | Themen-Gruppierung (Rückfall: Wortabgleich) |
| `compare.py` | Perspektivvergleich mit Claude |
| `site/` | Die Webseite fürs iPhone |
| `.github/workflows/update.yml` | Der automatische Job |

Lokal testen: `pip install -r requirements.txt && python build.py`, dann `_site/` mit
`python -m http.server -d _site` ansehen.
