"""Perspektivvergleich eines Themas mit Claude. Braucht ANTHROPIC_API_KEY (GitHub-Secret).

Um Kosten klein zu halten, wird ein Thema nur neu verglichen, wenn neue Quellen dazukommen."""
import os

MODEL = os.environ.get("NL_MODEL", "claude-haiku-5-5")

PROMPT = """Du bekommst Überschriften und Teaser verschiedener Medien zum selben Thema, teils auf Englisch.
Antworte immer auf Deutsch.
Vergleiche nüchtern, wie die Medien berichten. Nutze ausschließlich die gelieferten Texte,
ergänze kein eigenes Wissen und bewerte keine politische Ausrichtung der Medien.
Bedenke, dass Teaser kurz sind: Was fehlt, muss im Artikel nicht fehlen.

Antworte nur mit JSON in genau dieser Form:
{{
  "kern": "Was übereinstimmend berichtet wird (2-3 Sätze)",
  "perspektiven": [{{"quelle": "Name", "schwerpunkt": "Worauf diese Quelle den Fokus legt, 1 Satz"}}],
  "unterschiede": ["Konkreter Unterschied in Gewichtung, Wortwahl oder Fakten"],
  "offen": "Was unklar oder widersprüchlich bleibt (1-2 Sätze, oder leer)"
}}

Meldungen:
{items}"""


def available():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def compare(articles):
    import json
    import anthropic

    items = "\n".join(
        f"- [{a['source']}] {a['title']} — {(a.get('summary') or '')[:300]}" for a in articles[:25]
    )
    msg = anthropic.Anthropic().messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": PROMPT.format(items=items)}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    return json.loads(text[text.find("{") : text.rfind("}") + 1])
