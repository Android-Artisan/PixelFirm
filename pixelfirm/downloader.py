from __future__ import annotations
import json
from pathlib import Path
import sys
import requests
try:
    from rich.progress import Progress, BarColumn, DownloadColumn, TextColumn, TimeRemainingColumn, TransferSpeedColumn
    _HAS_RICH = True
except Exception:
    from tqdm import tqdm
    _HAS_RICH = False

REMOTE_MANIFEST = "https://raw.githubusercontent.com/Android-Artisan/PixelFirm/main/pixelfirm/manifest.json"


def load_manifest(timeout: int = 30):
    """Always fetch the remote manifest and return its parsed JSON.

    This intentionally does NOT prefer or fall back to a local manifest file.
    If the remote fetch fails or the JSON is invalid, a RuntimeError is raised.
    """
    try:
        r = requests.get(REMOTE_MANIFEST, timeout=timeout)
        r.raise_for_status()
        try:
            return r.json()
        except Exception as e:
            raise RuntimeError(f"Failed to parse remote manifest JSON: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch remote manifest: {e}")

def download_url(url: str, dest: Path, resume: bool = True, timeout: int = 30, show_progress: bool = True):
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
        # Only show progress when requested
        if show_progress and _HAS_RICH and hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
            # Use rich progress bar
            progress = Progress(
                TextColumn("[bold green]{task.fields[filename]}", justify="right"),
                BarColumn(bar_width=None, complete_style="green"),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            )
            task = progress.add_task("download", filename=dest.name, total=total or 0)
            progress.start()
            try:
                with open(temp, mode) as f:
                    for chunk in r.iter_content(chunk_size=128 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))
            finally:
                progress.stop()
        else:
            disable_bar = not show_progress
            # If total is None, tqdm will show indeterminate progress; still allow it if show_progress=True
            pbar = tqdm(
                total=total,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                initial=existing,
                desc=dest.name,
                disable=disable_bar,
                leave=True,
            )
            try:
                with open(temp, mode) as f:
                    for chunk in r.iter_content(chunk_size=128 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        pbar.update(len(chunk))
            finally:
                pbar.close()
        # response has already been streamed and written above in the chosen
        # progress branch (rich or tqdm). Do not iterate r.iter_content again
        # here — that causes requests.exceptions.StreamConsumedError because
        # the response stream was consumed. The file has already been written
        # to the temporary .part file at this point.
    temp.rename(dest)
    # Print a confirmation line
    try:
        if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
            print(f"Download complete: {dest}")
    except Exception:
        pass
    return dest

def search_latest_and_download(codename: str, out_dir: Path, resume: bool = True, timeout: int = 30, show_progress: bool = True) -> Path:
    manifest = load_manifest(timeout=timeout)
    if codename not in manifest:
        raise ValueError(f"No entry for codename {codename} in manifest.")
    entry = manifest[codename]
    url = entry["url"]
    filename = url.split("/")[-1]
    dest = Path(out_dir) / filename
    print("Selected:", filename)
    print("Downloading from:", url)
    return download_url(url, dest, resume=resume, timeout=timeout, show_progress=show_progress)
