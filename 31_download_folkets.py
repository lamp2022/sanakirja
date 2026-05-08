#!/usr/bin/env python3
"""
31_download_folkets.py

Download Folkets lexikon (KTH) EN↔SV XML files to ../sanakirja/.
These are public-domain bilingual Swedish dictionaries.

Run: python3 31_download_folkets.py
Idempotent — skips download if file already exists and size matches.
"""

import os
import sys
import time

import requests

SOURCES_DIR = "../sanakirja"

URLS = {
    "folkets_en_sv.xml": "https://folkets-lexikon.csc.kth.se/folkets/folkets_en_sv_public.xml",
    "folkets_sv_en.xml": "https://folkets-lexikon.csc.kth.se/folkets/folkets_sv_en_public.xml",
}

HEADERS = {"User-Agent": "sanakirja-builder/1.0 (https://github.com/lamp2022/sanakirja)"}


def download(url: str, dest: str) -> bool:
    """Download url to dest. Returns True if downloaded, False if skipped."""
    if os.path.exists(dest):
        print(f"  Already exists: {dest} ({os.path.getsize(dest):,} bytes) — skipping")
        return False

    print(f"  Downloading {url}")
    tmp = dest + ".tmp"
    try:
        r = requests.get(url, headers=HEADERS, stream=True, timeout=60)
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        written = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
                written += len(chunk)
                if total:
                    pct = written / total * 100
                    print(f"\r    {written:,}/{total:,} bytes ({pct:.0f}%)", end="", flush=True)
        print(f"\r    Done: {written:,} bytes                    ")
        os.replace(tmp, dest)
        return True
    except Exception as e:
        if os.path.exists(tmp):
            os.unlink(tmp)
        print(f"\n  ERROR: {e}")
        return False


def main():
    os.makedirs(SOURCES_DIR, exist_ok=True)
    ok = True
    for filename, url in URLS.items():
        dest = os.path.join(SOURCES_DIR, filename)
        print(f"\n{filename}:")
        result = download(url, dest)
        if result is False and not os.path.exists(dest):
            ok = False

    if ok:
        print("\nDone. Both Folkets lexikon files ready.")
    else:
        print("\nERROR: one or more downloads failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
