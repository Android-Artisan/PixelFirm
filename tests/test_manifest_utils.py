import os
from pathlib import Path

import pytest

from pixelfirm import manifest_utils as mu


def test_parse_factory_filename():
    url = "https://dl.google.com/dl/android/aosp/blazer-bd1a.250702.001-factory-f2267c45.zip"
    codename, version = mu.parse_factory_filename(url)
    assert codename == "blazer"
    assert version == "bd1a.250702.001"


def test_verify_url_head_mock(monkeypatch):
    class R:
        status_code = 200
        headers = {"content-type": "application/zip", "content-length": "123"}

    def fake_head(url, timeout, allow_redirects):
        return R()

    monkeypatch.setattr(mu.requests, "head", fake_head)
    res = mu.verify_url_head("https://example.com/foo.zip")
    assert res["ok"]
    assert res["size"] == 123


def test_update_manifest_with_entry(tmp_path, monkeypatch):
    mf = tmp_path / "manifest.json"
    url = "https://dl.google.com/dl/android/aosp/blazer-bd1a.250702.001-factory-f2267c45.zip"

    class R:
        status_code = 200
        headers = {"content-type": "application/zip", "content-length": "456"}

    def fake_head(url, timeout, allow_redirects):
        return R()

    monkeypatch.setattr(mu.requests, "head", fake_head)
    entry = mu.update_manifest_with_entry(url, manifest_path=mf, verify=True)
    assert entry["verified"]
    assert mf.exists()
    data = mf.read_text()
    assert "blazer" in data
