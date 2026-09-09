#!/usr/bin/env python3
"""Count what Voyager Maps knows about each curated city, into data/cities.csv.

Two things this has to get right, both learned from the data rather than
assumed:

Names. OSM tags the city in its local form and does not agree with itself
about granularity. Prague is spread over `Praha` and `Praha 1`-`Praha 22` in
mixed case; New York City is `New York` plus its boroughs; Tokyo has no city
entry at all, only its 23 special wards. So each city carries an explicit list
of the names that are it, curated in data/cities.json, and `北区` — a ward name
Tokyo shares with Osaka and Kyoto — is disambiguated by state_region.

Categories. Drinking water is not one type: drinking_fountain, water_tap,
spring, water_point and drinking_water are five, and counting only the last
undercounts a city's taps by roughly an order of magnitude.

Usage:  python3 tools/city-stats.py            # writes data/cities.csv
        python3 tools/city-stats.py --check    # print, write nothing
"""
import csv
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CITIES = os.path.join(REPO, "data", "cities.json")
OUT = os.path.join(REPO, "data", "cities.csv")
CONTAINER = "api-postgres-1"

# poi_types.id groups. Water is deliberately all five of its types.
TYPES = {
    "toilets": [7],
    "water": [2, 3, 4, 5, 6],
    "showers": [8],
    "laundry": [9],
    "parking": [91],
    "pharmacy": [15],
}
LIVE = "('operational','temporarily_closed')"


def sql(query):
    out = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "supertokens",
         "-d", "voyager", "-A", "-F", "\t", "-t", "-c", query],
        capture_output=True, text=True)
    if out.returncode:
        sys.exit(f"psql failed:\n{out.stderr.strip()}")
    return [l.split("\t") for l in out.stdout.strip().splitlines() if l.strip()]


def q(s):
    return "'" + s.replace("'", "''") + "'"


def build_query(cities):
    """One pass over poi, with the curated names joined in as a VALUES list."""
    rows = []
    for slug, c in cities.items():
        for name in c["cities"]:
            region = q(c["state_region"]) if c.get("state_region") else "NULL"
            rows.append(f"({q(slug)},{q(c['country'])},{q(name)},{region})")
    counts = ",\n  ".join(
        f"count(*) FILTER (WHERE p.type_id IN ({','.join(map(str, ids))})) AS {key}"
        for key, ids in TYPES.items())
    return f"""
WITH m(slug, country, city, region) AS (VALUES
  {','.join(rows)}
)
SELECT m.slug,
  count(*) AS total,
  {counts},
  count(*) FILTER (WHERE p.internet_access IN ('yes','Customers')) AS wifi,
  count(*) FILTER (WHERE p.wheelchair = 'yes') AS step_free,
  count(*) FILTER (WHERE p.fee = 'no') AS free_of_charge,
  count(*) FILTER (WHERE p.open_hours IS NOT NULL AND p.open_hours <> '') AS with_hours
FROM poi p
JOIN m ON p.country = m.country AND p.city = m.city
      AND (m.region IS NULL OR p.state_region = m.region)
WHERE p.status IN {LIVE}
GROUP BY m.slug
"""


# A city earns a page when both hold. The page's whole claim is that these
# counts are worth quoting, so the bar is about substance, not popularity:
# below roughly this much the headline number reads as a rounding error and
# the categories below it are mostly empty rows. Cities that miss are left in
# the CSV with published=no — the data is still true, it is just too thin to
# build a page on, and several are famous places whose OSM coverage will
# improve (Venice at 1,482 total, Florence at 74 toilets, Prague at 3).
MIN_TOTAL, MIN_TOILETS = 2000, 150

FIELDS = ["slug", "name_en", "name_local", "country", "lang", "total"] \
    + list(TYPES) + ["wifi", "step_free", "free_of_charge", "with_hours",
                     "published"]


def main():
    cities = json.load(open(CITIES, encoding="utf-8"))
    measured = {r[0]: [int(v) for v in r[1:]] for r in sql(build_query(cities))}

    rows = []
    for slug, c in cities.items():
        got = measured.get(slug)
        if not got:
            print(f"  no rows at all: {slug} ({c['country']})")
            continue
        row = dict(zip(FIELDS, [slug, c["en"], c["local"], c["country"],
                                c["lang"] or ""] + got))
        row["published"] = ("yes" if row["total"] >= MIN_TOTAL
                            and row["toilets"] >= MIN_TOILETS else "no")
        rows.append(row)
    rows.sort(key=lambda r: -r["total"])

    if "--check" in sys.argv:
        print(f"{'city':22} {'total':>7} {'toilets':>8} {'water':>7} {'wifi':>7} {'lang':>5}")
        for r in rows:
            print(f"{r['name_en'][:22]:22} {r['total']:7} {r['toilets']:8} "
                  f"{r['water']:7} {r['wifi']:7} {r['lang'] or '-':>5}")
        return

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    live = sum(1 for r in rows if r["published"] == "yes")
    print(f"{len(rows)} cities measured, {live} published "
          f"-> {os.path.relpath(OUT, REPO)}")


if __name__ == "__main__":
    main()
