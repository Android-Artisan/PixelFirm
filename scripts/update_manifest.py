#!/usr/bin/env python3

import argparse
import json
import logging
import re
import time
from pathlib import Path
import sys
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup

# Playwright is optional at import time; import lazily where used

URL = "https://developers.google.com/android/images"
manifest_path = Path(__file__).resolve().parent.parent / "pixelfirm" / "manifest.json"


def scrape_aosp_index() -> Dict[str, dict]:
    """Try to parse the AOSP index at dl.google.com for .zip factory images."""
    base = "https://dl.google.com/dl/android/aosp/"
    try:
        r = requests.get(base, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        entries = {}
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.endswith(".zip"):
                continue
            url = href if href.startswith("http") else base + href
            fname = url.split("/")[-1]
            if "-factory-" not in fname:
                continue
            codename = fname.split("-")[0]
            m = re.search(r"-([a-z0-9.]+)-factory", fname)
            version = m.group(1) if m else "unknown"
            entries[codename] = {"url": url, "version": version}
        return entries
    except Exception:
        return {}


def scrape_developers_playwright(timeout: int = 15000, max_pages: int = 200, snapshot_dir: Optional[Path] = None) -> Dict[str, dict]:
    """Use Playwright to navigate developers.google.com and visit per-device pages to find dl.google .zip links.

    This is a best-effort fallback when the AOSP index isn't available.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        logging.warning("Playwright not available: %s", e)
        return {}

    collected = {}
    found_urls = set()

    def try_add_url(url: str):
        if not url:
            return
        if not url.startswith("http"):
            return
        if not url.lower().endswith(".zip"):
            return
        fname = url.split("/")[-1]
        if "-factory-" not in fname:
            return
        codename = fname.split("-")[0]
        m = re.search(r"-([a-z0-9.]+)-factory", fname)
        version = m.group(1) if m else "unknown"
        collected[codename] = {"url": url, "version": version}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # capture responses and search for .zip urls in responses
        def on_response(response):
            try:
                r_url = response.url
                if r_url and r_url.lower().endswith('.zip'):
                    found_urls.add(r_url)
                    return
                ct = response.headers.get('content-type', '')
                if 'json' in ct or 'text' in ct or 'html' in ct:
                    try:
                        body = response.text()
                    except Exception:
                        return
                    for m in re.finditer(r'https?://[^"\'\s]+\.zip', body):
                        found_urls.add(m.group(0))
            except Exception:
                return

        page.on("response", on_response)

        try:
            page.goto(URL, timeout=timeout)
        except Exception:
            logging.debug("Failed to open main developers page")

        # short pause to let client-side scripts run
        page.wait_for_timeout(1500)

        # find candidate links to follow (device pages or sections)
        anchors = page.query_selector_all("a[href]")
        device_pages = set()
        for a in anchors:
            href = a.get_attribute("href")
            if not href:
                continue
            if href.startswith("/android/images") or href.startswith(URL):
                if href.startswith("/"):
                    device_pages.add("https://developers.google.com" + href)
                else:
                    device_pages.add(href)

        # visit discovered device pages (bounded by max_pages)
        count = 0
        for dp in list(device_pages):
            if count >= max_pages:
                break
            count += 1
            try:
                page.goto(dp, timeout=timeout)
                page.wait_for_timeout(800)

                # Scroll the page to trigger lazy loading
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(400)
                except Exception:
                    pass

                # Try clicking elements that likely reveal downloads
                try:
                    # click any element with text matching 'factory' or 'download'
                    loc = page.locator("text=/factory/i")
                    n = loc.count()
                    for i in range(n):
                        try:
                            loc.nth(i).click(timeout=1000)
                            page.wait_for_timeout(200)
                        except Exception:
                            continue
                except Exception:
                    pass

                try:
                    loc2 = page.locator("text=/download/i")
                    n2 = loc2.count()
                    for i in range(n2):
                        try:
                            loc2.nth(i).click(timeout=1000)
                            page.wait_for_timeout(200)
                        except Exception:
                            continue
                except Exception:
                    pass

                # optionally save a snapshot for debugging
                if snapshot_dir:
                    try:
                        snapshot_dir.mkdir(parents=True, exist_ok=True)
                        name = re.sub(r'[^a-z0-9.-]+', '_', dp)
                        (snapshot_dir / f"{name}.html").write_text(page.content())
                    except Exception:
                        pass
            except Exception:
                logging.debug("Failed to open device page %s", dp)
                continue

        # also search the main page html for urls
        try:
            html = page.content()
            for m in re.finditer(r'https?://[^"\'\s]+\.zip', html):
                found_urls.add(m.group(0))
        except Exception:
            pass

        # post-process found urls
        for u in sorted(found_urls):
            try_add_url(u)

        browser.close()
    return collected


def scrape() -> Dict[str, dict]:
    # 1) try the AOSP index
    by_aosp = scrape_aosp_index()
    if by_aosp:
        return by_aosp
    # 2) fallback to developers pages using Playwright
    by_dev = scrape_developers_playwright()
    if by_dev:
        return by_dev
    # 3) nothing found
    return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=15_000, help="Playwright timeout per page (ms)")
    parser.add_argument("--max-pages", type=int, default=200, help="Maximum number of device pages to visit")
    parser.add_argument("--snapshot-dir", type=Path, help="Directory to store HTML snapshots for debugging")
    parser.add_argument("--dry-run", action="store_true", help="Don't write manifest, just print summary")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s")

    try:
        logging.info("Starting manifest scrape")
        data = scrape()
        logging.info("Scrape found %d entries", len(data))

        if args.dry_run:
            print(json.dumps(data, indent=2))
            return

        # don't overwrite with empty results; preserve existing
        if not data:
            logging.warning("No entries found; existing manifest will be preserved")
            return

        # backup existing manifest
        if manifest_path.exists():
            bak = manifest_path.with_suffix(f".bak.{int(time.time())}")
            manifest_path.replace(bak)
            logging.info("Backed up existing manifest to %s", bak)

        manifest_path.write_text(json.dumps(data, indent=2))
        logging.info("Updated manifest with %d entries", len(data))
    except Exception as e:
        logging.exception("Failed to update manifest: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
