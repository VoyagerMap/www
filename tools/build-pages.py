#!/usr/bin/env python3
"""Generate the localized pages, the hreflang mesh and the sitemap.

English lives at the site root and is the source of truth for structure; every
other language is generated from it into /<code>/ with the text baked in from
locales/<code>.js. The text has to be in the HTML rather than applied by script
alone, otherwise a crawler indexes the English copy under a localized URL.

Usage:  python3 tools/build-pages.py
"""
import html as H
import json
import os
import re
import subprocess
import sys
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import city_pages  # noqa: E402  (needs REPO on the path first)
SITE = "https://getvoyagermaps.com"

# Root-relative pages, and which locale group each one reads.
PAGES = {
    "index.html": None,
    "drinking-water-map.html": "water",
    "public-toilet-map.html": "toilet",
    "free-shower-map.html": "shower",
    "parking-map.html": "parking",
    "campervan-service-map.html": "campervan",
    "backpacker-map.html": "backpacker",
}
LEGAL = ["privacy-policy.html", "terms.html", "delete-data.html"]

# Open Graph expects language_TERRITORY. The territory is the market we address
# with that language, not the only place it is spoken.
OG_LOCALE = {
    "en": "en_US", "de": "de_DE", "fr": "fr_FR", "es": "es_ES", "it": "it_IT",
    "pt": "pt_BR", "nl": "nl_NL", "pl": "pl_PL", "hu": "hu_HU", "ja": "ja_JP",
    "zh": "zh_CN", "ko": "ko_KR", "hi": "hi_IN",
}


def node_json(expr):
    out = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{REPO}:/w", "-w", "/w", "node:20-alpine",
         "node", "-e", expr],
        capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def load_languages():
    return node_json("global.window={};require('/w/assets/languages.js');"
                     "console.log(JSON.stringify(window.voyagerLanguages))")


def load_locales(codes):
    req = ";".join(f"require('/w/locales/{c}.js')" for c in codes)
    return node_json(f"global.window={{}};{req};"
                     "console.log(JSON.stringify(window.voyagerLocales))")


def url_for(code, page):
    """English at the root, everything else under its language directory."""
    path = "" if page == "index.html" else page
    return f"{SITE}/{path}" if code == "en" else f"{SITE}/{code}/{path}"


def href_for(code, page, from_code):
    """Link between pages, relative to the page doing the linking.

    Root-absolute paths (/assets/...) only resolve when the site is served from
    a domain root — opening a file directly or serving from a subdirectory
    silently breaks every asset, which leaves the language register empty and
    the switcher stuck on English. Relative paths work in both cases.
    """
    # index.html is named explicitly rather than linked as a bare directory:
    # a server would resolve "/de/" to its index, but the same page opened from
    # disk just shows a directory listing.
    path = "index.html" if page == "index.html" else page
    if code == from_code:                      # same language: same directory
        return f"./{path}"
    up = "" if from_code == "en" else "../"
    return f"{up}{path}" if code == "en" else f"{up}{code}/{path}"


def asset(path, from_code):
    """An asset URL relative to the page that loads it."""
    return ("./" if from_code == "en" else "../") + path.lstrip("/")


