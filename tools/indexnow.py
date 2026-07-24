#!/usr/bin/env python3
"""Tell IndexNow-participating search engines (Bing, Yandex, Seznam) what changed.

Google does not take part — it still needs Search Console. The value here is
speed on Bing, which also backs ChatGPT's search, and it costs one request.

Reads the URLs straight from sitemap.xml so the two can never disagree. The key
file has to be reachable at the site root before submitting, otherwise the
submission is rejected as unverified.

Usage:  python3 tools/indexnow.py            # everything in the sitemap
        python3 tools/indexnow.py /parking-map.html /de/   # just these
"""
import glob
import json
import os
import sys
import urllib.request
from xml.dom import minidom

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://getvoyagermaps.com"
ENDPOINT = "https://api.indexnow.org/IndexNow"


def find_key():
    """The key is the name of the .txt file at the repo root holding it."""
    for path in glob.glob(os.path.join(REPO, "*.txt")):
        name = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as fh:
            if fh.read().strip() == name:
                return name
    sys.exit("No IndexNow key file found at the repo root")


def sitemap_urls():
    doc = minidom.parse(os.path.join(REPO, "sitemap.xml"))
    return [n.firstChild.data for n in doc.getElementsByTagName("loc")]


def main():
    key = find_key()
    urls = [SITE + a if a.startswith("/") else a for a in sys.argv[1:]] or sitemap_urls()

    payload = {
        "host": SITE.split("//")[1],
        "key": key,
        "keyLocation": f"{SITE}/{key}.txt",
        "urlList": urls,
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    print(f"submitting {len(urls)} URLs with key {key}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            print(f"HTTP {response.status} — accepted")
    except urllib.error.HTTPError as err:
        # 422 usually means the key file could not be read from the site root.
        print(f"HTTP {err.code}: {err.read().decode()[:300]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
