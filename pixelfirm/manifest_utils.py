import json
import re
import time
from pathlib import Path
from typing import Optional, Tuple

import requests


REMOTE_MANIFEST = "https://raw.githubusercontent.com/Android-Artisan/PixelFirm/main/pixelfirm/manifest.json"


def parse_factory_filename(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse a factory filename URL into (codename, version).

    Returns (None, None) if parsing fails.
    """
    if not url:
        return None, None
    fname = url.split("/")[-1]
    m = re.search(r"^(?P<codename>[a-z0-9]+)-(?P<version>[a-z0-9.]+)-factory", fname)
    if not m:
        return None, None
    return m.group("codename"), m.group("version")


def verify_url_head(url: str, timeout: int = 10) -> dict:
    """Perform a HEAD request to verify the URL; return metadata dictionary.

    Keys: status, content_type, size, ok
    """
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True)
        status = int(getattr(r, "status_code", 0))
        ct = r.headers.get("content-type", "") if r.headers else ""
        cl = r.headers.get("content-length") if r.headers else None
        size = int(cl) if cl and cl.isdigit() else None
        ok = 200 <= status < 400 and ("zip" in ct or size is not None)
        return {"status": status, "content_type": ct, "size": size, "ok": ok}
    except Exception:
        return {"status": 0, "content_type": "", "size": None, "ok": False}


def update_manifest_with_entry(url: str, verify: bool = True) -> dict:
    """Add or update the manifest with a factory URL.

    This function now fetches the remote manifest directly and updates it.
    """
    codename, version = parse_factory_filename(url)
    if not codename:
        raise ValueError("Could not parse codename from url")

    meta = {"url": url, "version": version or "unknown"}

    if verify:
        v = verify_url_head(url)
        meta.update({"size": v.get("size"), "verified": bool(v.get("ok", False))})
    else:
        meta.update({"size": None, "verified": False})

    # Fetch the remote manifest
    try:
        r = requests.get(REMOTE_MANIFEST, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch remote manifest: {e}")

    # Update the manifest
    data[codename] = meta
    return meta
