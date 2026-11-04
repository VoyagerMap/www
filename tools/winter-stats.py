#!/usr/bin/env python3
"""Count the motorhome services of each winter destination, into data/winter.csv.

One row per region and one per country (region left empty), for the pages
built by tools/winter_pages.py. The counts follow what the app shows, not what
OSM could be read to mean:

  dump      a dump station of its own (sanitary_dump_station) or any other
            place tagged as having one, for everyone or for customers — the
            app's dump station filter brings both
  lpg       fuel stations recorded as selling LPG, or only LPG
  water     all five drinking water types, as on the city pages
  sites     caravan sites (aires, Stellplätze, camperplaatsen)
  campsites camp sites
  showers, laundry

Region names come from poi.state_region, which spells some regions both with
and without accents (Setúbal and Setubal). Spellings that differ only in
accents are one region, named by whichever spelling holds more places.

Usage:  python3 tools/winter-stats.py            # writes data/winter.csv
        python3 tools/winter-stats.py --check    # print, write nothing
"""
import csv
import os
import subprocess
import sys
import unicodedata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "winter.csv")
CONTAINER = "api-postgres-1"
COUNTRIES = ["ES", "PT"]
LIVE = "('operational','temporarily_closed')"
FIELDS = ["dump", "lpg", "water", "sites", "campsites", "showers", "laundry"]

QUERY = f"""
select country, coalesce(state_region, ''),
  count(*) filter (where type_id = 132
                   or sanitary_dump_station in ('yes', 'customers')),
  count(*) filter (where type_id = 65 and fuel_lpg in ('yes', 'only')),
  count(*) filter (where type_id in (2, 3, 4, 5, 6)),
  count(*) filter (where type_id = 14),
  count(*) filter (where type_id = 13),
  count(*) filter (where type_id = 8),
  count(*) filter (where type_id = 9)
from poi
where status in {LIVE}
  and country in ({",".join(f"'{c}'" for c in COUNTRIES)})
group by 1, 2
"""


def sql(query):
    out = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "supertokens",
         "-d", "voyager", "-A", "-F", "\t", "-t", "-c", query],
        capture_output=True, text=True)
    if out.returncode:
        sys.exit(f"psql failed:\n{out.stderr.strip()}")
    return [l.split("\t") for l in out.stdout.strip().splitlines() if l.strip()]


def fold(name):
    """The accent-free, case-free form two spellings of a region share."""
    return "".join(c for c in unicodedata.normalize("NFD", name.strip())
                   if not unicodedata.combining(c)).casefold()


def main():
    groups = {}
    for country, region, *counts in sql(QUERY):
        counts = [int(c) for c in counts]
        key = (country, fold(region))
        spellings, total = groups.setdefault(key, ({}, [0] * len(FIELDS)))
        spellings[region.strip()] = spellings.get(region.strip(), 0) + sum(counts)
        for i, c in enumerate(counts):
            total[i] += c

    rows = []
    for country in COUNTRIES:
        whole = [0] * len(FIELDS)
        regions = []
        for (c, folded), (spellings, counts) in groups.items():
            if c != country:
                continue
            whole = [a + b for a, b in zip(whole, counts)]
            name = max(spellings, key=spellings.get)
            # A place with no region still counts for the country, but an
            # unnamed row in the region table would tell a reader nothing.
            if folded and (counts[0] or counts[1] or counts[3]):
                regions.append([country, name] + counts)
        rows.append([country, ""] + whole)
        rows += sorted(regions, key=lambda r: (-r[2], -r[5], r[1]))

    if "--check" in sys.argv:
        for r in rows:
            print("\t".join(str(v) for v in r))
        return
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["country", "region"] + FIELDS)
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {os.path.relpath(OUT, REPO)}")


if __name__ == "__main__":
    main()
