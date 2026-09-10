#!/usr/bin/env python3
"""Render the city-page copy, then translate it into each city's own language.

Nothing reaches DeepL with a placeholder still in it. That is the whole design,
and it is not a stylistic preference: sending "Public toilets in {city}" to
Hungarian returns "Nyilvános WC-k és ivóviz{city}ban", because the case ending
has to attach to the name and there is no name to attach it to. Sent as
"Public toilets in Budapest" the same request returns "Nyilvános WC-k és ivóvíz
Budapesten", correctly inflected — and "w Warszawie" for Polish, "東京の" for
Japanese. So the counts and the name are substituted first and the finished
sentence is translated.

Each city is translated only into its own country's language, which is what
keeps this affordable: 34 city/language pairs rather than 50 x 11.

Copy that never names a city (category labels, the data note) is translated
once per language into _shared.<lang>.json.

Usage:  python3 tools/city-copy.py             # fill in whatever is missing
        python3 tools/city-copy.py --force     # redo everything
        python3 tools/city-copy.py --dry-run   # render English, translate nothing
"""
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "city-copy")
API = "https://api-free.deepl.com/v2/translate"
BATCH = 40

TARGETS = {"de": "DE", "fr": "FR", "it": "IT", "es": "ES", "pt": "PT-BR",
           "nl": "NL", "pl": "PL", "hu": "HU", "ja": "JA", "ko": "KO", "zh": "ZH",
           "hi": "HI", "ru": "RU",
           "ar": "AR", "id": "ID", "vi": "VI", "tr": "TR", "fa": "FA",
           "fil": "TL", "da": "DA", "sv": "SV", "nb": "NB", "is": "IS"}
                          # hi and ru are here for the all-cities hub only: no
                          # city page is in either — the dataset has no Indian
                          # or Russian city — but the hub is in every language

CONTEXT = (
    "Copy for a page of Voyager Maps, a free travel app showing practical "
    "places on a map: public toilets, drinking water taps, showers, "
    "launderettes, parking and pharmacies. The page reports how many of each "
    "the app has mapped in one named city. Keep city names and figures as they "
    "are; 'Voyager Maps' is a product name.")

ALL_LANGS = list(TARGETS)          # every site language except English
PLACEHOLDER = re.compile(r"\{(\w+)\}")
# The four candidate sentences highlight() chooses between. Only the chosen
# one is rendered, under the key "highlight"; none ship as themselves.
VARIANTS = {"highlightWater", "highlightToilets", "highlightFree",
            "highlightAccess"}


