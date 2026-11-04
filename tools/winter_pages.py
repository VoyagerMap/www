"""Build the motorhome wintering pages. Imported by build-pages.py, which owns the sitemap.

One page per winter destination (Spain, Portugal), in the languages of the
people who drive there for the winter: English, German, Dutch and French. A
Japanese page about Spanish dump stations would be a URL nobody searches for,
so the language switcher is told which four exist, as on the city pages.

The copy lives in data/winter-copy/, hand-written per language, with
{placeholders} filled here from data/winter.csv (tools/winter-stats.py). The
chrome around it (consent panel, footer, store badges) comes from each
locale's landing group, like the city pages.
"""
import csv
import json
import os
import re

import city_pages

SITE = city_pages.SITE
LANGS = ["en", "de", "nl", "fr"]
COUNTRIES = {"motorhome-winter-spain": "ES", "motorhome-winter-portugal": "PT"}
COUNTED_ON = "2026-11-04"

# Tiles in the figures card, in the order a motorhome asks for them.
CATEGORIES = [("dump", "catDump"), ("lpg", "catLpg"), ("sites", "catSites"),
              ("campsites", "catCampsites"), ("water", "catWater"),
              ("laundry", "catLaundry")]

# A sentence of the copy that is only true while the data says so. A refresh
# that changes the fact fails the build instead of publishing a wrong claim.
CLAIMS = {
    # "...the south coast, where many motorhomes spend the winter"
    "motorhome-winter-spain": lambda whole, top: top["region"] == "Andalusia",
    # "...more fuel stations selling LPG than dump stations"
    "motorhome-winter-portugal": lambda whole, top: whole["lpg"] > whole["dump"],
}


def number(n, lang):
    """Thousands grouped the way the reader writes them: 1,709 / 1.709 / 1 709."""
    s = f"{n:,}"
    if lang in ("de", "nl"):
        return s.replace(",", ".")
    if lang == "fr":
        return s.replace(",", " ")
    return s


def url_for(lang, slug):
    tail = f"{slug}.html"
    return f"{SITE}/{tail}" if lang == "en" else f"{SITE}/{lang}/{tail}"


def load_stats(repo):
    """{country: (whole-country row, [region rows, most dump stations first])}"""
    out = {}
    for r in csv.DictReader(open(os.path.join(repo, "data", "winter.csv"), encoding="utf-8")):
        for k, v in r.items():
            if v.isdigit():
                r[k] = int(v)
        whole, regions = out.setdefault(r["country"], ({}, []))
        if r["region"]:
            regions.append(r)
        else:
            whole.update(r)
    return out


def read(repo, name):
    return json.load(open(os.path.join(repo, "data", "winter-copy", name), encoding="utf-8"))


def region_name(regions, country, region, lang):
    names = regions[country].get(region)
    if names is None:
        raise SystemExit(f"winter pages: no translation of region {region!r} "
                         "in data/winter-copy/_regions.json")
    return names.get(lang) or names.get("en") or region


def fill(text, values):
    def one(m):
        if m.group(1) not in values:
            raise SystemExit(f"winter pages: unknown placeholder {m.group(0)}")
        return values[m.group(1)]
    return re.sub(r"\{(\w+)\}", one, text)


def region_rows(regions, names, country, lang):
    out = []
    for r in regions:
        cells = "".join(f'\n                <td class="num">{number(r[f], lang)}</td>'
                        for f in ("dump", "lpg", "sites", "water"))
        out.append(f'              <tr>\n                <th scope="row">'
                   f'{city_pages.esc(region_name(names, country, r["region"], lang))}</th>'
                   f'{cells}\n              </tr>')
    return "\n".join(out)


def stat_grid(whole, copy, lang, indent="            "):
    out = []
    for field, label_key in CATEGORIES:
        out.append(
            f'{indent}<div class="city-stat">\n'
            f'{indent}  <dd class="city-stat-value">{number(whole[field], lang)}</dd>\n'
            f'{indent}  <dt class="city-stat-label" data-i18n="{label_key}">'
            f'{city_pages.esc(copy[label_key])}</dt>\n'
            f'{indent}</div>')
    return "\n".join(out)


def other_links(repo, slug, lang, copy):
    out = []
    for other in COUNTRIES:
        if other == slug:
            continue
        label = read(repo, f"{other}.{lang}.json")["linkLabel"]
        out.append(f'          <li><a href="./{other}.html" data-track="nav"'
                   f' data-nav-target="{other}">{city_pages.esc(label)}</a></li>')
    out.append(f'          <li><a href="./campervan-service-map.html" data-i18n="campervanLink">'
               f'{city_pages.esc(copy["campervanLink"])}</a></li>')
    return "\n".join(out)


