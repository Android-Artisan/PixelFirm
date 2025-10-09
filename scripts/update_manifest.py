#!/usr/bin/env python3

import json
import re
from pathlib import Path
import sys
from typing import Dict

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

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


def scrape_developers_playwright(timeout: int = 30000) -> Dict[str, dict]:
    """Use Playwright to navigate developers.google.com and visit per-device pages to find dl.google .zip links.

    This is a best-effort fallback when the AOSP index isn't available.
    """
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
        page = browser.new_page()

        # capture responses and search for .zip urls in responses
        def on_response(response):
            try:
                r_url = response.url
                if r_url.endswith('.zip'):
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
        page.goto(URL, timeout=timeout)
        page.wait_for_load_state("networkidle", timeout=timeout)

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

        # visit discovered device pages (bounded)
        for dp in list(device_pages)[:300]:
            try:
                page.goto(dp, timeout=timeout)
                page.wait_for_load_state("networkidle", timeout=timeout)
            except Exception:
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
    try:
        data = scrape()
        manifest_path.write_text(json.dumps(data, indent=2))
        print(f"Updated manifest with {len(data)} entries")
    except Exception as e:
        print("Failed to update manifest:", e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
