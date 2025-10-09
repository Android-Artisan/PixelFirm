#!/usr/bin/env python3

import argparse
import json
import logging
import re
import time
from pathlib import Path
import sys
from typing import Dict, Optional
import os

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


def try_additional_indexes() -> Dict[str, dict]:
    urls = os.environ.get("PIXELFIRM_INDEX_URLS")
    if not urls:
        return {}
    entries = {}
    for u in urls.split(','):
        u = u.strip()
        if not u:
            continue
        try:
            r = requests.get(u, timeout=30)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not href.endswith(".zip"):
                    continue
                url = href if href.startswith("http") else u.rstrip("/") + "/" + href.lstrip("/")
                fname = url.split("/")[-1]
                if "-factory-" not in fname:
                    continue
                codename = fname.split("-")[0]
                m = re.search(r"-([a-z0-9.]+)-factory", fname)
                version = m.group(1) if m else "unknown"
                entries[codename] = {"url": url, "version": version}
        except Exception:
            continue
    return entries


def scrape_developers_playwright(timeout: int = 15000, max_pages: int = 200, snapshot_dir: Optional[Path] = None, headful: bool = False) -> Dict[str, dict]:
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
    responses = []
    console_messages = []

    def try_add_url(url: str, verify: bool = True):
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
        entry = {"url": url, "version": version}
        if verify:
            try:
                r = requests.head(url, timeout=10, allow_redirects=True)
                r.raise_for_status()
                ct = r.headers.get("content-type", "")
                cl = r.headers.get("content-length")
                size = int(cl) if cl and cl.isdigit() else None
                if "zip" in ct or "application" in ct or size:
                    entry["size"] = size
                    entry["verified"] = True
                else:
                    logging.debug("URL %s fails content-type check: %s", url, ct)
                    return
            except Exception as e:
                logging.debug("HEAD request failed for %s: %s", url, e)
                return
        else:
            entry["verified"] = False

        collected[codename] = entry

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headful)
        context = browser.new_context()
        page = context.new_page()

        def _handle_page_capture(payload):
            try:
                import json as _json
                obj = None
                if isinstance(payload, str):
                    try:
                        obj = _json.loads(payload)
                    except Exception:
                        obj = {"text": payload}
                else:
                    obj = payload
                url = obj.get("url") if isinstance(obj, dict) else None
                status = obj.get("status") if isinstance(obj, dict) else None
                text = obj.get("text") if isinstance(obj, dict) else None
                meta = {"url": url, "status": status, "from_page_capture": True}
                if text:
                    meta["body_snippet"] = (text or "")[:4096]
                responses.append(meta)

                if snapshot_dir and text:
                    try:
                        resp_dir = snapshot_dir / "responses"
                        resp_dir.mkdir(parents=True, exist_ok=True)
                        safe_name = re.sub(r"[^a-z0-9._-]+", "_", (url or "page_capture"))
                        idx = len(responses)
                        fname = resp_dir / f"pwcap_{idx}_{safe_name}.txt"
                        fname.write_text(text, encoding='utf-8', errors='replace')
                    except Exception:
                        pass
            except Exception:
                return

        try:
            page.expose_function("__pw_capture", _handle_page_capture)
            js_hook = r"""
            (() => {
              try {
                const origFetch = window.fetch;
                window.fetch = async function(...args) {
                  const resp = await origFetch.apply(this, args);
                  try {
                    const clone = resp.clone();
                    const text = await clone.text().catch(() => null);
                    if (window.__pw_capture) {
                      try { window.__pw_capture(JSON.stringify({url: resp.url, status: resp.status, text: text})); } catch(e) {}
                    }
                  } catch(e) {}
                  return resp;
                };
              } catch(e) {}
              try {
                const origOpen = XMLHttpRequest.prototype.open;
                const origSend = XMLHttpRequest.prototype.send;
                XMLHttpRequest.prototype.open = function(method, url) { this._pxf_url = url; return origOpen.apply(this, arguments); };
                XMLHttpRequest.prototype.send = function(body) {
                  this.addEventListener('load', function(){
                    try {
                      var txt = null;
                      try { txt = this.responseText; } catch(e) {}
                      if (window.__pw_capture) {
                        try { window.__pw_capture(JSON.stringify({url: this._pxf_url, status: this.status, text: txt})); } catch(e) {}
                      }
                    } catch(e) {}
                  });
                  return origSend.apply(this, arguments);
                };
              } catch(e) {}
            })();
            """
            page.add_init_script(js_hook)
        except Exception:
            pass

        def on_response(response):
            try:
                r_url = response.url
                if r_url and r_url.lower().endswith('.zip'):
                    found_urls.add(r_url)
                    return
                ct = response.headers.get('content-type', '')
                meta = {'url': r_url, 'status': None, 'content-type': ct}
                try:
                    meta['status'] = response.status
                except Exception:
                    pass

                if any(k in ct for k in ('json', 'text', 'html', 'javascript')):
                    try:
                        body = response.text()
                        meta['body_snippet'] = body[:4096]
                        responses.append(meta)
                        if snapshot_dir:
                            try:
                                resp_dir = snapshot_dir / 'responses'
                                resp_dir.mkdir(parents=True, exist_ok=True)
                                safe_name = re.sub(r'[^a-z0-9._-]+', '_', r_url)
                                fname = resp_dir / f"{len(responses)}_{safe_name}.txt"
                                fname.write_text(body, encoding='utf-8', errors='replace')
                            except Exception:
                                pass

                        for m in re.finditer(r'https?://[^"\'"\s]+\.zip', body):
                            found_urls.add(m.group(0))
                        for m in re.finditer(r'dl\.google\.com[^"\'"\s]+', body):
                            val = m.group(0)
                            if val.startswith('http'):
                                found_urls.add(val)
                            else:
                                found_urls.add('https://' + val)

                        try:
                            parsed = None
                            import json as _json
                            parsed = _json.loads(body)

                            def scan_obj(o):
                                if isinstance(o, str):
                                    if '.zip' in o.lower() or 'dl.google' in o.lower():
                                        if o.startswith('http'):
                                            found_urls.add(o)
                                        else:
                                            if o.startswith('//'):
                                                found_urls.add('https:' + o)
                                            elif o.startswith('/'):
                                                found_urls.add('https://developers.google.com' + o)
                                            else:
                                                if 'dl.google' in o:
                                                    if o.startswith('http'):
                                                        found_urls.add(o)
                                                    else:
                                                        found_urls.add('https://' + o)
                                elif isinstance(o, dict):
                                    for v in o.values():
                                        scan_obj(v)
                                elif isinstance(o, list):
                                    for v in o:
                                        scan_obj(v)

                            if parsed is not None:
                                scan_obj(parsed)
                        except Exception:
                            pass
                    except Exception:
                        return
            except Exception:
                return

        page.on('response', on_response)

        def on_console(msg):
            try:
                text = msg.text()
            except Exception:
                text = str(msg)
            console_messages.append(text)

        page.on('console', on_console)

        try:
            page.goto(URL, timeout=timeout)
            try:
                page.wait_for_load_state('networkidle', timeout=min(timeout, 10000))
            except Exception:
                page.wait_for_timeout(2000)
        except Exception:
            logging.debug('Failed to open main developers page')

        if snapshot_dir:
            try:
                snapshot_dir.mkdir(parents=True, exist_ok=True)
                (snapshot_dir / 'main_page.html').write_text(page.content())
            except Exception:
                pass

        anchors = page.query_selector_all('a[href]')
        device_pages = set()
        for a in anchors:
            href = a.get_attribute('href')
            if not href:
                continue
            if href.startswith('/android/images') or href.startswith(URL):
                if href.startswith('/'):
                    device_pages.add('https://developers.google.com' + href)
                else:
                    device_pages.add(href)

        count = 0
        for dp in list(device_pages):
            if count >= max_pages:
                break
            count += 1
            try:
                page.goto(dp, timeout=timeout)
                try:
                    page.wait_for_load_state('networkidle', timeout=min(timeout, 8000))
                except Exception:
                    page.wait_for_timeout(1000)

                try:
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    page.wait_for_timeout(400)
                except Exception:
                    pass

                try:
                    loc = page.locator('text=/factory/i')
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
                    onclicks = page.query_selector_all('[onclick]')
                    for el in onclicks:
                        try:
                            val = el.get_attribute('onclick') or ''
                            if '.zip' in val or 'download' in val.lower():
                                try:
                                    el.scroll_into_view_if_needed()
                                except Exception:
                                    pass
                                try:
                                    el.click(timeout=1000)
                                    page.wait_for_timeout(200)
                                except Exception:
                                    continue
                        except Exception:
                            continue
                except Exception:
                    pass

                try:
                    loc2 = page.locator('text=/download/i')
                    n2 = loc2.count()
                    for i in range(n2):
                        try:
                            loc2.nth(i).click(timeout=1000)
                            page.wait_for_timeout(200)
                        except Exception:
                            continue
                except Exception:
                    pass

                if snapshot_dir:
                    try:
                        snapshot_dir.mkdir(parents=True, exist_ok=True)
                        name = re.sub(r'[^a-z0-9.-]+', '_', dp)
                        (snapshot_dir / f"{name}.html").write_text(page.content())
                    except Exception:
                        pass

                try:
                    anchors = page.query_selector_all('a[href]')
                    for a in anchors:
                        try:
                            h = a.get_attribute('href')
                            if h and h.lower().endswith('.zip'):
                                if h.startswith('//'):
                                    found_urls.add('https:' + h)
                                elif h.startswith('/'):
                                    found_urls.add('https://developers.google.com' + h)
                                else:
                                    found_urls.add(h)
                        except Exception:
                            continue

                    elems = page.query_selector_all('[data-download],[data-url],[data-href]')
                    for e in elems:
                        try:
                            for attr in ('data-download','data-url','data-href'):
                                v = e.get_attribute(attr)
                                if v and ('.zip' in v or 'dl.google' in v):
                                    if v.startswith('//'):
                                        found_urls.add('https:' + v)
                                    elif v.startswith('/'):
                                        found_urls.add('https://developers.google.com' + v)
                                    else:
                                        found_urls.add(v)
                        except Exception:
                            continue

                    try:
                        js_snippet = (
                            '() => { '
                            'const out = []; '
                            'try { Array.from(document.querySelectorAll("a")).slice(0,200).forEach(a => { if (a.href) out.push(a.href); }); } catch(e) {} '
                            'try { const els = Array.from(document.querySelectorAll("[data-download],[data-url],[data-href]")); els.forEach(el => { ["data-download","data-url","data-href"].forEach(k => { if (el.getAttribute(k)) out.push(el.getAttribute(k)); }); }); } catch(e) {} '
                            'return out.slice(0,500); '
                            '}'
                        )
                        snippets = page.evaluate(js_snippet)
                        for s in (snippets or []):
                            if not s:
                                continue
                            if isinstance(s, str) and ('.zip' in s.lower() or 'dl.google' in s.lower()):
                                if s.startswith('//'):
                                    found_urls.add('https:' + s)
                                elif s.startswith('/'):
                                    found_urls.add('https://developers.google.com' + s)
                                else:
                                    found_urls.add(s)
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                logging.debug('Failed to open device page %s', dp)
                continue

        try:
            html = page.content()
            for m in re.finditer(r'https?://[^"\'"\s]+\.zip', html):
                found_urls.add(m.group(0))
        except Exception:
            pass

        try:
            js_text = page.evaluate("() => JSON.stringify(Object.keys(window).slice(0,200))")
            if js_text:
                all_text = page.evaluate("() => { try { return JSON.stringify(window) } catch(e) { return '' } }")
                for m in re.finditer(r'https?://[^"\'"\s]+\.zip', all_text or ''):
                    found_urls.add(m.group(0))
                for m in re.finditer(r'dl\.google\.com[^"\'"\s]+', all_text or ''):
                    val = m.group(0)
                    if val.startswith('http'):
                        found_urls.add(val)
                    else:
                        found_urls.add('https://' + val)
        except Exception:
            pass

        for u in sorted(found_urls):
            try_add_url(u)

        if snapshot_dir:
            try:
                snapshot_dir.mkdir(parents=True, exist_ok=True)
                if responses:
                    (snapshot_dir / 'responses_summary.json').write_text(json.dumps(responses, indent=2), encoding='utf-8')
                if console_messages:
                    (snapshot_dir / 'console.log').write_text('\n'.join(console_messages), encoding='utf-8')
            except Exception:
                pass

        browser.close()
    return collected


