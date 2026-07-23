#!/usr/bin/env python3
"""Round-trip check for a machine-translated locale.

Translates the locale back into English and reports the strings that drifted
furthest from the original. Without native speakers this is the practical way to
catch the severe mistranslations — German "practical places" came back as
"internship positions", which a back-translation shows immediately. Word-order
noise is expected; what matters is a line whose meaning changed.

Usage:  python3 tools/check-locale.py de DE [how many to show]
"""
import difflib
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api-free.deepl.com/v2/translate"
BATCH = 45
# Short labels and prose that sells the product: worth eyeballing regardless of
# how similar the back-translation looks.
ALWAYS_SHOW = ["pageTitle", "heroTitle", "heroLead", "heroProof", "vsTitle"]


def load(lang):
    node = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{REPO}:/w", "-w", "/w", "node:20-alpine",
         "node", "-e",
         f"global.window={{}};require('/w/locales/{lang}.js');"
         f"console.log(JSON.stringify(window.voyagerLocales.{lang}))"],
        capture_output=True, text=True, check=True)
    return json.loads(node.stdout.strip().splitlines()[-1])


def walk(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, path + (k,))
    elif isinstance(node, str):
        yield path, node


def translate(texts, source, key):
    out = []
    for start in range(0, len(texts), BATCH):
        chunk = texts[start:start + BATCH]
        params = [("target_lang", "EN-GB"), ("source_lang", source)]
        params += [("text", t) for t in chunk]
        req = urllib.request.Request(
            API, data=urllib.parse.urlencode(params).encode(),
            headers={"Authorization": f"DeepL-Auth-Key {key}"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            out += [t["text"] for t in json.load(resp)["translations"]]
    return out


def main():
    lang = sys.argv[1]
    source = sys.argv[2]
    top = int(sys.argv[3]) if len(sys.argv) > 3 else 12

    key = next(l.split("=", 1)[1].strip()
               for l in open(os.path.join(REPO, ".env.local"), encoding="utf-8")
               if l.startswith("DEEPL_AUTH_KEY="))

    en, tr = load("en"), load(lang)
    pairs = [(p, v, dict(walk(tr)).get(p)) for p, v in walk(en)]
    pairs = [(p, a, b) for p, a, b in pairs if b and p[-1] != "htmlLang"]

    back = translate([b for _, _, b in pairs], source, key)
    scored = sorted(
        ((difflib.SequenceMatcher(None, a.lower(), c.lower()).ratio(), p, a, c)
         for (p, a, _), c in zip(pairs, back)),
        key=lambda r: r[0])

    print(f"\n=== {lang}: {top} most divergent strings (1.00 = identical) ===")
    for ratio, path, original, roundtrip in scored[:top]:
        print(f"\n[{ratio:.2f}] {'.'.join(path)}")
        print(f"  EN in  : {original}")
        print(f"  EN back: {roundtrip}")

    print(f"\n=== key marketing lines ===")
    for ratio, path, original, roundtrip in scored:
        if path[-1] in ALWAYS_SHOW and len(path) == 1:
            print(f"\n[{ratio:.2f}] {path[-1]}")
            print(f"  EN in  : {original}")
            print(f"  EN back: {roundtrip}")


if __name__ == "__main__":
    main()
