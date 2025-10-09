import io
from pathlib import Path
import requests
import requests_mock
import tempfile

from pixelfirm.downloader import download_url


def test_download_url_writes_file(tmp_path, requests_mock):
    url = "https://example.com/test.bin"
    data = b"0123456789" * 1000
    requests_mock.get(url, content=data, headers={"Content-Length": str(len(data))})

    dest = tmp_path / "out.bin"
    out = download_url(url, dest, resume=False, timeout=5, show_progress=False)
    assert out.exists()
    assert out.read_bytes() == data
