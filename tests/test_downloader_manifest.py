import json
from pathlib import Path
import tempfile
import os

from pixelfirm import downloader


def test_remote_manifest_fetch(monkeypatch):
    remote = {"foo": {"url": "remote", "version": "2"}, "bar": {"url": "r", "version": "1"}}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return remote

    monkeypatch.setattr(downloader.requests, "get", lambda *a, **k: FakeResponse())

    loaded = downloader.load_manifest()
    assert loaded["foo"]["url"] == "remote"
    assert "bar" in loaded