def auth_key():
    for line in open(os.path.join(REPO, ".env.local"), encoding="utf-8"):
        if line.startswith("DEEPL_AUTH_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("DEEPL_AUTH_KEY missing from .env.local")


def deepl(texts, target, key):
    out = []
    for start in range(0, len(texts), BATCH):
        chunk = texts[start:start + BATCH]
        params = [("target_lang", target), ("source_lang", "EN"),
                  ("formality", "prefer_less"), ("context", CONTEXT)]
        params += [("text", t) for t in chunk]
        req = urllib.request.Request(
            API, data=urllib.parse.urlencode(params).encode(),
            headers={"Authorization": f"DeepL-Auth-Key {key}"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    out += [t["text"] for t in json.load(resp)["translations"]]
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 456) and attempt < 3:
                    time.sleep(6 * (attempt + 1))
                    continue
                sys.exit(f"DeepL {e.code}: {e.read().decode()[:300]}")
    return out


def highlight(row, src):
    """The one sentence that is only true of this city.

    Picked from the numbers rather than written, so every page says something
    the others do not — Rome's fountains outnumber its toilets eight to one,
    Fukuoka's toilets outnumber its taps nine to one. Ratios are only used when
    they are lopsided enough to be worth remarking on.
    """
    t, w = row["toilets"], row["water"]
    if w >= t * 2:
        return src["highlightWater"], {"ratio": round(w / t, 1)}
    if t >= w * 2:
        return src["highlightToilets"], {"ratio": round(t / max(w, 1), 1)}
    if row["step_free"] >= row["total"] * 0.15:
        return src["highlightAccess"], {}
    return src["highlightFree"], {}


def render(row, src, today):
    """Every string, with the name, the counts and the date filled in."""
    n = lambda v: f"{v:,}"
    values = {
        "city": row["name_en"], "date": today,
        "total": n(row["total"]), "toilets": n(row["toilets"]),
        "water": n(row["water"]), "showers": n(row["showers"]),
        "laundry": n(row["laundry"]), "parking": n(row["parking"]),
        "pharmacy": n(row["pharmacy"]), "wifi": n(row["wifi"]),
        "step_free": n(row["step_free"]), "free": n(row["free_of_charge"]),
        "hours": n(row["with_hours"]),
    }
    text, extra = highlight(row, src)
    values.update({k: n(v) if isinstance(v, int) else v for k, v in extra.items()})

    out = {}
    for key, value in src.items():
        if key.startswith("_") or key in VARIANTS:
            continue
        out[key] = PLACEHOLDER.sub(lambda m: str(values.get(m.group(1), m.group(0))), value)
    out["highlight"] = PLACEHOLDER.sub(
        lambda m: str(values.get(m.group(1), m.group(0))), text)
    left = {k: v for k, v in out.items() if PLACEHOLDER.search(v)}
    if left:
        sys.exit(f"unfilled placeholder in {row['slug']}: {left}")
    return out


def load_rows():
    path = os.path.join(REPO, "data", "cities.csv")
    rows = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["published"] != "yes":
            continue
        for k, v in r.items():
            if v.isdigit():
                r[k] = int(v)
        rows.append(r)
    return rows


def write(path, payload, note):
    payload = dict(payload, _note=note)
    json.dump(payload, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


def main():
    force = "--force" in sys.argv
    dry = "--dry-run" in sys.argv
    src = json.load(open(os.path.join(REPO, "data", "city-page.en.json"),
                         encoding="utf-8"))
    today = date.today().isoformat()
    rows = load_rows()
    os.makedirs(OUT, exist_ok=True)

    city_keys = [k for k, v in src.items()
                 if not k.startswith("_") and "{city}" in v
                 and k not in VARIANTS] + ["highlight"]
    shared_keys = [k for k, v in src.items()
                   if not k.startswith("_") and "{city}" not in v
                   and k not in VARIANTS]

    # English: rendered straight from the source, no translation involved.
    for row in rows:
        full = render(row, src, today)
        write(os.path.join(OUT, f"{row['slug']}.en.json"),
              {k: full[k] for k in city_keys},
              "Rendered by tools/city-copy.py from city-page.en.json.")
    shared_en = render(rows[0], src, today)
    write(os.path.join(OUT, "_shared.en.json"),
          {k: shared_en[k] for k in shared_keys},
          "Rendered by tools/city-copy.py; contains no city-specific text.")
    print(f"English: {len(rows)} cities + shared")
    if dry:
        return

    key = auth_key()
    langs = sorted({r["lang"] for r in rows if r["lang"]})

    # The all-cities index at /cities.html exists in every language the site
    # has, unlike the city pages — it is a directory, not a page about one
    # place, so a Korean reader has a reason to see it.
    hub_src = json.load(open(os.path.join(REPO, "data", "cities-page.en.json"),
                             encoding="utf-8"))
    hub_keys = [k for k in hub_src if not k.startswith("_")]
    write(os.path.join(OUT, "_hub.en.json"), {k: hub_src[k] for k in hub_keys},
          "Copied from data/cities-page.en.json.")
    for lang in ALL_LANGS:
        path = os.path.join(OUT, f"_hub.{lang}.json")
        if os.path.exists(path) and not force:
            continue
        print(f"  hub -> {TARGETS[lang]}")
        got = deepl([hub_src[k] for k in hub_keys], TARGETS[lang], key)
        write(path, dict(zip(hub_keys, got)),
              f"DeepL {TARGETS[lang]} of cities-page.en.json.")

    for lang in langs:
        path = os.path.join(OUT, f"_shared.{lang}.json")
        if os.path.exists(path) and not force:
            continue
        print(f"  shared -> {TARGETS[lang]}")
        got = deepl([shared_en[k] for k in shared_keys], TARGETS[lang], key)
        write(path, dict(zip(shared_keys, got)),
              f"DeepL {TARGETS[lang]} of _shared.en.json. Re-run "
              f"tools/city-copy.py --force after editing the English.")

    todo = [r for r in rows if r["lang"] and (force or not os.path.exists(
        os.path.join(OUT, f"{r['slug']}.{r['lang']}.json")))]
    for i, row in enumerate(todo, 1):
        full = render(row, src, today)
        texts = [full[k] for k in city_keys]
        print(f"  [{i}/{len(todo)}] {row['name_en']} -> {TARGETS[row['lang']]}")
        got = deepl(texts, TARGETS[row["lang"]], key)
        write(os.path.join(OUT, f"{row['slug']}.{row['lang']}.json"),
              dict(zip(city_keys, got)),
              f"DeepL {TARGETS[row['lang']]} of {row['slug']}.en.json.")

    print(f"done: {len(rows)} English, {len(langs)} shared, {len(todo)} city translations")


if __name__ == "__main__":
    main()
