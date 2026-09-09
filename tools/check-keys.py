#!/usr/bin/env python3
"""Fail when a page asks for a string its language does not have.

The generator resolves every data-i18n key with dic.get(), so a key missing
from one locale is not an error there — the English source text simply stays
in the localized page. Nothing shows up in the build log and nothing looks
broken; a Hungarian visitor just reads a line of English. That is the failure
this guards, and it is the one that actually reaches a reader.

It also flags keys defined in a locale that no page uses any more, which is
how locales/en.js ended up carrying a dead `heroProof` for months.

Usage:  python3 tools/check-keys.py [--strict]
        --strict also fails on unused keys, not just missing ones.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_spec = importlib.util.spec_from_file_location(
    "bp", os.path.join(REPO, "tools", "build-pages.py"))
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)

# Read by the generator itself rather than rendered from a key.
BUILD_KEYS = {"htmlLang", "pageTitle", "metaDescription", "meta", "landingPages"}
ATTR = re.compile(r'data-i18n(?:-aria|-alt)?="([^"]+)"')
# The consent panel, install bar and "why" modal are built in JS, which names
# its keys as plain property access or string literals. Scanning the markup
# alone reports all of them as dead, so the scripts count as usage too.
RUNTIME = re.compile(r'[."\'\[]([a-z][A-Za-z0-9]{3,})')


def runtime_keys():
    found = set()
    for name in sorted(os.listdir(os.path.join(REPO, "assets"))):
        if name.endswith(".js"):
            src = open(os.path.join(REPO, "assets", name), encoding="utf-8").read()
            found |= set(RUNTIME.findall(src))
    return found


def load(codes):
    """Read the locale files with the host's node — no container needed."""
    req = ";".join(f"require('{REPO}/locales/{c}.js')" for c in codes)
    out = subprocess.run(
        ["node", "-e", f"global.window={{}};{req};"
                       "console.log(JSON.stringify(window.voyagerLocales))"],
        capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    strict = "--strict" in sys.argv
    languages = bp.load_languages()
    codes = [l["code"] for l in languages]
    locales = load(codes)

    from_js = runtime_keys()
    missing, unused = [], []
    for page, group in bp.PAGES.items():
        used = set(ATTR.findall(
            open(os.path.join(REPO, page), encoding="utf-8").read()))
        for code in codes:
            dic = locales[code]
            if group:
                if group not in dic.get("landingPages", {}):
                    continue          # page not translated yet: build skips it
                dic = dic["landingPages"][group]
            gone = sorted(k for k in used if not isinstance(dic.get(k), str))
            if gone:
                missing.append(f"{page} [{code}]: {', '.join(gone)}")
        # Unused is a property of the dictionary, not of any one language, so
        # it is only worth asking of the source locale.
        if group is None:
            spare = sorted(k for k, v in locales["en"].items()
                           if isinstance(v, str) and k not in used
                           and k not in BUILD_KEYS and k not in from_js)
            if spare:
                unused.append(f"{page}: {', '.join(spare)}")

    # The key existing is not the same as the page showing it. Every
    # "Privacy Policy" link on the site stayed English in all thirteen
    # languages because the substitution pattern required data-i18n to be the
    # last attribute on its tag and those links carry data-track after it —
    # no error, no missing key, just English text under a localized URL. This
    # compares what was generated against what the dictionary says it is.
    stale = []
    for page, group in bp.PAGES.items():
        for code in codes:
            rel = page if code == "en" else os.path.join(code, page)
            path = os.path.join(REPO, rel)
            if not os.path.exists(path):
                continue
            dic = locales[code]
            if group:
                dic = dic.get("landingPages", {}).get(group)
                if not dic:
                    continue
            html = open(path, encoding="utf-8").read()
            for key, _attrs, shown in re.findall(
                    r'data-i18n="([^"]+)"([^>]*)>([^<]*)<', html):
                want = dic.get(key)
                if isinstance(want, str) and shown != bp.esc(want):
                    stale.append(f"{rel}: {key} shows {shown!r}, "
                                 f"dictionary says {want!r}")

    for line in missing:
        print(f"MISSING  {line}")
    for line in stale[:20]:
        print(f"STALE    {line}")
    if len(stale) > 20:
        print(f"STALE    …and {len(stale) - 20} more")
    for line in unused:
        print(f"unused   {line}")

    print(f"\n{len(bp.PAGES)} pages x {len(codes)} languages checked")
    if missing:
        sys.exit(f"{len(missing)} page/language pairs would fall back to English")
    if stale:
        sys.exit(f"{len(stale)} rendered strings do not match their dictionary")
    if unused and strict:
        sys.exit(f"{len(unused)} pages carry keys nothing renders")
    print("every key a page renders exists in every language")


if __name__ == "__main__":
    main()
