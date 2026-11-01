/**
 * Nachrichtenlage – Live-Suche (Vercel-Funktion)
 *
 * Erreichbar unter https://<projekt>.vercel.app/api/live-search?q=…
 * Fragt bei jeder Suche alle Medien parallel ab, nimmt die neuesten Artikel quer über
 * die Medien (höchstens 2 pro Medium) und lässt Claude optional kurz zusammenfassen.
 *
 * Quelle der Treffer: Google-News-Suche je Medium (site:…), bei Problemen GDELT.
 * Einstellungen in Vercel → Project → Settings → Environment Variables:
 *   HENDRIK_API_KEY    (optional) – Claude-Key für Übersetzung und Zusammenfassung
 *   ALLOWED_ORIGIN     (optional) – Standard: https://wobbierilliams.github.io
 */

export const config = { runtime: "edge" };

const OUTLETS = [
  ["Tagesschau", "tagesschau.de", "de"],
  ["ZDFheute", "zdf.de", "de"],
  ["Deutschlandfunk", "deutschlandfunk.de", "de"],
  ["Deutsche Welle", "dw.com", "de"],
  ["WDR", "wdr.de", "de"],
  ["FAZ", "faz.net", "de"],
  ["Süddeutsche", "sueddeutsche.de", "de"],
  ["Welt", "welt.de", "de"],
  ["taz", "taz.de", "de"],
  ["Bild", "bild.de", "de"],
  ["Spiegel", "spiegel.de", "de"],
  ["Zeit", "zeit.de", "de"],
  ["Handelsblatt", "handelsblatt.com", "de"],
  ["Wirtschaftswoche", "wiwo.de", "de"],
  ["NZZ", "nzz.ch", "de"],
  ["Der Standard", "derstandard.at", "de"],
  ["BBC", "bbc.co.uk", "en"],
  ["The Guardian", "theguardian.com", "en"],
  ["Al Jazeera", "aljazeera.com", "en"],
  ["New York Times", "nytimes.com", "en"],
];

const RESULTS = 10;       // so viele Artikel liefert die Live-Suche
const PER_OUTLET = 2;     // höchstens so viele pro Medium
const CACHE_SECONDS = 600; // gleiche Suche 10 Minuten lang aus dem Zwischenspeicher
const MODEL = "claude-haiku-5-5";

export default async function handler(request) {
  // Claude-Key: HENDRIK_API_KEY (wie bei GitHub) oder ANTHROPIC_API_KEY
  // Notfalls jede Variable nehmen, deren Wert wie ein Claude-Key aussieht – der Name ist dann egal
  const anyKey = Object.values(process.env).find(v => typeof v === "string" && v.trim().startsWith("sk-ant-"));
  const env = { ...process.env, ANTHROPIC_API_KEY: (process.env.HENDRIK_API_KEY || process.env.ANTHROPIC_API_KEY || anyKey || "").trim() };
  const allowed = env.ALLOWED_ORIGIN || "https://wobbierilliams.github.io";
  const cors = {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Vary": "Origin",
  };
  if (request.method === "OPTIONS") return new Response(null, { headers: cors });

  // Nur die eigene Seite darf die Suche nutzen (schützt dein Claude-Guthaben)
  const origin = request.headers.get("Origin");
  if (origin !== allowed) return json({ error: "Nicht erlaubt" }, 403, cors);

  const url = new URL(request.url);
  const q = (url.searchParams.get("q") || "").trim().slice(0, 100);
  if (!q) return json({ error: "Suchbegriff fehlt" }, 400, cors);
  const wanted = (url.searchParams.get("sources") || "").split(",").filter(Boolean);
  const outlets = wanted.length ? OUTLETS.filter(o => wanted.includes(o[0])) : OUTLETS;
  const withSummary = url.searchParams.get("sum") === "1" && !!env.ANTHROPIC_API_KEY;

  try {
    const result = await search(q, outlets, env, withSummary);
    // Vercel speichert die Antwort 10 Minuten im CDN – gleiche Suche kostet dann nichts
    return json(result, 200, { ...cors, "Cache-Control": `public, s-maxage=${CACHE_SECONDS}, stale-while-revalidate=60` });
  } catch (err) {
    return json({ error: "Suche fehlgeschlagen", detail: String(err).slice(0, 200) }, 502, cors);
  }
}

