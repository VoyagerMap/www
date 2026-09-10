#!/usr/bin/env python3
"""Translate locales/en.js into another language with DeepL.

Reads the English dictionary, sends every string through DeepL in batches and
writes locales/<lang>.js with the same shape. Structural values (language codes)
are carried over untouched, and "Voyager Maps" is protected from translation.

Usage:  python3 tools/translate-locale.py de DE
        (first argument: our locale key, second: the DeepL target code)
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api-free.deepl.com/v2/translate"
BATCH = 45  # DeepL accepts up to 50 text params per request

# Keys whose value is a language code, not prose.
STRUCTURAL_KEYS = {"htmlLang"}
# The brand is substituted out before translation and back in afterwards.
#
# DeepL was trusted to keep it intact on its own, and mostly does — but not in
# a language written in another script. Persian returned "نقشه‌های وویجر" and
# Korean "보이저 맵스" for the product name, 28 and 27 strings each, and Hindi
# and Arabic a few more. A brand rendered phonetically in Devanagari is not the
# brand.
#
# ignore_tags was tried first and is worse: it made DeepL treat the name as a
# foreign quotation and wrap it in the target language's quote marks. A
# numbered brace is the form that survives — the same trick the mobile script
# uses for placeholders, where it also kept the surrounding grammar right.
BRAND = "Voyager Maps"
BRAND_TOKEN = "{0}"


def hide_brand(text):
    """Swap the product name for a token DeepL will carry through untouched."""
    return text.replace(BRAND, BRAND_TOKEN)


def show_brand(text):
    """Put it back. A token DeepL dropped means the name is simply absent,
    which is not worth forcing — the sentence has been rewritten around it."""
    return text.replace(BRAND_TOKEN, BRAND)

# Sent alongside every batch but never translated. Without it "practical places"
# came back as "Praktikumsplätze" (internship positions) in German.
CONTEXT = ("Marketing copy for Voyager Maps, a free mobile app that shows a map "
           "of practical travel locations: public toilets, drinking water taps, "
           "showers, laundromats, Wi-Fi spots, parking and luggage lockers.")

# Short labels carry no sentence around them, so they are the easiest to get
# wrong. These are sent one per request with a context of their own.
LABEL_CONTEXT = {
    "cat1", "cat2", "cat3", "cat4", "cat5", "cat6", "cat7", "cat8", "cat9",
    "vsNeed1", "vsNeed2", "vsNeed3", "vsNeed4", "vsNeed5",
}
LABEL_HINT = ("One category of places shown on a travel map, listed next to "
              "Toilets, Drinking water, Showers and Parking.")

# Languages whose software convention is the formal second person, whatever the
# English source does. Russian is the one that bit us: prefer_less put the whole
# site in ты, which reads as a stranger being over-familiar and disagreed with
# the mobile app, where the same fix is already in scripts/translate_locales.py.
# Keep the two lists in step.
FORMAL_TARGETS = {"RU"}

# Targets DeepL has no formality model for. Sending the parameter anyway is a
# 400 on some of them, so it is left off rather than guessed.
NO_FORMALITY = {"ZH", "UK", "AR", "FA", "TL", "HI", "ID", "KO", "TH", "TR",
                "VI", "DA", "SV", "NB", "IS"}


def formality_for(target):
    """The register to ask DeepL for, or None to leave the choice to it."""
    if target in NO_FORMALITY:
        return None
    return "prefer_more" if target in FORMAL_TARGETS else "prefer_less"


def load_english():
    node = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{REPO}:/w", "-w", "/w", "node:20-alpine",
         "node", "-e",
         "global.window={};require('/w/locales/en.js');"
         "console.log(JSON.stringify(window.voyagerLocales.en))"],
        capture_output=True, text=True, check=True)
    return json.loads(node.stdout.strip().splitlines()[-1])


def walk(node, path=()):
    """Yield (path, value) for every string leaf."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, path + (k,))
    elif isinstance(node, str):
        yield path, node


def translate(texts, target, key, context=CONTEXT):
    out = []
    for start in range(0, len(texts), BATCH):
        chunk = texts[start:start + BATCH]
        params = [("target_lang", target), ("source_lang", "EN"),
                  ("context", context)]
        # The English copy says "you", not "one", so casual is the default —
        # but "you" is not a register, and some languages have to pick one.
        register = formality_for(target)
        if register:
            params.append(("formality", register))
        params += [("text", hide_brand(t)) for t in chunk]
        req = urllib.request.Request(
            API,
            data=urllib.parse.urlencode(params).encode(),
            headers={"Authorization": f"DeepL-Auth-Key {key}"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.load(resp)
        except urllib.error.HTTPError as err:
            # DeepL puts the reason in the body; without it a 400 says nothing.
            sys.exit(f"DeepL {err.code} for {target}: {err.read().decode()[:400]}")
        out += [show_brand(t["text"]) for t in body["translations"]]
        print(f"  {min(start + BATCH, len(texts))}/{len(texts)}", flush=True)
    return out


def set_in(tree, path, value):
    for k in path[:-1]:
        tree = tree[k]
    tree[path[-1]] = value


def render(tree, indent=2):
    """Emit the dictionary as the same JS shape the other locale files use."""
    pad = " " * indent
    lines = []
    for k, v in tree.items():
        if isinstance(v, dict):
            lines.append(f"{pad}{k}: {{")
            lines.append(render(v, indent + 2))
            lines.append(f"{pad}}},")
        else:
            lines.append(f"{pad}{k}: {json.dumps(v, ensure_ascii=False)},")
    return "\n".join(lines).rstrip(",")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    lang, target = sys.argv[1], sys.argv[2]

    key = None
    for line in open(os.path.join(REPO, ".env.local"), encoding="utf-8"):
        if line.startswith("DEEPL_AUTH_KEY="):
            key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit("DEEPL_AUTH_KEY missing from .env.local")

    en = load_english()
    leaves = [(p, v) for p, v in walk(en) if p[-1] not in STRUCTURAL_KEYS]
    print(f"{len(leaves)} strings, {sum(len(v) for _, v in leaves)} characters -> {target}")

    prose = [(p, v) for p, v in leaves if p[-1] not in LABEL_CONTEXT]
    labels = [(p, v) for p, v in leaves if p[-1] in LABEL_CONTEXT]
    done = dict(zip((p for p, _ in prose), translate([v for _, v in prose], target, key)))
    if labels:
        print(f"  {len(labels)} short labels with their own context")
        done.update(zip((p for p, _ in labels),
                        translate([v for _, v in labels], target, key, LABEL_HINT)))
    translated = [done[p] for p, _ in leaves]

    out = json.loads(json.dumps(en))  # deep copy
    for (path, _), value in zip(leaves, translated):
        set_in(out, path, value)
    for path, _ in walk(en):
        if path[-1] in STRUCTURAL_KEYS:
            set_in(out, path, lang)

    dest = os.path.join(REPO, "locales", f"{lang}.js")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write("window.voyagerLocales = window.voyagerLocales || {};\n")
        fh.write(f'window.voyagerLocales["{lang}"] = {{\n')
        fh.write(render(out))
        fh.write("\n};\n")
    print("written:", dest)


if __name__ == "__main__":
    main()
