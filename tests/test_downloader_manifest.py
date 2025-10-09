import json
from pathlib import Path
import tempfile
import os

from pixelfirm import downloader


def test_local_manifest_parsing(tmp_path, monkeypatch):
    # create a local manifest
    m = tmp_path / "manifest.json"
    data = {"foo": {"url": "https://example.com/foo.zip", "version": "1"}}
    m.write_text(json.dumps(data))

    monkeypatch.setattr(downloader, "LOCAL_MANIFEST", m)

    # If remote fetch fails, load_manifest should return local data
    def fake_get(*a, **k):
        raise RuntimeError("no network")

    monkeypatch.setattr(downloader.requests, "get", fake_get)

    loaded = downloader.load_manifest()
    assert loaded == data


def test_merge_remote_overrides(tmp_path, monkeypatch):
    # local manifest has foo=1, remote has foo=2 and bar=1
    local = {"foo": {"url": "local", "version": "1"}}
    remote = {"foo": {"url": "remote", "version": "2"}, "bar": {"url": "r", "version": "1"}}
    m = tmp_path / "manifest.json"
    m.write_text(json.dumps(local))
    monkeypatch.setattr(downloader, "LOCAL_MANIFEST", m)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return remote

    monkeypatch.setattr(downloader.requests, "get", lambda *a, **k: FakeResponse())

    loaded = downloader.load_manifest()
    assert loaded["foo"]["url"] == "remote"
    assert "bar" in loaded