async function search(q, outlets, env, withSummary) {
  const needsEnglish = outlets.some(o => o[2] === "en");
  const k = env.ANTHROPIC_API_KEY || "";
  // Nur die Form des Keys melden, nie den Key selbst
  const ai = {
    key: !!k, fehler: null,
    form: k ? { beginnt_mit_sk_ant: k.startsWith("sk-ant-"), laenge: k.length, leerzeichen: /\s/.test(k), anfuehrungszeichen: /["'“”„]/.test(k) } : null,
  };
  const note = err => { ai.fehler = ai.fehler || String(err).slice(0, 160); };
  const qEn = needsEnglish && env.ANTHROPIC_API_KEY ? await translate(q, env).catch(err => { note(err); return q; }) : q;

  let items = [];
  let engine = "google";
  const perOutlet = await Promise.all(
    outlets.map(o => googleNews(o[2] === "en" ? qEn : q, o).catch(() => []))
  );
  items = perOutlet.flat();

  if (!items.length) {
    engine = "gdelt";
    items = await gdelt(q, qEn, outlets).catch(() => []);
  }

  const picked = pickLatest(items);
  const out = {
    query: q,
    query_en: qEn !== q ? qEn : null,
    engine,
    at: new Date().toISOString(),
    outlets: outlets.length,
    found_in: [...new Set(items.map(i => i.source))],
    items: picked,
  };
  if (withSummary && picked.length >= 2) out.summary = await summarize(q, picked, env).catch(err => { note(err); return null; });
  out.ai = ai;
  return out;
}

// ---------- Relevanz: Suchbegriff muss in der Überschrift vorkommen ----------
function norm(t) {
  return (t || "").toLowerCase()
    .replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
}
function matcher(q) {
  const words = norm(q).split(" ").filter(w => w.length >= 3);
  if (!words.length) return () => true;
  return title => {
    const tw = norm(title).split(" ");
    // jedes Suchwort muss ein Wort der Überschrift beginnen – oder (ab 5 Buchstaben) darin stecken,
    // damit „Rente“ auch „Rentenpaket“ und „Grundrente“ findet
    return words.every(w => tw.some(t => t.startsWith(w) || (w.length >= 5 && t.includes(w))));
  };
}

// ---------- Google News (je Medium) ----------
async function googleNews(q, [name, domain, lang]) {
  const loc = lang === "en" ? { hl: "en-GB", gl: "GB", ceid: "GB:en" } : { hl: "de", gl: "DE", ceid: "DE:de" };
  const params = new URLSearchParams({ q: `${q} site:${domain} when:7d`, ...loc });
  const res = await fetch(`https://news.google.com/rss/search?${params}`, {
    headers: { "User-Agent": "Mozilla/5.0 (Nachrichtenlage Live-Suche)" },
  });
  if (!res.ok) throw new Error(`google ${res.status}`);
  const relevant = matcher(q);
  return parseRss(await res.text())
    .map(i => ({ ...i, source: name, lang, title: stripSource(i.title) }))
    .filter(i => relevant(i.title))
    .slice(0, 5);
}

function parseRss(xml) {
  const items = [];
  for (const m of xml.matchAll(/<item>([\s\S]*?)<\/item>/g)) {
    const tag = t => {
      const r = m[1].match(new RegExp(`<${t}[^>]*>([\\s\\S]*?)<\\/${t}>`));
      return r ? decode(r[1].replace(/^<!\[CDATA\[|\]\]>$/g, "")).trim() : "";
    };
    const title = tag("title"), link = tag("link"), pub = tag("pubDate");
    if (!title || !link) continue;
    const d = new Date(pub);
    items.push({ title, link, published: isNaN(d) ? null : d.toISOString() });
  }
  return items;
}

function stripSource(title) {
  // Google hängt " - Medienname" an
  let t = title.replace(/\s[-–]\s[^-–]{2,40}$/, "").trim();
  // manche Medien hängen selbst noch Ressort und Marke an, z. B. „… - Politik - SZ.de“
  t = t.replace(/\s[-–|]\s(?:[A-Za-zÄÖÜäöü ]{2,20}\s[-–|]\s)?(SZ\.de|ZEIT ONLINE|DER SPIEGEL|FAZ|tagesschau\.de|WELT|n-tv\.de)$/i, "").trim();
  return t;
}

function decode(s) {
  return s
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n)).replace(/&amp;/g, "&");
}

