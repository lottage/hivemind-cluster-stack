import importlib
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PHONE_TOKEN = "test-phone-token"
READ_TOKEN = "test-read-token"
PUBLISH_TOKEN = "test-publish-token"


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    monkeypatch.setenv("BRIDGE_PHONE_TOKEN", PHONE_TOKEN)
    monkeypatch.setenv("BRIDGE_READ_TOKEN", READ_TOKEN)
    monkeypatch.setenv("BRIDGE_PUBLISH_TOKEN", PUBLISH_TOKEN)
    monkeypatch.setenv("BRIDGE_DB", str(tmp_path / "bridge.db"))
    monkeypatch.setenv("STONESAGE_REPLY_WEBHOOK", "")
    monkeypatch.setenv("USAGE_INTERVAL_S", "3600")
    monkeypatch.setenv("ANTHROPIC_ADMIN_KEY", "")
    monkeypatch.setenv("LLAMA_METRICS_URLS", "")

    import app as app_mod

    importlib.reload(app_mod)
    return app_mod


@pytest.fixture
def client(app_module):
    with TestClient(app_module.app) as c:
        yield c


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
