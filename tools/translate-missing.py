#!/usr/bin/env python3
"""Add only the keys missing from a locale, translated with DeepL.

Unlike translate-locale.py (which re-translates the whole dictionary), this
diffs locales/en.js against locales/<lang>.js, sends only the strings that the
target is missing, and writes them back — leaving every existing translation
untouched. Used to bring older locales up to date with new keys (e.g. two new
landing-page groups) without re-spending quota or churning good translations.

Usage:  python3 tools/translate-missing.py de DE
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "tl", os.path.join(os.path.dirname(os.path.abspath(__file__)), "translate-locale.py"))
tl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tl)

REPO = tl.REPO


def load_locale(code):
    node = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{REPO}:/w", "-w", "/w", "node:20-alpine",
         "node", "-e",
         f"global.window={{}};require('/w/locales/{code}.js');"
         f"console.log(JSON.stringify(window.voyagerLocales['{code}']||window.voyagerLocales.{code}))"],
        capture_output=True, text=True, check=True)
    return json.loads(node.stdout.strip().splitlines()[-1])


def has_path(tree, path):
    for k in path:
        if not isinstance(tree, dict) or k not in tree:
            return False
        tree = tree[k]
    return True


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

    en = tl.load_english()
    cur = load_locale(lang)

    missing = [(p, v) for p, v in tl.walk(en)
               if p[-1] not in tl.STRUCTURAL_KEYS and not has_path(cur, p)]
    if not missing:
        print(f"{lang}: nothing missing")
        return
    print(f"{lang}: {len(missing)} missing strings, "
          f"{sum(len(v) for _, v in missing)} chars -> {target}")

    prose = [(p, v) for p, v in missing if p[-1] not in tl.LABEL_CONTEXT]
    labels = [(p, v) for p, v in missing if p[-1] in tl.LABEL_CONTEXT]
    done = dict(zip((p for p, _ in prose),
                    tl.translate([v for _, v in prose], target, key)))
    if labels:
        done.update(zip((p for p, _ in labels),
                        tl.translate([v for _, v in labels], target, key, tl.LABEL_HINT)))

    # Ensure parent dicts exist, then set each missing leaf.
    for path, _ in missing:
        node = cur
        for k in path[:-1]:
            node = node.setdefault(k, {})
        node[path[-1]] = done[path]

    dest = os.path.join(REPO, "locales", f"{lang}.js")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write("window.voyagerLocales = window.voyagerLocales || {};\n")
        fh.write(f'window.voyagerLocales["{lang}"] = {{\n')
        fh.write(tl.render(cur))
        fh.write("\n};\n")
    print("written:", dest)


if __name__ == "__main__":
    main()
