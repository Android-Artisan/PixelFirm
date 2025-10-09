# CHANGES

## 1.0.1 - 2025-10-09

- Fix: Use repository raw manifest URL by default.
- Fix: Prefer local `manifest.json` (offline fallback) and merge remote updates when available.
- Feature: Add `--no-progress` CLI flag to disable download progress bar.
- Improvement: Better error messages for manifest fetch/parse failures.
- Test: Added a temporary `testdevice` manifest entry for local testing (remove before release).
