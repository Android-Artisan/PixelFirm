pixelfirm
========

CLI to download the latest Google Pixel factory image by codename.

- Fetches `manifest.json` online from GitHub (preferred)
- Falls back to local manifest if offline

Usage:
    pixelfirm -c (codename)

Manifest auto-updates daily via GitHub Actions scraping developers.google.com/android/images
