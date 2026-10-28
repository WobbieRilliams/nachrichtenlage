"""Liste der Quellen. Feed-URLs ändern sich gelegentlich – der Tab "Quellen" in der App
zeigt an, welche Feeds gerade nicht funktionieren. Einfach hier anpassen oder ergänzen."""

FEEDS = [
    # name, kurz, typ, sprache, url
    ("Tagesschau", "TS", "öffentlich-rechtlich", "de", "https://www.tagesschau.de/xml/rss2/"),
    ("ZDFheute", "ZDF", "öffentlich-rechtlich", "de", "https://www.zdf.de/rss/zdf/nachrichten"),
    ("Deutschlandfunk", "DLF", "öffentlich-rechtlich", "de", "https://www.deutschlandfunk.de/nachrichten-100.rss"),
    ("Deutsche Welle", "DW", "öffentlich-rechtlich", "de", "https://rss.dw.com/rdf/rss-de-all"),
    ("WDR", "WDR", "öffentlich-rechtlich", "de", "https://www1.wdr.de/uebersicht-100.feed"),
    ("FAZ", "FAZ", "Tageszeitung", "de", "https://www.faz.net/rss/aktuell/"),
    ("Süddeutsche", "SZ", "Tageszeitung", "de", "https://rss.sueddeutsche.de/rss/Topthemen"),
    ("Welt", "WELT", "Tageszeitung", "de", "https://www.welt.de/feeds/latest.rss"),
    ("taz", "taz", "Tageszeitung", "de", "https://taz.de/!p4608;rss/"),
    ("Bild", "BILD", "Boulevard", "de", "https://www.bild.de/feed/alles.xml"),
    ("Spiegel", "SPON", "Magazin", "de", "https://www.spiegel.de/schlagzeilen/index.rss"),
    ("Zeit", "ZEIT", "Wochenzeitung", "de", "https://newsfeed.zeit.de/index"),
    ("Handelsblatt", "HB", "Wirtschaft", "de", "https://www.handelsblatt.com/contentexport/feed/schlagzeilen"),
    ("Wirtschaftswoche", "WiWo", "Wirtschaft", "de", "https://www.wiwo.de/contentexport/feed/rss/schlagzeilen"),
    ("NZZ", "NZZ", "international (CH)", "de", "https://www.nzz.ch/recent.rss"),
    ("Der Standard", "STD", "international (AT)", "de", "https://www.derstandard.at/rss"),
    ("BBC", "BBC", "international (UK)", "en", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("The Guardian", "GDN", "international (UK)", "en", "https://www.theguardian.com/world/rss"),
    ("Al Jazeera", "AJ", "international (QA)", "en", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("New York Times", "NYT", "international (US)", "en", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
]

# Abrufintervall steht in .github/workflows/update.yml (cron)

# Wie weit zurück Meldungen für die Themen berücksichtigt werden (Stunden)
WINDOW_HOURS = 36
