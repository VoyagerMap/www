#!/usr/bin/env python3
"""Delete the dictionary keys nothing on the site renders any more.

`heroProof`, the whole `why` section, the old hero CTAs — index.html was
rebuilt around install and proof in 6a3c3b1 and the markup for them went with
it, but the strings stayed in all twenty-four locale files. So did four keys
in the landing groups from an earlier preview design. Together that is 1056
strings that no reader has ever seen.

They are not free. They ship: the generated slice a visitor downloads on a
landing page carries about 291 bytes of them. They cost DeepL quota whenever a
language is retranslated, and the quota is spent. Worst of all they cost
review — the September pass read, compared and corrected them across every
language, and two of the divergences it left behind were in strings nothing
renders.

What counts as referenced is decided by tools/check-keys.py, so the tool that
reports dead keys and the tool that removes them can never disagree.

Usage:  python3 tools/prune-locales.py [--dry-run] [code ...]
"""
import importlib.util
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALES = os.path.join(REPO, "locales")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ck = _load("ck", "tools/check-keys.py")
ms = _load("ms", "tools/migrate-shared.py")


def dead_keys():
    """What English defines and nothing references: loose keys, and branches.

    Both come from check-keys.py so the tool that reports and the tool that
    removes can never disagree about what dead means.
    """
    live = ck.referenced()
    en = ck.bp.resolve_shared(ck.load(["en"]))["en"]
    spare = {k for k, v in en.items()
             if isinstance(v, str) and k not in live and k not in ck.BUILD_KEYS}
    for page in (en.get("landingPages") or {}).values():
        spare |= {k for k, v in page.items()
                  if isinstance(v, str) and k not in live and k not in ck.BUILD_KEYS}
    return spare, set(ck.dead_branches(en, live))


def strip(node, names, branches, top=True):
    removed = 0
    for key in list(node):
        value = node[key]
        if top and key in branches:
            removed += sum(1 for v in value.values() if isinstance(v, str))
            del node[key]
        elif isinstance(value, dict):
            removed += strip(value, names, branches, top=False)
        elif key in names:
            del node[key]
            removed += 1
    return removed


def prune(code, names, branches, dry_run=False):
    dic = ms.load(code)
    removed = strip(dic, names, branches)
    if not removed:
        return f"{code}: nothing to remove"
    if not dry_run:
        body = ms.render(dic, 0)
        text = ("window.voyagerLocales = window.voyagerLocales || {};\n"
                f"window.voyagerLocales[{json.dumps(code)}] = {body};\n")
        with open(os.path.join(LOCALES, f"{code}.js"), "w", encoding="utf-8") as fh:
            fh.write(text)
    return f"{code}: {removed} strings removed"


def main():
    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    names, branches = dead_keys()
    if not names and not branches:
        print("nothing is dead")
        return
    if names:
        print(f"{len(names)} dead key names: {', '.join(sorted(names))}")
    if branches:
        print(f"{len(branches)} dead branches: {', '.join(sorted(branches))}")
    print()
    codes = args or sorted(f[:-3] for f in os.listdir(LOCALES)
                           if f.endswith(".js")
                           and os.path.isfile(os.path.join(LOCALES, f)))
    total = 0
    for code in codes:
        line = prune(code, names, branches, dry_run)
        total += int(line.split(":")[1].split()[0]) if "removed" in line else 0
        print(line)
    print(f"\n{total} strings {'would be' if dry_run else ''} removed across {len(codes)} languages")


if __name__ == "__main__":
    main()
