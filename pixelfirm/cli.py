#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from .downloader import search_latest_and_download

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pixelfirm", description="Download latest Google Pixel factory image by codename")
    p.add_argument("-c", "--codename", required=True, help="device codename (e.g. tokay)")
    p.add_argument("-o", "--out", default=".", help="output directory")
    p.add_argument("--no-resume", action="store_true", help="disable resume support")
    p.add_argument("--no-progress", action="store_true", help="disable progress bar")
    p.add_argument("--timeout", type=int, default=30, help="network timeout in seconds")
    args = p.parse_args(argv)
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        path = search_latest_and_download(
            args.codename,
            out_dir,
            resume=not args.no_resume,
            timeout=args.timeout,
            show_progress=not args.no_progress,
        )
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        return 2
    print("Downloaded to:", path)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
