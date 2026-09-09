"""Build the per-city pages. Imported by build-pages.py, which owns the sitemap.

Each published city gets an English page at /<slug>-map.html and, when its
country's language is one of the site's thirteen, a second at
/<lang>/<slug>-map.html. Nothing else: a Korean page about Vienna's toilets
would be a URL nobody searches for, and the language switcher is told which
two exist so it cannot offer the eleven that do not.

The copy comes pre-rendered and pre-translated from data/city-copy/ — see
tools/city-copy.py for why the translation happens there and not here. The
chrome around it (consent panel, footer, store badges) is reused from each
locale's existing landingPages group rather than translated again.
"""
import csv
import json
import os

SITE = "https://getvoyagermaps.com"
APPLE = "https://apps.apple.com/app/6758412494"
GOOGLE = ("https://play.google.com/store/apps/details"
          "?id=com.voyagermap.voyagermobil.voyagermobil")

# Keys the page renders that are not about the city. Taken from the water
# landing group, whose values are identical across all six groups.
CHROME = [
    "htmlLang", "brandLabel", "langSwitcherAria", "langOptionsAria",
    "badgeAppleLine", "badgeGoogleLine", "badgeAppleAria", "badgeGoogleAria",
    "proofRatingValue", "proofDownloadsValue", "proofDownloadsLabel",
    "proofStores", "proofRatingAria", "pageFree",
    "exploreTitle", "exploreHomeLink", "exploreWaterLink", "exploreToiletLink",
    "exploreShowerLink", "exploreParkingLink", "exploreCampervanLink",
    "exploreBackpackerLink",
    "legalTitle", "privacyLink", "termsLink", "deleteLink", "footer",
    "consentEyebrow", "consentTitle", "consentDescription",
    "consentNecessaryLabel", "consentNecessaryDescription",
    "consentNecessaryValue", "consentStatisticsLabel", "consentStatisticsValue",
    "consentNote", "consentReject", "consentCustomize", "consentSave",
    "consentAccept", "consentManage",
]

# Stat tiles, in the order they read: the two the page is about, then the rest.
CATEGORIES = [("toilets", "catToilets"), ("water", "catWater"),
              ("parking", "catParking"), ("showers", "catShowers"),
              ("laundry", "catLaundry"), ("pharmacy", "catPharmacy")]
ATTRIBUTES = [("free_of_charge", "attrFree"), ("step_free", "attrStepFree"),
              ("with_hours", "attrHours"), ("wifi", "attrWifi")]

APPLE_SVG = ('<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" focusable="false">'
             '<path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.3.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>')
GOOGLE_SVG = ('<svg width="19" height="21" viewBox="0 0 512 512" fill="currentColor" focusable="false">'
              '<path d="M325.3 234.3L104.6 13l280.8 161.2-60.1 60.1zM47 0C34 6.8 25.3 19.2 25.3 35.3v441.3c0 16.1 8.7 28.5 21.7 35.3l2.7 1.5 247.2-247v-5.8L47 0zm425.2 225L377.5 167l-65.1 65 65.1 65 95.6-57c27.2-15.6 27.2-41 0-56.6zM104.6 499l280.8-161.2-60.1-60.1-220.7 221.3z"/></svg>')
STAR = ("M7 .35 8.44 4.618 12.945 4.669 9.33 7.357 10.674 11.657 "
        "7 9.05 3.326 11.657 4.67 7.357 1.055 4.669 5.56 4.618Z")


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def url_for(lang, slug):
    tail = f"{slug}-map.html"
    return f"{SITE}/{tail}" if lang == "en" else f"{SITE}/{lang}/{tail}"


def load(repo):
    """Published cities, newest counts first, as plain dicts."""
    path = os.path.join(repo, "data", "cities.csv")
    rows = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["published"] != "yes":
            continue
        for k, v in r.items():
            if v.isdigit():
                r[k] = int(v)
        rows.append(r)
    rows.sort(key=lambda r: -r["total"])
    return rows


def badges(copy, position):
    out = []
    for href, svg, line_key, name, kind, aria in (
            (APPLE, APPLE_SVG, "badgeAppleLine", "App Store", "app_store_ios", "badgeAppleAria"),
            (GOOGLE, GOOGLE_SVG, "badgeGoogleLine", "Google Play", "app_store_android", "badgeGoogleAria")):
        out.append(f'''            <a class="store-badge" href="{href}"
               aria-label="{esc(copy[aria])}" data-i18n-aria="{aria}"
               data-track="cta" data-cta-type="{kind}" data-cta-position="{position}">
              <span class="store-badge-icon" aria-hidden="true">{svg}</span>
              <span class="store-badge-copy">
                <span class="store-badge-line1" data-i18n="{line_key}">{esc(copy[line_key])}</span>
                <span class="store-badge-line2">{name}</span>
              </span>
            </a>''')
    return "\n".join(out)


