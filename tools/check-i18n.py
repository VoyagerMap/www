#!/usr/bin/env python3
"""Catch the translation faults that are not a missing key.

tools/check-keys.py asks whether a key exists; the CI build asks whether the
generated pages match their source. Neither notices a key that is present
everywhere and simply says different things — which is what a half-applied
correction looks like from the outside, and is how most of this site's
translation faults have actually shown up.

Six checks, each one written because it found something real:

  divergence      One English string rendered two ways inside one language.
                  "Public Toilet Map" was two different German headings and
                  "downloads" two different Turkish labels.
  shared-drift    The index copy of a key disagrees with the `shared` block
                  the six landing pages inherit. This is the seventh copy
                  that `shared` cannot deduplicate, so it gets watched.
  dead-override   A landing group restates a value identical to `shared`.
                  Harmless to a reader, but it is a copy that can drift, and
                  deleting it is always right.
  register        Informal and formal address mixed inside one language.
                  Russian shipped "Составь" next to "Составьте" for months.
  seo-length      A meta description or page title past what a search result
                  shows. Translations run 30-50% longer than the English.
  english         A translated value byte-identical to the English source,
                  outside the handful of brand names that stay English.

Usage:  python3 tools/check-i18n.py [--strict] [--only CHECK] [code ...]
        --strict  also fails on warnings, not just errors.
        --only    run one check by name.
"""
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALES = os.path.join(REPO, "locales")
SOURCE = "en"

# Brand and platform names that are the same string in every language.
KEEPS_ENGLISH = {
    "Voyager Maps", "App Store", "Google Play", "Google Maps", "Wi-Fi",
    "OpenStreetMap", "Google Analytics 4", "App Store & Google Play",
    "iOS", "Android", "CSV", "SEO",
}

# Translations that genuinely land on the English wording. Listed one by one
# rather than loosening the check, because "identical to English" is exactly
# what an untranslated string looks like and the difference is a judgement
# only a reader of that language can make.
ALLOWED_IDENTICAL = {
    ("fr", "vsGm5"),            # "Navigation, restaurants, cafés" — all French words
    ("nl", "ctaOpenApp"),       # "Open" is the Dutch imperative too
    ("nl", "openAppAria"),
}

# Search results truncate. Latin scripts get the usual character budget; CJK
# carries far more meaning per character and is cut much earlier.
CJK = {"ja", "ko", "zh"}
LIMITS = {                       # (latin, cjk)
    "description": (160, 80),
    "pageTitle": (60, 36),
}

# Second-person markers. A language belongs here only when the informal and
# formal forms are distinct enough to match without guessing; Turkish
# agglutination and Japanese politeness levels are not, so they are absent
# rather than reported badly.
#
# Patterns are matched on word boundaries built from the language's own
# alphabet, because \b is ASCII-only and would never fire on Cyrillic.
REGISTERS = {
    "de": ("du|dich|dir|dein|deine|deinem|deiner|deines",
           "Ihnen|Ihre|Ihrem|Ihrer|Ihres", "du / Sie"),
    "fr": ("tu|toi|ton|ta|tes", "vous|votre|vos", "tu / vous"),
    "es": ("tú|ti|tuyo|tuya", "usted|ustedes", "tú / usted"),
    "it": ("tu|ti|tuo|tua|tuoi|tue", "Lei|Suo|Sua", "tu / Lei"),
    "pt": ("tu|teu|tua|teus|tuas", "você|vocês", "tu / você"),
    "ru": ("ты|тебя|тебе|твой|твоя|твои|твоё",
           "вы|вас|вам|ваш|ваша|ваши|ваше", "ты / вы"),
    "pl": ("ty|ciebie|tobie|twój|twoja|twoje|cię",
           "Pan|Pani|Państwo|Państwa", "ty / Pan"),
    "nl": ("je|jij|jou|jouw", "uw", "je / u"),
    "id": ("kamu|kau", "Anda", "kamu / Anda"),
}