def json_ld(copy, lang, country, canonical):
    page = {
        "@context": "https://schema.org", "@type": "WebPage",
        "name": copy["pageTitle"], "url": canonical,
        "description": copy["metaDescription"], "inLanguage": lang,
        "isPartOf": {"@type": "WebSite", "name": "Voyager Maps", "url": SITE + "/"},
        "about": {"@type": "Country", "name": copy["countryName"],
                  "identifier": country},
    }
    crumbs = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Voyager Maps",
             "item": SITE + ("/" if lang == "en" else f"/{lang}/")},
            {"@type": "ListItem", "position": 2, "name": copy["countryName"],
             "item": canonical},
        ],
    }
    blocks = []
    for obj in (page, crumbs):
        body = json.dumps(obj, ensure_ascii=False, indent=2).replace("\n", "\n      ")
        blocks.append(f'    <script type="application/ld+json">\n      {body}\n    </script>')
    return "\n".join(blocks)


def build(repo, locales, og_locale, write_locale):
    """Write every winter page. Returns [(lang, repo-relative path, canonical)]."""
    stats = load_stats(repo)
    names = read(repo, "_regions.json")
    template = open(os.path.join(repo, "data", "winter-page.template.html"),
                    encoding="utf-8").read()

    written = []
    for slug, country in COUNTRIES.items():
        whole, regions = stats[country]
        top = regions[0]
        if not CLAIMS[slug](whole, top):
            raise SystemExit(f"winter pages: the highlight of {slug} is no longer "
                             "true of data/winter.csv; rewrite it before building")
        for lang in LANGS:
            values = {k: number(whole[k], lang) for k in
                      ("dump", "lpg", "water", "sites", "campsites", "showers", "laundry")}
            values.update(topRegion=region_name(names, country, top["region"], lang),
                          topDump=number(top["dump"], lang),
                          topSites=number(top["sites"], lang),
                          date=COUNTED_ON)
            chrome = locales[lang]["landingPages"]["water"]
            copy = {k: chrome[k] for k in city_pages.CHROME if k in chrome}
            for source in (read(repo, f"_shared.{lang}.json"),
                           read(repo, f"{slug}.{lang}.json")):
                copy.update({k: fill(v, values) for k, v in source.items()
                             if not k.startswith("_")})

            rel = f"{slug}.html" if lang == "en" else f"{lang}/{slug}.html"
            canonical = url_for(lang, slug)
            a = "./" if lang == "en" else "../"

            hreflang = [f'    <link rel="canonical" href="{canonical}" />']
            hreflang += [f'    <link rel="alternate" hreflang="{c}" href="{url_for(c, slug)}" />'
                         for c in LANGS]
            hreflang.append(f'    <link rel="alternate" hreflang="x-default" '
                            f'href="{url_for("en", slug)}" />')
            oglocale = [f'    <meta property="og:locale" content="{og_locale[lang]}" />']
            oglocale += [f'    <meta property="og:locale:alternate" content="{og_locale[c]}" />'
                         for c in LANGS if c != lang]

            locale_file = f"locales/pages/{lang}.{slug}.js"
            write_locale(locale_file, lang, {"winterPages": {slug: dict(copy, htmlLang=lang)}})

            html = template
            for key, value in {
                "lang": lang, "dir": "", "a": a,
                "title": city_pages.esc(copy["pageTitle"]),
                "description": city_pages.esc(copy["metaDescription"]),
                "canonical": canonical,
                "hreflang": "\n".join(hreflang),
                "oglocale": "\n".join(oglocale),
                "jsonld": json_ld(copy, lang, country, canonical),
                "badges_hero": city_pages.badges(copy, "hero"),
                "badges_cta": city_pages.badges(copy, "final"),
                "proof": city_pages.proof_row(copy),
                "stat_grid": stat_grid(whole, copy, lang),
                "region_rows": region_rows(regions, names, country, lang),
                "other_links": other_links(repo, slug, lang, copy),
                "localefile": locale_file,
                "pageconfig": json.dumps({
                    "localeKey": slug, "localeGroup": "winterPages",
                    "pageType": "winter_page", "topic": "motorhome_winter",
                    "languages": LANGS}, ensure_ascii=False),
            }.items():
                html = html.replace("{{%s}}" % key, str(value))
            for key, value in copy.items():
                html = html.replace("{{%s}}" % key, city_pages.esc(value))
            left = re.findall(r"\{\{\w+\}\}", html)
            if left:
                raise SystemExit(f"winter pages: {rel} left unfilled: {sorted(set(left))}")

            dest = os.path.join(repo, rel)
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            open(dest, "w", encoding="utf-8").write(html)
            written.append((lang, rel, canonical))
    return written


def teaser(repo, code):
    """The campervan page's way in, in the four languages that have the pages.

    Without it the pages are orphans. Every other language gets nothing:
    a link in English on a Korean page would be a dead end for its reader.
    """
    if code not in LANGS:
        return ""
    shared = read(repo, f"_shared.{code}.json")
    links = "\n".join(
        f'          <li><a href="./{slug}.html" data-track="nav"'
        f' data-nav-target="{slug}">'
        f'{city_pages.esc(read(repo, f"{slug}.{code}.json")["linkLabel"])}</a></li>'
        for slug in COUNTRIES)
    return (f'\n      <section class="card" data-track-section="winter_teaser">\n'
            f'        <h2>{city_pages.esc(shared["teaserTitle"])}</h2>\n'
            f'        <p>{city_pages.esc(shared["teaserText"])}</p>\n'
            f'        <ul class="city-links">\n{links}\n        </ul>\n'
            f'      </section>\n      ')