def hreflang_block(page, codes, indent="    "):
    lines = [f'{indent}<link rel="canonical" href="{url_for("%s", page)}" />']
    for c in codes:
        lines.append(f'{indent}<link rel="alternate" hreflang="{c}" href="{url_for(c, page)}" />')
    lines.append(f'{indent}<link rel="alternate" hreflang="x-default" href="{url_for("en", page)}" />')
    return "\n".join(lines)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def localize(source, code, dic, page, codes, page_codes=None):
    """Bake one language's text into the source page.

    `codes` is every language the site has — used to recognise and rewrite
    internal links whatever language prefix they currently carry. `page_codes`
    is the subset that actually has this page translated, and is what the
    hreflang mesh and the og:locale alternates advertise; a newly added page
    starts out English-only, and pointing hreflang at URLs that do not exist
    yet would be worse than not advertising them.
    """
    page_codes = page_codes or codes
    t = source

    t = re.sub(r'<html lang="[^"]*">', f'<html lang="{code}">', t, count=1)

    # Assets, relative to where this page will live. Normalizes whatever form
    # the source happens to use, so re-running the generator is idempotent.
    prefix = "./" if code == "en" else "../"
    # Every reference to a shared directory, wherever it appears: href, src, and
    # each candidate inside a srcset (the first one sits right after the quote,
    # the rest after commas — missing those left the images 404ing on localized
    # pages, which in turn left an empty frame where the screenshot should be).
    t = re.sub(r'(?<=["\s,])(?:\./|/)(assets|locales|pictures)/',
               lambda m: f'{prefix}{m.group(1)}/', t)

    # The legal pages exist only at the site root — they are not translated —
    # so a localized page has to reach up to them.
    for legal in LEGAL:
        t = re.sub(r'href="(?:\.\./|\./|/)?%s"' % re.escape(legal),
                   f'href="{prefix}{legal}"', t)

    # Internal navigation stays inside this language. Any earlier form is
    # matched — bare "/", a language prefix, or a relative path.
    lang_alt = "|".join(codes)
    for other in PAGES:
        target = href_for(code, other, code)
        if other == "index.html":
            t = re.sub(r'href="(?:\.\./|\./|/)?(?:%s)?/?"' % lang_alt,
                       f'href="{target or "./"}"', t)
        t = re.sub(r'href="(?:\.\./|\./|/)?(?:(?:%s)/)?%s"' % (lang_alt, re.escape(other)),
                   f'href="{target}"', t)

    # Canonical + the hreflang set, limited to the languages this page exists in.
    canon = re.search(r' *<link rel="canonical"[^>]*/>\n(?: *<link rel="alternate"[^>]*/>\n)*', t)
    lines = [f'    <link rel="canonical" href="{url_for(code, page)}" />']
    for c in page_codes:
        lines.append(f'    <link rel="alternate" hreflang="{c}" href="{url_for(c, page)}" />')
    lines.append(f'    <link rel="alternate" hreflang="x-default" href="{url_for("en", page)}" />')
    t = t[:canon.start()] + "\n".join(lines) + "\n" + t[canon.end():]

    # Text nodes and aria labels straight from the dictionary.
    def swap_text(m):
        v = dic.get(m.group(1))
        return f'data-i18n="{m.group(1)}">{esc(v)}<' if isinstance(v, str) else m.group(0)
    t = re.sub(r'data-i18n="([^"]+)">([^<]*)<', swap_text, t)

    def swap_aria(m):
        v = dic.get(m.group(2))
        if not isinstance(v, str):
            return m.group(0)
        return m.group(0).replace(f'aria-label="{m.group(1)}"',
                                  'aria-label="%s"' % esc(v).replace('"', "&quot;"), 1)
    t = re.sub(r'aria-label="([^"]*)"[^>]*?data-i18n-aria="([^"]+)"', swap_aria, t)

    # Image alt text. Without this the alt stays English on every localized
    # page — invisible to a sighted visitor, but it is what a crawler and a
    # screen reader read.
    def swap_alt(m):
        v = dic.get(m.group(2))
        if not isinstance(v, str):
            return m.group(0)
        return m.group(0).replace(f'alt="{m.group(1)}"',
                                  'alt="%s"' % esc(v).replace('"', "&quot;"), 1)
    t = re.sub(r'alt="([^"]*)"([^>]*?)data-i18n-alt="([^"]+)"',
               lambda m: swap_alt(re.match(r'alt="([^"]*)".*?data-i18n-alt="([^"]+)"',
                                           m.group(0), re.S)) or m.group(0), t)

    # Head metadata.
    title = dic.get("pageTitle", "")
    # The homepage title already carries the brand; landing pages get it appended
    # only when the result still fits the ~60 characters Google shows. Some
    # translations are long enough that the suffix would just be truncated away,
    # taking part of the actual title with it.
    if page != "index.html" and len(title) + len(" | Voyager Maps") <= 60:
        title = f"{title} | Voyager Maps"
    desc = (dic.get("meta") or {}).get("description") or dic.get("metaDescription", "")
    t = re.sub(r"<title>[^<]*</title>", f"<title>{esc(title)}</title>", t)
    t = re.sub(r'(<meta\s+name="description"\s*\n?\s*content=)"[^"]*"',
               lambda m: f'{m.group(1)}"{esc(desc)}"', t)
    for prop in ("og:description", "twitter:description"):
        t = re.sub(r'(<meta (?:property|name)="%s" content=)"[^"]*"' % prop,
                   lambda m: f'{m.group(1)}"{esc(desc)}"', t)
    for prop in ("og:title", "twitter:title"):
        t = re.sub(r'(<meta (?:property|name)="%s" content=)"[^"]*"' % prop,
                   lambda m: f'{m.group(1)}"{esc(title)}"', t)
    t = re.sub(r'(<meta property="og:url" content=)"[^"]*"',
               lambda m: f'{m.group(1)}"{url_for(code, page)}"', t)
    # Open Graph wants language_TERRITORY, not a bare language code.
    t = re.sub(r'<meta property="og:locale" content="[^"]*" />\n *', "", t)
    t = re.sub(r'<meta property="og:locale:alternate"[^>]*/>\n *', "", t)
    alternates = "".join(f'\n    <meta property="og:locale:alternate" content="{OG_LOCALE[c]}" />'
                         for c in page_codes if c != code)
    t = t.replace('<meta property="og:site_name" content="Voyager Maps" />',
                  '<meta property="og:site_name" content="Voyager Maps" />\n'
                  f'    <meta property="og:locale" content="{OG_LOCALE[code]}" />'
                  + alternates)

    # JSON-LD blocks carry the same language and URL.
    def swap_ld(m):
        try:
            obj = json.loads(m.group(1))
        except ValueError:
            return m.group(0)
        if isinstance(obj, dict):
            obj["inLanguage"] = code
            if "url" in obj:
                obj["url"] = url_for(code, page)
            if obj.get("@type") == "WebPage":
                obj["name"] = title
                obj["description"] = desc
        body = json.dumps(obj, ensure_ascii=False, indent=2).replace("\n", "\n      ")
        return m.group(0).replace(m.group(1), body)
    t = re.sub(r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', swap_ld, t, flags=re.S)

    # Load the register plus this page's own slice of its own language.
    # Replaces whatever locale <script> tags the source page happened to carry.
    #
    # Two cuts, in order. The switcher navigates to the other language's URL
    # rather than swapping text in place, so the other twelve dictionaries were
    # never read — that was the first cut. The remaining file still carried all
    # six landing groups on every page, and the runtime only ever reads one of
    # them: index.js takes the root object and never touches landingPages,
    # landing-pages.js takes landingPages[its own group] and never touches the
    # root. So each page now gets exactly the branch it reads — see
    # page_dictionary(). On /hu/parking-map.html that is 5 KB where the whole
    # file was 53 KB.
    scripts = [f'    <script src="{prefix}assets/languages.js"></script>',
               f'    <script src="{prefix}{locale_asset(code, page)}"></script>']
    block = "\n".join(scripts) + "\n    "
    t = re.sub(r'(?: *<script src="[^"]*(?:languages\.js|locales/(?:pages/)?[a-z]{2}'
               r'(?:\.[a-z0-9-]+)?\.js)"></script>\n)+ *',
               block, t, count=1)
    return t


def city_alternates(cities, rel):
    """Every language this one city page exists in, English first."""
    page = os.path.basename(rel)
    found = [(lang, url) for lang, r, url in cities if os.path.basename(r) == page]
    return sorted(found, key=lambda p: p[0] != "en")


def git_lastmod():
    """The date each tracked file last actually changed, in one pass.

    git log lists commits newest first, so the first time a path appears is
    its most recent change. Filesystem mtimes cannot be used for this: a fresh
    checkout stamps every file with the time of the checkout, which would tell
    a crawler the whole site changed whenever CI ran.
    """
    shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                             cwd=REPO, capture_output=True, text=True).stdout.strip()
    if shallow == "true":
        # Worth saying out loud rather than quietly emitting wrong dates: a
        # shallow clone has one commit, so every file outside it would look
        # like it changed today. CI passes fetch-depth: 0 for this reason.
        print("warning: shallow clone — sitemap dates will be wrong; "
              "fetch the full history (git fetch --unshallow)")
    out = subprocess.run(["git", "log", "--format=%cs", "--name-only"],
                         cwd=REPO, capture_output=True, text=True).stdout
    dates, current = {}, None
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", line):
            current = line
        else:
            dates.setdefault(line, current)
    return dates


