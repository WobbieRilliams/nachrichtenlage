"""Bedeutungs-Vektoren für Meldungen – sprachübergreifend (Deutsch, Englisch und 50 weitere).

Kleines mehrsprachiges Modell (fastembed/ONNX), läuft direkt im GitHub-Job, ohne API-Key.
Vektoren werden in data/embeddings.npz zwischengespeichert, damit jede Meldung nur einmal
berechnet wird. Ohne fastembed fällt das Projekt auf den Wortabgleich zurück."""
import os

import numpy as np

MODEL = os.environ.get("NL_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
CACHE = "data/embeddings.npz"

_model = None
_error = None


def _load():
    global _model, _error
    if _model is None and _error is None:
        try:
            from fastembed import TextEmbedding
            _model = TextEmbedding(model_name=MODEL, cache_dir=os.environ.get("NL_MODEL_CACHE"))
        except Exception as exc:
            _error = str(exc)[:200]
    return _model


def status():
    _load()
    return {"aktiv": _model is not None, "modell": MODEL, "fehler": _error}


def _text(a):
    return f"{a['title']}. {(a.get('summary') or '')[:300]}"


def _compute(texts):
    return [np.asarray(v, dtype=np.float32) for v in _load().embed(texts, batch_size=32)]


def vectors(articles):
    """{artikel_id: normierter Vektor} oder None, wenn kein Modell verfügbar ist."""
    if _load() is None:
        return None
    cache = {}
    if os.path.exists(CACHE):
        with np.load(CACHE) as f:
            cache = {k: f[k] for k in f.files}

    out = {a["id"]: cache[a["id"]] for a in articles if a["id"] in cache}
    missing = [a for a in articles if a["id"] not in out]
    if missing:
        for a, v in zip(missing, _compute([_text(a) for a in missing])):
            out[a["id"]] = v / (np.linalg.norm(v) or 1.0)

    os.makedirs("data", exist_ok=True)
    np.savez(CACHE, **out)  # nur aktuelle Meldungen behalten
    print(f"Vektoren: {len(out) - len(missing)} aus Cache, {len(missing)} neu berechnet")
    return out
