from __future__ import annotations
import json
from pathlib import Path
import requests
from tqdm import tqdm

LOCAL_MANIFEST = Path(__file__).parent / "manifest.json"
REMOTE_MANIFEST = "https://raw.githubusercontent.com/YOUR_GITHUB_USER/pixelfirm/main/pixelfirm/manifest.json"

def load_manifest(timeout: int = 30):
    # Try online manifest first
    try:
        r = requests.get(REMOTE_MANIFEST, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        # fallback to local
        if LOCAL_MANIFEST.exists():
            return json.loads(LOCAL_MANIFEST.read_text())
        raise RuntimeError("Failed to fetch manifest online and no local copy found.")

def download_url(url: str, dest: Path, resume: bool = True, timeout: int = 30):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(dest.suffix + ".part")
    headers = {"User-Agent": "pixelfirm/1.0"}
    mode = "wb"
    existing = temp.stat().st_size if temp.exists() else 0
    if resume and existing > 0:
        headers["Range"] = f"bytes={existing}-"
        mode = "ab"
    with requests.get(url, headers=headers, stream=True, timeout=timeout) as r:
        if r.status_code == 416:
            temp.rename(dest)
            return dest
        r.raise_for_status()
        total = None
        if "Content-Length" in r.headers:
            try:
                total = int(r.headers["Content-Length"]) + (existing if "Range" in headers else 0)
            except Exception:
                total = None
        pbar = tqdm(total=total, unit="B", unit_scale=True, unit_divisor=1024, initial=existing, desc=dest.name)
        try:
            with open(temp, mode) as f:
                for chunk in r.iter_content(chunk_size=128*1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    pbar.update(len(chunk))
        finally:
            pbar.close()
    temp.rename(dest)
    return dest

def search_latest_and_download(codename: str, out_dir: Path, resume: bool = True, timeout: int = 30) -> Path:
    manifest = load_manifest(timeout=timeout)
    if codename not in manifest:
        raise ValueError(f"No entry for codename {codename} in manifest.")
    entry = manifest[codename]
    url = entry["url"]
    filename = url.split("/")[-1]
    dest = Path(out_dir) / filename
    print("Selected:", filename)
    print("Downloading from:", url)
    return download_url(url, dest, resume=resume, timeout=timeout)
