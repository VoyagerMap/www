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

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://getvoyagermaps.com"
LASTMOD = "2026-07-24"

# Root-relative pages, and which locale group each one reads.
PAGES = {
    "index.html": None,
    "drinking-water-map.html": "water",
    "public-toilet-map.html": "toilet",
    "free-shower-map.html": "shower",
    "parking-map.html": "parking",
}
LEGAL = ["privacy-policy.html", "terms.html", "delete-data.html"]
LEGAL_LASTMOD = "2026-05-27"

# Open Graph expects language_TERRITORY. The territory is the market we address
# with that language, not the only place it is spoken.
OG_LOCALE = {
    "en": "en_US", "de": "de_DE", "fr": "fr_FR", "es": "es_ES", "it": "it_IT",
    "pt": "pt_BR", "nl": "nl_NL", "pl": "pl_PL", "hu": "hu_HU", "ja": "ja_JP",
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


def localize(source, code, dic, page, codes):
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

    # Canonical + the full hreflang set.
    canon = re.search(r' *<link rel="canonical"[^>]*/>\n(?: *<link rel="alternate"[^>]*/>\n)*', t)
    block = hreflang_block(page, codes) % code if "%s" in hreflang_block(page, codes) else None
    lines = [f'    <link rel="canonical" href="{url_for(code, page)}" />']
    for c in codes:
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
                         for c in codes if c != code)
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

    # Load the register plus every locale so the switcher can render all
    # languages and navigate between them. Replaces whatever locale <script>
    # tags the source page happened to carry.
    scripts = [f'    <script src="{prefix}assets/languages.js"></script>']
    scripts += [f'    <script src="{prefix}locales/{c}.js"></script>' for c in codes]
    block = "\n".join(scripts) + "\n    "
    t = re.sub(r'(?: *<script src="[^"]*(?:languages|locales/[a-z]{2})\.js"></script>\n)+ *',
               block, t, count=1)
    return t


def main():
    languages = load_languages()
    codes = [l["code"] for l in languages]
    locales = load_locales(codes)

    written = []
    for page in PAGES:
        source = open(os.path.join(REPO, page), encoding="utf-8").read()
        group = PAGES[page]
        for code in codes:
            dic = locales[code]
            if group:
                dic = dic["landingPages"][group]
            out = localize(source, code, dic, page, codes)
            dest = os.path.join(REPO, page if code == "en" else os.path.join(code, page))
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            open(dest, "w", encoding="utf-8").write(out)
            written.append(dest.replace(REPO + "/", ""))

    # Sitemap: every page in every language, with the alternates repeated.
    rows = []
    for page in PAGES:
        alts = "".join(
            f'\n    <xhtml:link rel="alternate" hreflang="{c}" href="{url_for(c, page)}" />'
            for c in codes)
        alts += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{url_for("en", page)}" />'
        for code in codes:
            rows.append(f"  <url>\n    <loc>{url_for(code, page)}</loc>"
                        f"\n    <lastmod>{LASTMOD}</lastmod>{alts}\n  </url>")
    for page in LEGAL:
        rows.append(f"  <url>\n    <loc>{SITE}/{page}</loc>"
                    f"\n    <lastmod>{LEGAL_LASTMOD}</lastmod>\n  </url>")
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
               ' xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
               + "\n".join(rows) + "\n</urlset>\n")
    open(os.path.join(REPO, "sitemap.xml"), "w", encoding="utf-8").write(sitemap)

    print(f"{len(written)} pages, {len(codes)} languages")
    print(f"sitemap: {len(codes) * len(PAGES) + len(LEGAL)} URLs")


if __name__ == "__main__":
    main()