def git_dirty():
    """Paths this build (or a hand edit) has changed since the last commit."""
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"],
                         cwd=REPO, capture_output=True, text=True).stdout
    return {line[3:].strip().strip('"') for line in out.splitlines() if line[3:].strip()}


def lastmod_for(rel, dates, dirty, today):
    """A page changed in this run is dated today; otherwise its real date.

    Sending today for everything on every build would be the same wasted
    signal as the fixed constant this replaces — a crawler that is told the
    whole site changed learns nothing about what to recrawl first.
    """
    if rel in dirty:
        return today
    return dates.get(rel, today)


def locale_asset(code, page):
    """Where this page's trimmed dictionary lives, relative to the site root."""
    slug = "index" if page == "index.html" else page[:-len(".html")]
    return f"locales/pages/{code}.{slug}.js"


def page_dictionary(locales, code, page, group):
    """The only branch of the dictionary this page's runtime can reach.

    Shaped so both consumers keep the exact access path they use today:
    index.js reads window.voyagerLocales[code], landing-pages.js reads
    window.voyagerLocales[code].landingPages[its group].

    The hand-edited locales/<code>.js files stay whole — they are the source,
    and routing.html loads two of them directly.
    """
    if group:
        return {"landingPages": {group: locales[code]["landingPages"][group]}}
    return {k: v for k, v in locales[code].items() if k != "landingPages"}