def proof_row(copy):
    paths = "".join(
        f'<path{"" if i == 0 else f" transform=\"translate({i * 15} 0)\""} d="{STAR}" />'
        for i in range(5))
    return f'''          <p class="hero-proof">
            <svg class="hero-proof-stars" width="74" height="12" viewBox="0 0 74 12" role="img" aria-label="{esc(copy["proofRatingAria"])}" data-i18n-aria="proofRatingAria" focusable="false">
              <defs><linearGradient id="proofStars" x1="1" y1="0" x2="73" y2="0" gradientUnits="userSpaceOnUse"><stop offset="0.98" stop-color="#f0b429" /><stop offset="0.98" stop-color="#33425e" /></linearGradient></defs>
              <g fill="url(#proofStars)">{paths}</g>
            </svg>
            <span class="hero-proof-value" data-i18n="proofRatingValue">{esc(copy["proofRatingValue"])}</span>
            <span class="hero-proof-sep" aria-hidden="true">·</span>
            <span class="hero-proof-count" data-i18n="proofDownloadsValue">{esc(copy["proofDownloadsValue"])}</span>
            <span data-i18n="proofDownloadsLabel">{esc(copy["proofDownloadsLabel"])}</span>
            <span class="hero-proof-sep" aria-hidden="true">·</span>
            <span class="hero-proof-stores" data-i18n="proofStores">{esc(copy["proofStores"])}</span>
          </p>'''


def grid(row, copy, pairs, indent="            "):
    """A definition list of count and label — the substance of the page."""
    out = []
    for field, label_key in pairs:
        out.append(
            f'{indent}<div class="city-stat">\n'
            f'{indent}  <dd class="city-stat-value">{row[field]:,}</dd>\n'
            f'{indent}  <dt class="city-stat-label" data-i18n="{label_key}">'
            f'{esc(copy[label_key])}</dt>\n'
            f'{indent}</div>')
    return "\n".join(out)


def other_cities(rows, current, lang):
    """Six neighbours by size, linked in the language the reader is already in."""
    pool = [r for r in rows if r["slug"] != current["slug"]
            and (lang == "en" or r["lang"] == lang)]
    picks = pool[:6] if lang != "en" else (
        pool[:3] + [r for r in pool[3:] if r["country"] != current["country"]][:3])
    out = []
    for r in picks:
        href = f"./{r['slug']}-map.html"
        out.append(f'          <li><a href="{href}">{esc(r["name_en"])}'
                   f' <span class="city-link-count">{r["total"]:,}</span></a></li>')
    return "\n".join(out)


def json_ld(row, copy, lang, langs, canonical):
    page = {
        "@context": "https://schema.org", "@type": "WebPage",
        "name": copy["pageTitle"], "url": canonical,
        "description": copy["metaDescription"], "inLanguage": lang,
        "isPartOf": {"@type": "WebSite", "name": "Voyager Maps", "url": SITE + "/"},
        "about": {"@type": "City", "name": row["name_en"],
                  "address": {"@type": "PostalAddress",
                              "addressCountry": row["country"]}},
    }
    crumbs = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Voyager Maps",
             "item": SITE + ("/" if lang == "en" else f"/{lang}/")},
            {"@type": "ListItem", "position": 2, "name": row["name_en"],
             "item": canonical},
        ],
    }
    blocks = []
    for obj in (page, crumbs):
        body = json.dumps(obj, ensure_ascii=False, indent=2).replace("\n", "\n      ")
        blocks.append(f'    <script type="application/ld+json">\n      {body}\n    </script>')
    return "\n".join(blocks)