// ---------- GDELT (Rückfall) ----------
async function gdelt(q, qEn, outlets) {
  const relDe = matcher(q), relEn = matcher(qEn || q);
  const domains = outlets.map(o => `domainis:${o[1]}`).join(" OR ");
  const terms = qEn && qEn !== q ? `(${quote(q)} OR ${quote(qEn)})` : quote(q);
  const params = new URLSearchParams({
    query: `${terms} (${domains})`, mode: "artlist", maxrecords: "75",
    sort: "datedesc", timespan: "7d", format: "json",
  });
  const res = await fetch(`https://api.gdeltproject.org/api/v2/doc/doc?${params}`);
  if (!res.ok) throw new Error(`gdelt ${res.status}`);
  const data = await res.json();
  return (data.articles || []).map(a => {
    const o = outlets.find(x => a.domain && a.domain.endsWith(x[1]));
    const s = a.seendate || "";
    const iso = s.length >= 15 ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}T${s.slice(9, 11)}:${s.slice(11, 13)}:${s.slice(13, 15)}Z` : null;
    return o && { title: a.title, link: a.url, published: iso, source: o[0], lang: o[2], image: a.socialimage || "" };
  }).filter(Boolean).filter(i => (i.lang === "en" ? relEn : relDe)(i.title));
}

function quote(s) {
  return /\s/.test(s) ? `"${s.replace(/"/g, "")}"` : s;
}

// ---------- Auswahl: neueste, aber quer über die Medien ----------
function pickLatest(items) {
  const seen = new Set();
  const sorted = items
    .filter(i => i.published)
    .sort((a, b) => (a.published < b.published ? 1 : -1))
    .filter(i => {
      // Doppelte nur innerhalb eines Mediums entfernen – gleiche Agenturmeldung bei zwei Medien bleibt drin
      const key = i.source + "|" + i.title.toLowerCase().replace(/[^a-z0-9äöüß]+/g, " ").trim();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  const count = {};
  const out = [];
  for (const i of sorted) {
    if ((count[i.source] || 0) >= PER_OUTLET) continue;
    count[i.source] = (count[i.source] || 0) + 1;
    out.push(i);
    if (out.length >= RESULTS) break;
  }
  return out;
}

// ---------- Claude ----------
async function claude(env, prompt, maxTokens) {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({ model: env.NL_MODEL || MODEL, max_tokens: maxTokens, messages: [{ role: "user", content: prompt }] }),
  });
  if (!res.ok) throw new Error(`claude ${res.status}: ${(await res.text()).slice(0, 120)}`);
  const data = await res.json();
  const text = (data.content || []).filter(b => b.type === "text").map(b => b.text).join("").trim();
  if (!text) throw new Error(`leere Antwort (stop: ${data.stop_reason}, blöcke: ${(data.content || []).map(b => b.type).join("/")}, modell: ${data.model})`);
  return text;
}

async function translate(q, env) {
  const text = await claude(env,
    `Übersetze diesen Nachrichten-Suchbegriff ins Englische, so wie englischsprachige Medien ihn nennen würden. ` +
    `Eigennamen bleiben. Antworte nur mit dem Suchbegriff, ohne Anführungszeichen.\n\n${q}`, 40);
  return text.split("\n")[0].replace(/["„“]/g, "").trim().slice(0, 100) || q;
}

async function summarize(q, items, env) {
  const list = items.map(i => `- [${i.source}, ${i.published?.slice(0, 16).replace("T", " ")}] ${i.title}`).join("\n");
  const text = await claude(env,
    `Suchbegriff: ${q}\n\nDie neuesten Überschriften verschiedener Medien:\n${list}\n\n` +
    `Fasse auf Deutsch nüchtern zusammen, was diese Überschriften zum Suchbegriff zeigen. ` +
    `Nutze nur die Überschriften, ergänze kein eigenes Wissen, bewerte keine Medien. ` +
    `Antworte nur mit JSON: {"lage":"Neuester Stand in 2-3 Sätzen","schwerpunkte":["Wer betont was, je 1 kurzer Satz, höchstens 4"]}`, 600);
  const s = text.indexOf("{"), e = text.lastIndexOf("}");
  return JSON.parse(text.slice(s, e + 1));
}

// ---------- Hilfen ----------
function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...headers },
  });
}
