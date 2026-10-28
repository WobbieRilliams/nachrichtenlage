"""Gruppiert Meldungen verschiedener Quellen zu Themen (TF-IDF + Kosinus-Ähnlichkeit).
Bewusst ohne schwere Abhängigkeiten, damit es flott auf dem Raspberry Pi läuft."""
import math
import re
from collections import Counter, defaultdict

STOP = set("""
aber alle allem allen aller alles als also am an ander andere anderem anderen anderer anderes
auch auf aus bei beim bin bis bisher bist da dabei dadurch dafür dagegen daher damit danach
dann darauf darf darum das dass dein deine dem den denen denn der deren des deshalb dessen die
dies diese diesem diesen dieser dieses doch dort du durch ein eine einem einen einer eines
einige er es etwa euch für gegen gibt hat hatte hätte haben hier hin hinter ich ihm ihn ihr
ihre ihrem ihren ihrer im immer in ins ist ja jede jedem jeden jeder jetzt kann kein keine
können könnte man mehr mein meine mit muss müssen nach neue neuen nicht nichts noch nun nur
ob oder ohne schon sehr sei seid sein seine seinem seinen seiner seit sich sie sind so soll
sollen sollte sondern sowie über um und uns unser unter viel vom von vor wann war waren
warum was weil welche welchem welchen welcher wenn wer werden wie wieder will wir wird wo
wurde wurden zu zum zur zwei drei jahr jahre jahren mehrere laut sagt sagte heute gestern
morgen beim bereits dpa afp reuters newsblog liveblog ticker live video podcast kommentar
analyse meinung exklusiv neu news update aktuell aktuelle the and for with that this from
""".split())

WORD = re.compile(r"[a-zäöüß0-9]+")

# Deutschsprachige Quellen bevorzugt als Thementitel
from feeds import FEEDS
GERMAN = {f[0] for f in FEEDS if f[3] == "de"}


def _stem(w):
    if len(w) > 6:
        for suf in ("ungen", "ung", "en", "er", "es", "em", "e", "n", "s"):
            if w.endswith(suf):
                return w[: -len(suf)]
    return w


def tokens(text):
    return [_stem(w) for w in WORD.findall(text.lower()) if len(w) > 2 and w not in STOP]


def _vectors(articles):
    docs = []
    for a in articles:
        tf = Counter(tokens(a["title"]) * 2 + tokens(a.get("summary", "")))
        docs.append(tf)
    df = Counter(t for d in docs for t in d)
    n = len(docs)
    vecs = []
    for d in docs:
        v = {t: (1 + math.log(c)) * math.log((1 + n) / (1 + df[t])) for t, c in d.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm for t, x in v.items()})
    return vecs


def _cos(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def _add(centroid, vec, size):
    out = defaultdict(float)
    for t, x in centroid.items():
        out[t] += x * size
    for t, x in vec.items():
        out[t] += x
    norm = math.sqrt(sum(x * x for x in out.values())) or 1.0
    return {t: x / norm for t, x in out.items()}


# Ab welcher Ähnlichkeit zwei Meldungen als dasselbe Thema gelten.
# Höher = strengere Themen, niedriger = mehr wird zusammengefasst.
WORD_THRESHOLD = 0.16      # Wortabgleich (Rückfall ohne Sprachmodell)
MEANING_THRESHOLD = float(__import__("os").environ.get("NL_MEANING_THRESHOLD", 0.62))


def _greedy_words(arts, vecs, threshold):
    groups = []
    for i, v in enumerate(vecs):
        if not v:
            continue
        best, best_sim = None, threshold
        for g in groups:
            s = _cos(v, g["centroid"])
            if s > best_sim:
                best, best_sim = g, s
        if best is None:
            groups.append({"centroid": v, "members": [i]})
        else:
            best["centroid"] = _add(best["centroid"], v, len(best["members"]))
            best["members"].append(i)
    return [g["members"] for g in groups]


def _greedy_meaning(arts, emb, threshold):
    import numpy as np
    X = np.stack([emb[a["id"]] for a in arts])
    sums, counts, members = [], [], []
    for i in range(len(arts)):
        if sums:
            C = np.stack(sums)
            C = C / np.linalg.norm(C, axis=1, keepdims=True)
            sims = C @ X[i]
            j = int(np.argmax(sims))
            if sims[j] > threshold:
                sums[j] = sums[j] + X[i]
                members[j].append(i)
                continue
        sums.append(X[i].copy())
        members.append([i])
    return members


def cluster(articles, embeddings=None):
    """Gibt Themen zurück, sortiert nach Anzahl unterschiedlicher Quellen.
    embeddings: {artikel_id: Vektor} für den Bedeutungs-Abgleich; ohne → Wortabgleich."""
    if not articles:
        return []
    arts = sorted(articles, key=lambda a: a["published"])
    vecs = _vectors(arts)
    use_meaning = bool(embeddings) and all(a["id"] in embeddings for a in arts)
    if use_meaning:
        groups = _greedy_meaning(arts, embeddings, MEANING_THRESHOLD)
    else:
        groups = _greedy_words(arts, vecs, WORD_THRESHOLD)

    topics = []
    for idx in groups:
        members = [arts[i] for i in idx]
        sources = sorted({m["source"] for m in members})
        # Stichworte und repräsentative Meldung aus dem Wortprofil des Themas
        centroid = defaultdict(float)
        for i in idx:
            for t, x in vecs[i].items():
                centroid[t] += x
        rep_idx = max(idx, key=lambda i: (_cos(vecs[i], centroid), arts[i]["source"] in GERMAN))
        terms = sorted(centroid.items(), key=lambda kv: -kv[1])[:5]
        members.sort(key=lambda m: m["published"], reverse=True)
        topics.append({
            "id": "-".join(sorted(m["id"] for m in members))[:64],
            "title": arts[rep_idx]["title"],
            "keywords": [t for t, _ in terms],
            "sources": sources,
            "source_count": len(sources),
            "articles": members,
            "latest": members[0]["published"],
            "method": "bedeutung" if use_meaning else "woerter",
        })
    topics.sort(key=lambda t: (t["source_count"], t["latest"]), reverse=True)
    return topics
