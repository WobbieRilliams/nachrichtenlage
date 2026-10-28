"""Feeds abrufen und lesen (RSS 2.0, RSS 1.0/RDF, Atom) – nur Standardbibliothek."""
import hashlib
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

USER_AGENT = "Mozilla/5.0 (Nachrichtenlage; privater RSS-Leser)"


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def _child(el, *names):
    for c in el:
        if _local(c.tag) in names:
            return c
    return None


def _text(el, *names):
    c = _child(el, *names)
    return (c.text or "").strip() if c is not None and c.text else ""


def _date(value):
    if not value:
        return datetime.now(timezone.utc)
    try:
        d = parsedate_to_datetime(value)  # RSS: "Wed, 28 Oct 2026 10:00:00 +0100"
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(value.replace("Z", "+00:00"))  # Atom/RDF: ISO 8601
        except ValueError:
            return datetime.now(timezone.utc)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _image(item):
    for c in item:
        tag = _local(c.tag)
        if tag in ("content", "thumbnail") and c.get("url") and "image" in (c.get("type") or c.get("medium") or "image"):
            return c.get("url")
        if tag == "enclosure" and (c.get("type") or "").startswith("image"):
            return c.get("url")
    return None


def _link(item):
    link = _text(item, "link")
    if link:
        return link
    for c in item:  # Atom: <link href="..."/>
        if _local(c.tag) == "link" and c.get("href") and c.get("rel", "alternate") == "alternate":
            return c.get("href")
    return _text(item, "guid")

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def parse_feed(name, data):
    """data: roher Feed (RSS 2.0, RSS 1.0/RDF oder Atom) als bytes/str."""
    root = ET.fromstring(data)
    entries = [el for el in root.iter() if _local(el.tag) in ("item", "entry")]
    items = []
    for e in entries:
        link = _link(e)
        title = _clean(_text(e, "title"))
        if not link or not title:
            continue
        summary = _text(e, "description", "summary", "encoded", "content")
        items.append({
            "id": hashlib.sha1(link.encode()).hexdigest()[:16],
            "source": name,
            "title": title,
            "summary": _clean(summary)[:600],
            "link": link,
            "image": _image(e),
            "published": _date(_text(e, "pubdate", "published", "updated", "date")).isoformat(),
        })
    return items


