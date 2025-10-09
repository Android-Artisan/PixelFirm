import json
import re
import time
from pathlib import Path
from typing import Optional, Tuple

import requests


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


def update_manifest_with_entry(url: str, manifest_path: Path = Path("pixelfirm/manifest.json"), verify: bool = True) -> dict:
    """Add or update the manifest with a factory URL.

    Returns the entry written to the manifest.
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

    # load existing manifest
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if manifest_path.exists():
        try:
            text = manifest_path.read_text()
            data = json.loads(text) if text.strip() else {}
        except Exception:
            data = {}

    # backup
    if manifest_path.exists():
        bak = manifest_path.with_suffix(f".bak.{int(time.time())}")
        manifest_path.replace(bak)

    data[codename] = meta
    manifest_path.write_text(json.dumps(data, indent=2))
    return meta
