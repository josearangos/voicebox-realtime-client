import os

import httpx
import pytest


def _voicebox_up() -> bool:
    url = os.environ.get("VOICEBOX_URL", "http://127.0.0.1:17493")
    try:
        return httpx.get(f"{url}/health", timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


def pytest_collection_modifyitems(config, items):
    if any("voicebox" in i.keywords for i in items) and not _voicebox_up():
        skip = pytest.mark.skip(reason="Voicebox not reachable")
        for item in items:
            if "voicebox" in item.keywords:
                item.add_marker(skip)