def scrape(verify: bool = True, timeout: int = 15000, max_pages: int = 200, snapshot_dir: Optional[Path] = None, headful: bool = False) -> Dict[str, dict]:
    # 1) try the AOSP index (no verify here)
    by_aosp = scrape_aosp_index()
    if by_aosp:
        return by_aosp
    # 2) fallback to developers pages using Playwright
    by_dev = scrape_developers_playwright(timeout=timeout, max_pages=max_pages, snapshot_dir=snapshot_dir, headful=headful)
    if by_dev:
        # when using dev scraping, optionally verify the discovered urls
        if verify:
            verified = {}
            for k, v in by_dev.items():
                url = v.get('url')
                try:
                    r = requests.head(url, timeout=10, allow_redirects=True)
                    r.raise_for_status()
                    ct = r.headers.get('content-type', '')
                    cl = r.headers.get('content-length')
                    size = int(cl) if cl and cl.isdigit() else None
                    v['size'] = size
                    v['verified'] = True
                    verified[k] = v
                except Exception:
                    continue
            return verified
        return by_dev
    # 3) nothing found
    return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=15_000, help="Playwright timeout per page (ms)")
    parser.add_argument("--max-pages", type=int, default=200, help="Maximum number of device pages to visit")
    parser.add_argument("--snapshot-dir", type=Path, help="Directory to store HTML snapshots for debugging")
    parser.add_argument("--headful", action="store_true", help="Run Playwright in headful mode (visible browser)")
    parser.add_argument("--no-verify", action="store_true", help="Do not verify discovered URLs with HEAD")
    parser.add_argument("--dry-run", action="store_true", help="Don't write manifest, just print summary")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s")

    try:
        logging.info("Starting manifest scrape")
        data = scrape(verify=not args.no_verify, timeout=args.timeout, max_pages=args.max_pages, snapshot_dir=args.snapshot_dir, headful=args.headful)
        logging.info("Scrape found %d entries", len(data))

        if args.dry_run:
            print(json.dumps(data, indent=2))
            return

        # if we found nothing, try fallback manifest URL from env
        if not data:
            fb = os.environ.get("PIXELFIRM_FALLBACK_MANIFEST_URL")
            if fb:
                logging.info("Attempting to fetch fallback manifest from %s", fb)
                try:
                    r = requests.get(fb, timeout=30)
                    r.raise_for_status()
                    remote = r.json()
                    if isinstance(remote, dict) and remote:
                        data = remote
                        logging.info("Loaded %d entries from fallback manifest", len(data))
                except Exception as e:
                    logging.warning("Failed to load fallback manifest: %s", e)

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
