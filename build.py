"""Ein Durchlauf: Feeds holen → Themen bilden → Vergleiche erstellen → Webseite schreiben.
Läuft automatisch im GitHub-Job (.github/workflows/update.yml), lokal mit: python build.py"""
import json
import os
import shutil
import time
from datetime import datetime, timedelta, timezone

import compare
import embed
from cluster import cluster
from feeds import FEEDS, WINDOW_HOURS
from fetch import fetch, parse_feed

DATA = "data"
OUT = "_site"
KEEP_HOURS = 72          # so lange werden Meldungen zwischen den Läufen aufbewahrt
MAX_COMPARE = int(os.environ.get("NL_MAX_COMPARE", 8))   # Claude-Vergleiche pro Lauf (Kosten!)
MIN_SOURCES_COMPARE = 3  # erst ab so vielen Quellen lohnt ein Vergleich
TEST_FEEDS = os.environ.get("NL_TEST_FEEDS")  # Ordner mit <Quelle>.xml statt Internet (zum Testen)

now = datetime.now(timezone.utc)


def load(name, default):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(folder, name, obj):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def hours_ago(iso):
    return (now - datetime.fromisoformat(iso)).total_seconds() / 3600


# 1) Feeds holen und mit dem Bestand zusammenführen
articles = load("articles.json", {})
status = {}
for name, _short, _typ, _lang, url in FEEDS:
    try:
        if TEST_FEEDS:
            path = os.path.join(TEST_FEEDS, f"{name}.xml")
            if not os.path.exists(path):
                raise RuntimeError("keine Testdaten")
            raw = open(path, "rb").read()
        else:
            raw = fetch(url)
        items = parse_feed(name, raw)
        new = 0
        for it in items:
            if it["id"] not in articles:
                articles[it["id"]] = it
                new += 1
        status[name] = {"ok": True, "count": len(items), "neu": new, "error": ""}
    except Exception as exc:  # ein kaputter Feed soll die anderen nicht stoppen
        status[name] = {"ok": False, "count": 0, "neu": 0, "error": str(exc)[:200]}
    if not TEST_FEEDS:
        time.sleep(0.5)

articles = {k: a for k, a in articles.items() if hours_ago(a["published"]) <= KEEP_HOURS}
save(DATA, "articles.json", articles)
recent = [a for a in articles.values() if hours_ago(a["published"]) <= WINDOW_HOURS]
print(f"{len(recent)} Meldungen im Zeitfenster, {sum(s['ok'] for s in status.values())}/{len(FEEDS)} Feeds ok")

# 2) Themen bilden (nach Bedeutung, sonst Wortabgleich)
try:
    vecs = embed.vectors(recent)
except Exception as exc:
    print("Bedeutungs-Abgleich fehlgeschlagen, nutze Wortabgleich:", exc)
    vecs = None
topics = [t for t in cluster(recent, vecs) if t["source_count"] >= 2][:60]
print(f"{len(topics)} Themen mit mindestens zwei Quellen")

# 3) Claude-Vergleiche für die größten Themen – nur neu, wenn neue Quellen dazukommen
cache = load("compare.json", [])
cache = [c for c in cache if hours_ago(c["at"]) <= KEEP_HOURS]
done = 0
for t in topics:
    if t["source_count"] < MIN_SOURCES_COMPARE:
        continue
    ids = {a["id"] for a in t["articles"]}
    best, best_overlap = None, 0.0
    for c in cache:
        overlap = len(ids & set(c["ids"])) / len(ids | set(c["ids"]))
        if overlap > best_overlap:
            best, best_overlap = c, overlap
    if best and best_overlap >= 0.4 and set(t["sources"]) <= set(best["sources"]):
        t["vergleich"] = best["result"]
        continue
    if not compare.available() or done >= MAX_COMPARE:
        continue
    try:
        result = compare.compare(t["articles"])
        done += 1
    except Exception as exc:
        print("Vergleich fehlgeschlagen:", exc)
        continue
    t["vergleich"] = result
    if best and best_overlap >= 0.4:
        cache.remove(best)
    cache.append({"ids": sorted(ids), "sources": t["sources"], "result": result, "at": now.isoformat()})
save(DATA, "compare.json", cache)
print(f"{done} neue Vergleiche erstellt")

# 4) Webseite schreiben
for t in topics:
    for a in t["articles"]:
        a["summary"] = (a.get("summary") or "")[:1500]
sources = {name: {"short": short, "type": typ, "lang": lang} for name, short, typ, lang, _ in FEEDS}
latest = sorted(recent, key=lambda a: a["published"], reverse=True)[:150]

shutil.rmtree(OUT, ignore_errors=True)
shutil.copytree("site", OUT)
save(OUT, "topics.json", {"topics": topics, "sources": sources, "stand": now.isoformat()})
save(OUT, "latest.json", {"articles": [{k: (a.get(k) or "")[:1500] if k == "summary" else a.get(k) for k in ("source", "title", "link", "published", "image", "summary")} for a in latest]})
save(OUT, "status.json", {
    "feeds": status,
    "abgleich": embed.status(),
    "vergleich": compare.available(),
    "stand": now.isoformat(),
})
print("Webseite geschrieben nach", OUT)