def write_locale_file(rel, code, payload, source):
    dest = os.path.join(REPO, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write("// Generated by tools/build-pages.py — do not edit.\n"
                 "// %s\n"
                 "window.voyagerLocales = window.voyagerLocales || {};\n"
                 "window.voyagerLocales[%s] = %s;\n"
                 % (source, json.dumps(code), body))


def write_page_locale(code, page, payload):
    write_locale_file(locale_asset(code, page), code, payload,
                      f"This page's slice of locales/{code}.js; edit that instead.")


def main():
    languages = load_languages()
    codes = [l["code"] for l in languages]
    locales = load_locales(codes)

    # A page is only generated for the languages that actually translate it, so
    # a newly added page can ship in English and pick up languages as their
    # locale files gain the group — rather than publishing the English copy
    # under every localized URL.
    page_codes = {}
    for page, group in PAGES.items():
        page_codes[page] = [c for c in codes
                            if not group or group in locales[c].get("landingPages", {})]
        missing = [c for c in codes if c not in page_codes[page]]
        if missing:
            print(f"{page}: no translation yet for {', '.join(missing)}")

    # City pages: their own generator, because they share none of the machinery
    # above — one dictionary for all of them rather than a locale group each,
    # and two languages per page rather than thirteen.
    cities = city_pages.build(
        REPO, locales, OG_LOCALE,
        lambda rel, lang, payload: write_locale_file(
            rel, lang, payload,
            "Rendered from data/city-copy/; edit the English source there "
            "and re-run tools/city-copy.py."))
    print(f"{len(cities)} city pages "
          f"({sum(1 for l, _, _ in cities if l == 'en')} cities)")

    written = [rel for _, rel, _ in cities]
    for page in PAGES:
        source = open(os.path.join(REPO, page), encoding="utf-8").read()
        group = PAGES[page]
        for code in page_codes[page]:
            dic = locales[code]
            if group:
                dic = dic["landingPages"][group]
            out = localize(source, code, dic, page, codes, page_codes[page])
            # Matches the marker whether it is still empty or already holds
            # a previous run's list: the generator writes English back over
            # its own source, so a build that only recognised the empty form
            # would leave every other language showing the English one.
            if "data-city-teaser" in out:
                out = re.sub(
                    r'<ul class="city-teaser" data-city-teaser>.*?</ul>',
                    lambda _: '<ul class="city-teaser" data-city-teaser>\n%s\n        </ul>'
                    % city_pages.teaser(REPO, code, cities, locales[code]),
                    out, count=1, flags=re.S)
            dest = os.path.join(REPO, page if code == "en" else os.path.join(code, page))
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            open(dest, "w", encoding="utf-8").write(out)
            written.append(dest.replace(REPO + "/", ""))
            write_page_locale(code, page, page_dictionary(locales, code, page, group))

    # Drop the dictionaries of pages and languages that no longer exist, so a
    # renamed page cannot leave a stale file behind for a crawler to find.
    live = {locale_asset(c, p) for p in PAGES for c in page_codes[p]}
    live |= {locale_asset(lang, os.path.basename(rel)) for lang, rel, _ in cities}
    pages_dir = os.path.join(REPO, "locales", "pages")
    for name in sorted(os.listdir(pages_dir)):
        rel = f"locales/pages/{name}"
        if rel not in live:
            os.remove(os.path.join(REPO, rel))
            print(f"removed stale {rel}")

    # Sitemap: each page in the languages it exists in, with the alternates
    # repeated. lastmod is per URL and truthful — it is the one field here a
    # crawler uses to decide what to fetch again, and a site-wide constant
    # tells it nothing.
    dates, dirty, today = git_lastmod(), git_dirty(), date.today().isoformat()
    rows = []
    for page in PAGES:
        alts = "".join(
            f'\n    <xhtml:link rel="alternate" hreflang="{c}" href="{url_for(c, page)}" />'
            for c in page_codes[page])
        alts += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{url_for("en", page)}" />'
        for code in page_codes[page]:
            rel = page if code == "en" else f"{code}/{page}"
            stamp = lastmod_for(rel, dates, dirty, today)
            rows.append(f"  <url>\n    <loc>{url_for(code, page)}</loc>"
                        f"\n    <lastmod>{stamp}</lastmod>{alts}\n  </url>")
    for lang, rel, canonical in cities:
        alts = "".join(
            f'\n    <xhtml:link rel="alternate" hreflang="{c}" href="{u}" />'
            for c, u in city_alternates(cities, rel))
        alts += ('\n    <xhtml:link rel="alternate" hreflang="x-default" '
                 f'href="{city_alternates(cities, rel)[0][1]}" />')
        stamp = lastmod_for(rel, dates, dirty, today)
        rows.append(f"  <url>\n    <loc>{canonical}</loc>"
                    f"\n    <lastmod>{stamp}</lastmod>{alts}\n  </url>")
    for page in LEGAL:
        stamp = lastmod_for(page, dates, dirty, today)
        rows.append(f"  <url>\n    <loc>{SITE}/{page}</loc>"
                    f"\n    <lastmod>{stamp}</lastmod>\n  </url>")
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
               ' xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
               + "\n".join(rows) + "\n</urlset>\n")
    open(os.path.join(REPO, "sitemap.xml"), "w", encoding="utf-8").write(sitemap)

    print(f"{len(written)} pages, {len(codes)} languages")
    print(f"sitemap: {len(rows)} URLs")


if __name__ == "__main__":
    main()
