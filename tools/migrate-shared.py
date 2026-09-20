#!/usr/bin/env python3
"""Hoist the strings every landing group repeats into one `shared` block.

A landing page carries about seventy strings, and forty-four of them are
identical on all six pages: the store badge lines, the consent notice, the
language switcher, the explore links, the footer. Held per group that is six
copies of one sentence per language — 5280 redundant strings across the site,
and the reason a correction applied to five of six was the most common way a
translation went half-done.

This rewrites locales/<code>.js once: the repeated strings move to a `shared`
block, the groups keep only what is genuinely theirs. tools/build-pages.py
folds the block back in at build time, so the generated slices under
locales/pages/ do not change and neither does anything the browser loads.

A group that needs its own wording keeps the key and still wins.

Usage:  python3 tools/migrate-shared.py [--dry-run] [code ...]
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALES = os.path.join(REPO, "locales")

# Identifiers JavaScript lets us write bare. Anything else gets quoted, which
# is how the file is written today for keys like "meta".
import re
BARE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def load(code):
    """The locale as the browser sees it, key order intact."""
    expr = (f"global.window={{}};require('{LOCALES}/{code}.js');"
            f"console.log(JSON.stringify(window.voyagerLocales[{json.dumps(code)}]))")
    out = subprocess.run(["node", "-e", expr], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def render(value, indent):
    """Emit a value the way the locale files are already written."""
    pad = "  " * indent
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = []
        for key, inner in value.items():
            name = key if BARE.match(key) else json.dumps(key)
            lines.append(f"{pad}  {name}: {render(inner, indent + 1)}")
        return "{\n" + ",\n".join(lines) + f"\n{pad}}}"
    return json.dumps(value, ensure_ascii=False)


def shared_keys(groups):
    """Keys present in every group with one value shared by all of them."""
    if len(groups) < 2:
        return []
    names = None
    for page in groups.values():
        here = {k for k, v in page.items() if isinstance(v, str)}
        names = here if names is None else (names & here)
    keep = []
    for key in names:
        values = {page[key] for page in groups.values()}
        if len(values) == 1:
            keep.append(key)
    # Follow the first group's order so the block reads like the page does.
    first = next(iter(groups.values()))
    return [k for k in first if k in keep]


def migrate(code, dry_run=False):
    """Re-runnable: an existing block is dissolved and recomputed.

    Worth running again after a divergence is settled. Once the six groups
    finally agree on a string, that string becomes hoistable — Hungarian's
    previewOverlay stayed per-group only because two pages worded it
    differently.
    """
    dic = load(code)
    groups = dic.get("landingPages") or {}
    was = dic.pop("shared", None)
    if was:
        for page in groups.values():
            for key, value in was.items():
                page.setdefault(key, value)
    keys = shared_keys(groups)
    if not keys:
        return f"{code}: nothing shared by all {len(groups)} groups"
    if was:
        # Keep the block's existing order so re-running only ever appends.
        # Otherwise every generated slice churns for no change in content.
        keys = ([k for k in was if k in keys]
                + [k for k in keys if k not in was])

    sample = next(iter(groups.values()))
    shared = {k: sample[k] for k in keys}
    for page in groups.values():
        for key in keys:
            del page[key]

    # `shared` sits directly before the groups it feeds.
    rebuilt = {}
    for key, value in dic.items():
        if key == "landingPages":
            rebuilt["shared"] = shared
        rebuilt[key] = value

    body = render(rebuilt, 0)
    text = ("window.voyagerLocales = window.voyagerLocales || {};\n"
            f"window.voyagerLocales[{json.dumps(code)}] = {body};\n")
    saved = len(keys) * (len(groups) - 1)
    if not dry_run:
        with open(os.path.join(LOCALES, f"{code}.js"), "w", encoding="utf-8") as fh:
            fh.write(text)
    return f"{code}: {len(keys)} keys shared across {len(groups)} groups, {saved} copies removed"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv
    codes = args or sorted(f[:-3] for f in os.listdir(LOCALES)
                           if f.endswith(".js") and os.path.isfile(os.path.join(LOCALES, f)))
    for code in codes:
        print(migrate(code, dry_run))


if __name__ == "__main__":
    main()
