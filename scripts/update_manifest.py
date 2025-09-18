#!/usr/bin/env python3
import json, re, requests
from pathlib import Path
from bs4 import BeautifulSoup

URL = "https://dl.google.com/dl/android/aosp/"
manifest_path = Path(__file__).resolve().parent.parent / "pixelfirm" / "manifest.json"

def scrape():
    r = requests.get(URL)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    data = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.endswith(".zip") and "-factory-" in href:
            # Ensure we have a full URL
            if not href.startswith("http"):
                href = URL + href
            fname = href.split("/")[-1]
            codename = fname.split("-")[0]
            # Try to extract build id
            m = re.search(r"-([a-z0-9.]+)-factory", fname)
            version = m.group(1) if m else "unknown"
            data[codename] = {
                "url": href,
                "version": version
            }
    return data

def main():
    data = scrape()
    manifest_path.write_text(json.dumps(data, indent=2))
    print(f"Updated manifest with {len(data)} entries")

if __name__ == "__main__":
    main()