def load(codes):
    req = ";".join(f"require('{LOCALES}/{c}.js')" for c in codes)
    out = subprocess.run(
        ["node", "-e", f"global.window={{}};{req};"
                       "console.log(JSON.stringify(window.voyagerLocales))"],
        capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def flatten(obj, prefix=""):
    flat = {}
    for key, value in (obj or {}).items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(flatten(value, path))
        elif isinstance(value, str):
            flat[path] = value
    return flat


def words(pattern):
    """Whole-word match that works outside ASCII."""
    return re.compile(rf"(?<![^\W\d_])(?:{pattern})(?![^\W\d_])",
                      re.IGNORECASE | re.UNICODE)


def check_divergence(code, dic, english):
    """One English string that became two in this language."""
    by_source = defaultdict(lambda: defaultdict(list))
    for path, value in dic.items():
        source = english.get(path)
        if not source or len(source) < 8:
            continue
        by_source[source][value].append(path)
    out = []
    for source, variants in by_source.items():
        if len(variants) > 1:
            shown = " | ".join(sorted(variants)[:3])
            where = sorted(p for paths in variants.values() for p in paths)
            out.append((f"{code}: {len(variants)} renderings of \"{source[:60]}\"",
                        f"{shown[:150]}   [{len(where)} keys]"))
    return out


def check_shared_drift(code, raw):
    """The index copy of a shared key disagreeing with the block."""
    shared = raw.get("shared") or {}
    out = []
    for key, value in shared.items():
        index = raw.get(key)
        if isinstance(index, str) and index != value:
            out.append((f"{code}: index and shared disagree on {key}",
                        f"index {index[:60]!r} vs shared {value[:60]!r}"))
    return out


def check_dead_override(code, raw):
    """A landing group restating exactly what it would inherit."""
    shared = raw.get("shared") or {}
    out = []
    for group, page in (raw.get("landingPages") or {}).items():
        for key, value in page.items():
            if isinstance(value, str) and shared.get(key) == value:
                out.append((f"{code}: landingPages.{group}.{key} repeats shared",
                            "delete it — the block already says this"))
    return out


def check_register(code, dic):
    """Informal and formal address inside the same language."""
    if code not in REGISTERS:
        return []
    informal, formal, label = REGISTERS[code]
    text = " ".join(dic.values())
    # A capital at the start of a sentence is not evidence of the formal
    # pronoun, and German "Sie" also means "they".
    casual = words(informal).findall(text)
    polite = words(formal).findall(text)
    if not casual or not polite:
        return []
    minority = min(len(casual), len(polite))
    if minority / (len(casual) + len(polite)) < 0.05:
        return []
    return [(f"{code}: mixed address ({label})",
             f"{len(casual)} informal vs {len(polite)} formal markers")]


def check_seo_length(code, dic):
    out = []
    for path, value in dic.items():
        leaf = path.rsplit(".", 1)[-1]
        if leaf == "description" and "meta" not in path:
            continue
        limits = LIMITS.get(leaf)
        if not limits:
            continue
        cap = limits[1] if code in CJK else limits[0]
        if len(value) > cap:
            out.append((f"{code}: {path} is {len(value)} characters, budget {cap}",
                        value[:80] + "…"))
    return out


def check_english(code, dic, english):
    out = []
    for path, value in dic.items():
        source = english.get(path)
        if source and source == value and len(source) >= 12 \
                and value not in KEEPS_ENGLISH \
                and (code, path) not in ALLOWED_IDENTICAL:
            out.append((f"{code}: {path} is still the English source",
                        value[:80]))
    return out


# All six are clean as of 2026-09-20, so all six block. They were not when
# this tool was written: divergence started at 35 findings and seo-length at
# one, and both reported without failing until the backlog was paid down.
# Keep that pattern for anything added later — a check that fails on the day
# it lands gets switched off, and then it is not a check.
CHECKS = {
    "divergence": "error",
    "shared-drift": "error",
    "dead-override": "error",
    "register": "error",
    "seo-length": "error",
    "english": "error",
}


def main():
    strict = "--strict" in sys.argv
    only = None
    argv = sys.argv[1:]
    if "--only" in argv:
        only = argv[argv.index("--only") + 1]
    codes = [a for a in argv if not a.startswith("--") and a != only]

    available = sorted(f[:-3] for f in os.listdir(LOCALES)
                       if f.endswith(".js") and os.path.isfile(os.path.join(LOCALES, f)))
    codes = codes or available
    raw = load(sorted(set(codes) | {SOURCE}))
    english = flatten({k: v for k, v in raw[SOURCE].items() if k != "shared"})

    findings = defaultdict(list)
    for code in codes:
        source = raw[code]
        dic = flatten({k: v for k, v in source.items() if k != "shared"})
        if only in (None, "divergence"):
            findings["divergence"] += check_divergence(code, dic, english)
        if only in (None, "shared-drift"):
            findings["shared-drift"] += check_shared_drift(code, source)
        if only in (None, "dead-override"):
            findings["dead-override"] += check_dead_override(code, source)
        if only in (None, "register"):
            findings["register"] += check_register(code, dic)
        if only in (None, "seo-length"):
            findings["seo-length"] += check_seo_length(code, dic)
        if only in (None, "english") and code != SOURCE:
            findings["english"] += check_english(code, dic, english)

    failed = 0
    for name, level in CHECKS.items():
        hits = findings.get(name) or []
        if only not in (None, name):
            continue
        tag = "ERROR" if level == "error" or strict else "warn "
        if hits and (level == "error" or strict):
            failed += len(hits)
        print(f"\n{name}: {len(hits)}" + ("" if hits else "  ok"))
        for headline, detail in hits[:15]:
            print(f"  {tag}  {headline}\n         {detail}")
        if len(hits) > 15:
            print(f"  …and {len(hits) - 15} more")

    print(f"\n{len(codes)} languages checked")
    if failed:
        sys.exit(f"{failed} findings at error level")
    print("no blocking i18n findings")


if __name__ == "__main__":
    main()