def teaser(repo, code, built, dic, limit=12, per_country=2):
    """The homepage's way in to the city pages.

    Without this they are orphans: nothing on the site links to them, which
    costs a reader any chance of finding them and costs a crawler the internal
    links it reads as a signal. Capped at two per country so the list reads as
    a world map rather than a ranking — by raw size the first six would be
    Japan and Australia.

    A city links to its page in the reader's own language where that page was
    built, and to the English one otherwise. Nothing here can point at a URL
    that does not exist.
    """
    have = {}
    for lang, rel, _ in built:
        slug = os.path.basename(rel)[:-len("-map.html")]
        have.setdefault(slug, set()).add(lang)

    picks, per = [], {}
    for r in load(repo):
        if per.get(r["country"], 0) >= per_country:
            continue
        picks.append(r)
        per[r["country"]] = per.get(r["country"], 0) + 1
        if len(picks) == limit:
            break

    up = "" if code == "en" else "../"
    out = []
    for r in picks:
        local = code in have.get(r["slug"], set())
        href = f"./{r['slug']}-map.html" if local else f"{up}{r['slug']}-map.html"
        out.append(
            f'          <li><a class="city-teaser-card" href="{href}"'
            f' data-track="city" data-city="{r["slug"]}">\n'
            f'            <span class="city-teaser-name">{esc(r["name_en"])}</span>\n'
            f'            <span class="city-teaser-figures">'
            f'<span><b>{r["toilets"]:,}</b> {esc(dic["citiesToiletsLabel"])}</span>'
            f'<span><b>{r["water"]:,}</b> {esc(dic["citiesWaterLabel"])}</span>'
            f'</span>\n          </a></li>')
    return "\n".join(out)


def build(repo, locales, og_locale, write_locale):
    """Write every city page. Returns [(lang, repo-relative path, canonical)]."""
    rows = load(repo)
    template = open(os.path.join(repo, "data", "city-page.template.html"),
                    encoding="utf-8").read()
    shared = {}
    for lang in {"en"} | {r["lang"] for r in rows if r["lang"]}:
        shared[lang] = json.load(open(
            os.path.join(repo, "data", "city-copy", f"_shared.{lang}.json"),
            encoding="utf-8"))

    written = []
    for row in rows:
        langs = ["en"] + ([row["lang"]] if row["lang"] else [])
        for lang in langs:
            city = json.load(open(
                os.path.join(repo, "data", "city-copy", f"{row['slug']}.{lang}.json"),
                encoding="utf-8"))
            chrome = locales[lang]["landingPages"]["water"]
            copy = {k: chrome[k] for k in CHROME if k in chrome}
            copy.update({k: v for k, v in shared[lang].items() if not k.startswith("_")})
            copy.update({k: v for k, v in city.items() if not k.startswith("_")})

            page = f"{row['slug']}-map.html"
            rel = page if lang == "en" else f"{lang}/{page}"
            canonical = url_for(lang, row["slug"])
            a = "./" if lang == "en" else "../"

            hreflang = [f'    <link rel="canonical" href="{canonical}" />']
            for c in langs:
                hreflang.append(f'    <link rel="alternate" hreflang="{c}" '
                                f'href="{url_for(c, row["slug"])}" />')
            hreflang.append(f'    <link rel="alternate" hreflang="x-default" '
                            f'href="{url_for("en", row["slug"])}" />')
            oglocale = [f'    <meta property="og:locale" content="{og_locale[lang]}" />']
            oglocale += [f'    <meta property="og:locale:alternate" content="{og_locale[c]}" />'
                         for c in langs if c != lang]

            locale_file = f"locales/pages/{lang}.{row['slug']}-map.js"
            write_locale(locale_file, lang,
                         {"cityPages": {row["slug"]: dict(copy, htmlLang=lang)}})

            html = template
            for key, value in {
                "lang": lang, "a": a, "h": "./",
                "title": esc(copy["pageTitle"]),
                "description": esc(copy["metaDescription"]),
                "canonical": canonical,
                "hreflang": "\n".join(hreflang),
                "oglocale": "\n".join(oglocale),
                "jsonld": json_ld(row, copy, lang, langs, canonical),
                "badges_hero": badges(copy, "hero"),
                "badges_cta": badges(copy, "final"),
                "proof": proof_row(copy),
                "stat_grid": grid(row, copy, CATEGORIES),
                "attr_grid": grid(row, copy, ATTRIBUTES),
                "other_cities": other_cities(rows, row, lang),
                "localefile": locale_file,
                "pageconfig": json.dumps({
                    "localeKey": row["slug"], "localeGroup": "cityPages",
                    "pageType": "city_page", "topic": "city",
                    "languages": langs}, ensure_ascii=False),
            }.items():
                html = html.replace("{{%s}}" % key, str(value))
            # Remaining single-word placeholders are copy keys.
            for key, value in copy.items():
                html = html.replace("{{%s}}" % key, esc(value))

            dest = os.path.join(repo, rel)
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            open(dest, "w", encoding="utf-8").write(html)
            written.append((lang, rel, canonical))
    return written
